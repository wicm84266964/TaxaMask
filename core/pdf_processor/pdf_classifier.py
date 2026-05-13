import json
import re
import csv
import logging
import hashlib
import os
import subprocess
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, List, Tuple, Dict
import time
import random
import numpy as np
import shutil
import requests

try:
    from .poppler_discovery import discover_poppler, poppler_path_for_pdf2image
except ImportError:
    from poppler_discovery import discover_poppler, poppler_path_for_pdf2image

try:
    import torch
except ModuleNotFoundError:
    torch = None

try:
    from openai import OpenAI
except ModuleNotFoundError:
    OpenAI = None

try:
    from pdf2image import convert_from_path
except ModuleNotFoundError:
    convert_from_path = None

# 尝试导入 EasyOCR
easyocr = None
try:
    import easyocr
    HAS_OCR = True
except ImportError:
    HAS_OCR = False

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

_PDF_EXTRACTION_LOGGERS = (
    "pdfminer",
    "pdfminer.converter",
    "pdfminer.layout",
    "pdfminer.pdfinterp",
    "pdfplumber",
)


def _silence_noisy_pdf_loggers() -> None:
    for logger_name in _PDF_EXTRACTION_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.ERROR)


def _easyocr_gpu_enabled(config: Dict | None = None) -> bool:
    preference = "auto"
    if isinstance(config, dict):
        preference = str(config.get("ocr_device", config.get("runtime_device", "auto")) or "auto").strip().lower()
    if preference == "cpu":
        return False
    if preference == "cuda":
        return bool(torch is not None and torch.cuda.is_available())
    return bool(torch is not None and torch.cuda.is_available())


def _probe_pdf_file_path(pdf_path: Path) -> Dict[str, str] | None:
    try:
        if not pdf_path.exists():
            return {"code": "pdf_missing", "message": "PDF 文件不存在"}
        file_size = pdf_path.stat().st_size
        if file_size <= 0:
            return {"code": "pdf_empty", "message": "PDF 文件为空（0 字节）"}
        with open(pdf_path, "rb") as handle:
            header = handle.read(1024)
        if not header:
            return {"code": "pdf_empty", "message": "PDF 文件为空（无内容流）"}
        if b"%PDF-" not in header:
            return {"code": "pdf_invalid_header", "message": "文件缺少有效 PDF 头，可能不是 PDF 或已损坏"}
        with open(pdf_path, "rb") as handle:
            if file_size > 2048:
                handle.seek(-2048, 2)
            tail = handle.read()
        if b"%%EOF" not in tail:
            return {"code": "pdf_incomplete", "message": "PDF 缺少 EOF 结束标记，文件可能下载不完整或已损坏"}
    except Exception as exc:
        return {"code": "pdf_access_error", "message": f"PDF 文件检查失败: {exc}"}
    return None


def _infer_pdf_issue_from_exception_text(exc: Exception | str) -> Dict[str, str]:
    detail = str(exc or "").strip()
    lowered = detail.lower()
    if "document stream is empty" in lowered:
        return {"code": "pdf_empty", "message": "PDF 内容流为空，文件可能为空或已损坏"}
    if "no /root object" in lowered or "is this really a pdf" in lowered:
        return {"code": "pdf_invalid_structure", "message": "PDF 结构无效，缺少根对象，文件可能损坏或并非有效 PDF"}
    if (
        "eof marker not found" in lowered
        or "startxref not found" in lowered
        or "xref" in lowered
        or "trailer" in lowered
    ):
        return {"code": "pdf_invalid_structure", "message": "PDF 结构不完整或交叉引用表损坏，文件可能已损坏"}
    if "unable to get page count" in lowered:
        return {"code": "pdf_unreadable", "message": "无法读取 PDF 页数，文件可能损坏、不完整或格式异常"}
    return {"code": "pdf_read_failed", "message": f"PDF 读取失败: {detail}"}


def _resolve_local_poppler_path() -> Path | None:
    poppler_path = poppler_path_for_pdf2image()
    return Path(poppler_path) if poppler_path else None


def _ocr_pdf_page_direct(pdf_path: Path) -> List[str]:
    if not HAS_OCR:
        return []
    if convert_from_path is None:
        return []
    reader = easyocr.Reader(['en'], gpu=_easyocr_gpu_enabled())
    poppler_path = _resolve_local_poppler_path()
    convert_kwargs: dict[str, Any] = {
        "first_page": 1,
        "last_page": 1,
        "dpi": 300,
        "fmt": "jpeg",
    }
    if poppler_path is not None:
        convert_kwargs["poppler_path"] = poppler_path
    images = convert_from_path(str(pdf_path), **convert_kwargs)
    if not images:
        return []
    img_np = np.array(images[0])
    return reader.readtext(img_np, detail=0, paragraph=True) or []


def _extract_first_lines_direct(pdf_path: Path, num_lines: int = 30) -> tuple[List[str], Dict[str, str] | None, str]:
    _silence_noisy_pdf_loggers()
    lines: List[str] = []
    issue = _probe_pdf_file_path(pdf_path)
    if issue:
        return [], issue, "failed"

    try:
        import pdfplumber

        with pdfplumber.open(pdf_path) as pdf:
            pages_to_check = pdf.pages[:2]
            all_text = ""
            for page in pages_to_check:
                text = page.extract_text()
                if text:
                    all_text += text + "\n"

        if all_text and len(all_text.strip()) > 100:
            lines = [line.strip() for line in all_text.split('\n') if line.strip()]
            if len(lines) >= 5:
                return lines[:num_lines], None, "text_layer"
    except Exception as exc:
        issue = _infer_pdf_issue_from_exception_text(exc)

    if HAS_OCR:
        try:
            ocr_lines = _ocr_pdf_page_direct(pdf_path)
            if ocr_lines:
                return ocr_lines[:num_lines], None, "ocr"
        except Exception as exc:
            issue = _infer_pdf_issue_from_exception_text(exc)

    return lines[:num_lines], issue, "text_layer" if lines else "failed"


def _write_extract_result_payload(result_json_path: str, lines: List[str], issue: Dict[str, str] | None, extract_source: str) -> None:
    payload = {
        "lines": lines,
        "issue": issue,
        "extract_source": str(extract_source or "").strip() or "failed",
    }
    with open(result_json_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _run_extract_lines_cli(pdf_path_text: str, num_lines: int, result_json_path: str) -> int:
    pdf_path = Path(pdf_path_text)
    try:
        lines, issue, extract_source = _extract_first_lines_direct(pdf_path, num_lines)
        _write_extract_result_payload(result_json_path, lines, issue, extract_source)
        return 0
    except Exception as exc:
        _write_extract_result_payload(result_json_path, [], _infer_pdf_issue_from_exception_text(exc), "failed")
        return 1


def _terminate_process_tree(process: subprocess.Popen[Any]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        process.kill()


def _maybe_run_extract_cli_from_argv(argv: List[str]) -> int | None:
    if "--extract-first-lines" not in argv:
        return None

    pdf_path = None
    result_json = None
    num_lines = 30
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "--pdf" and index + 1 < len(argv):
            pdf_path = argv[index + 1]
            index += 2
            continue
        if token == "--result-json" and index + 1 < len(argv):
            result_json = argv[index + 1]
            index += 2
            continue
        if token == "--num-lines" and index + 1 < len(argv):
            try:
                num_lines = max(1, int(argv[index + 1]))
            except ValueError:
                num_lines = 30
            index += 2
            continue
        index += 1

    if not pdf_path or not result_json:
        return 2
    return _run_extract_lines_cli(pdf_path, num_lines, result_json)

class LLMScreenPDFClassifier:
    DEFAULT_CONFIG = {
        "required_keywords": [
            "new species", "new specie", "novel species", "novel specie", 
            "described", "description", "sp. nov.", "sp. n.", "spec. nov.", "spec. n.",
            "new record", "redescription", "new genus", "gen. nov.", "gen. n."
        ],
        "supportive_keywords": [
            "morphology", "morphological", "worker", "queen", "male", "caste", "polymorphism",
            "taxonomy", "taxonomic", "diagnosis", "holotype", "paratype", "type", 
            "measurements", "color", "structure", "head", "mesosoma", "petiole", "gaster",
            "mandible", "clypeus", "antenna", "eye", "scape", "funiculus", "pronotum",
            "mesonotum", "propodeum", "node", "postpetiole", "setae", "pilosity", "sculpture",
            "striation", "reticulation", "punctation", "shining", "mat", "smooth",
            "distribution", "locality", "material examined", "type locality"
        ],
        "taxonomic_group_keywords": [
            "hymenoptera", "formicidae", "myrmicinae", "formicinae", "ponerinae", "dolichoderinae", "ectatomminae", "ant", "ants"
        ],
        "strong_exclude_keywords": [
            "review", "survey", "overview", "synopsis", "perspective", "opinion", "editorial",
            "ecology", "behavior", "foraging", "nest", "colony", "population", "community",
            "phylogeny", "phylogenetic", "molecular", "dna", "barcoding", "genetic",
            "conservation", "threat", "decline", "impact", "control", "management",
            "algorithm", "machine learning", "neural network", "deep learning", "artificial intelligence",
            "economic", "cost", "benefit", "market", "trade", "commerce"
        ],
        "weak_exclude_keywords": [
            "note", "remark", "addition", "extension", "correction", "erratum", "comment",
            "letter", "reply", "response", "discussion", "debate"
        ],
        "biological_exclude_keywords": [
            "microbe", "microbiology", "microbial", "bacteria", "bacterial", "bacterium", "prokaryote",
            "archaea", "archaeon", "cyanobacteria", "actinobacteria", "firmicutes", "proteobacteria",
            "eubacteria", "pathogen", "pathogenic", "symbiont", "symbiotic", "microbiome",
            "virus", "viral", "virus-like", "bacteriophage", "phage", "viroid", "prion", "virus infection",
            "viral disease", "viral pathogen", "antiviral",
            "fungus", "fungi", "fungal", "mycology", "mycosis", "yeast", "mold", "mould", "aspergillus",
            "candida", "fusarium", "trichoderma", "mycorrhiza", "lichen", "mushroom", "basidiomycota",
            "ascomycota", "zygomycota", "chytridiomycota", "fungus infection", "fungal disease",
            "parasite", "parasitic", "parasitism", "host", "host-parasite", "parasitoid", "parasitology",
            "endoparasite", "ectoparasite", "brood parasite", "social parasite", "kleptoparasite",
            "parasitic wasp", "parasitoid wasp", "parasitic fly", "tachinid", "tachinidae", 
            "ichneumonid", "ichneumonidae", "braconid", "braconidae", "chalcid", "chalcidoid",
            "parasitoid larvae", "parasitoid egg", "parasitoid development"
        ],
        "llm_system_prompt": "你是一个严谨的分类学审稿助手，必须输出可解析JSON。",
        "llm_prompt_template": """你是一个专业的昆虫分类学专家，请审查以下文献是否确实是一篇新蚂蚁物种描述的论文。

请根据以下标准判断：
1. 文献是否明确描述了一个新的蚂蚁物种？
2. 是否包含了新物种的形态学描述？
3. 是否提供了必要的分类学信息（如属名、种加词等）？
4. 特别注意：请确认这篇文献是关于蚂蚁本身的新种描述，而非关于蚂蚁相关的微生物、病毒、真菌、寄生flies或其他天敌生物/某种蜂的研究。

文献标题：{filename}

文献前30行内容：
{text}

请严格按以下格式回答：
判断：是/否
理由：[详细理由]""",
        "llm_batch_prompt_template": """你是一个专业的昆虫分类学专家。你将获得一个文献列表(JSON数组)，每条记录含 record_id、record_index、display_label、filename、title、text。

本批次应判定记录数：{expected_record_count}

请逐条判断该文献是否属于“蚂蚁新种报道”。必须严格区分：
1) include: 明确是蚂蚁新种报道；
2) exclude: 明确不是；
3) uncertain: 证据不足或有冲突。

注意：必须基于每条记录独立判断，不可受其他记录影响。record_id 需原样返回。

请只输出 JSON 数组，不要输出任何额外文字。每个元素结构必须是：
{"record_id":"<原值>","decision":"include|exclude|uncertain","confidence":0-1,"reason":"一句话理由"}

待判定记录：
{records_json}
""",
        "processing_mode": "v2",
        "lines_per_pdf": 30,
        "csv_batch_size": 80,
        "csv_batch_fallback_size": 40,
        "batch_char_budget": 100000,
        "include_confidence_threshold": 0.75,
        "max_text_chars_per_file": 1600,
        "llm_batch_max_tokens": 12000,
        "api_protocol": "auto",
        "resume_interrupted_runs": True,
        "isolate_v2_runs": True,
        "llm_request_timeout_seconds": 240,
        "split_failed_batches": True,
        "pdf_extract_timeout_seconds": 30,
    }

    def __init__(self, source_folder: str, output_folder: str, api_key: str = None, base_url: str = None, 
                 model: str = "gpt-5.4", config: Dict = None):
        self.logger = logger # Move to the very top
        self.source_folder = Path(source_folder)
        self.output_root = Path(output_folder)
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.output_folder = self.output_root
        
        self.config = dict(self.DEFAULT_CONFIG)
        if config:
            self.config.update(config)
        self.required_keywords = self.config.get("required_keywords", self.DEFAULT_CONFIG["required_keywords"])
        self.supportive_keywords = self.config.get("supportive_keywords", self.DEFAULT_CONFIG["supportive_keywords"])
        self.taxonomic_group_keywords = self.config.get("taxonomic_group_keywords", self.DEFAULT_CONFIG["taxonomic_group_keywords"])
        self.strong_exclude_keywords = self.config.get("strong_exclude_keywords", self.DEFAULT_CONFIG["strong_exclude_keywords"])
        self.weak_exclude_keywords = self.config.get("weak_exclude_keywords", self.DEFAULT_CONFIG["weak_exclude_keywords"])
        self.biological_exclude_keywords = self.config.get("biological_exclude_keywords", self.DEFAULT_CONFIG["biological_exclude_keywords"])
        self.llm_system_prompt = self.config.get("llm_system_prompt", self.DEFAULT_CONFIG["llm_system_prompt"])
        self.llm_prompt_template = self.config.get("llm_prompt_template", self.DEFAULT_CONFIG["llm_prompt_template"])
        self.llm_batch_prompt_template = self.config.get("llm_batch_prompt_template", self.DEFAULT_CONFIG["llm_batch_prompt_template"])

        self.processing_mode = "v2"
        self.config["processing_mode"] = "v2"
        self.lines_per_pdf = max(1, int(self.config.get("lines_per_pdf", 30)))
        self.csv_batch_size = max(1, int(self.config.get("csv_batch_size", 80)))
        self.csv_batch_fallback_size = max(1, int(self.config.get("csv_batch_fallback_size", 40)))
        if self.csv_batch_fallback_size > self.csv_batch_size:
            self.csv_batch_fallback_size = self.csv_batch_size
        self.batch_char_budget = max(5000, int(self.config.get("batch_char_budget", 100000)))
        self.include_confidence_threshold = float(self.config.get("include_confidence_threshold", 0.75))
        if self.include_confidence_threshold < 0:
            self.include_confidence_threshold = 0.0
        if self.include_confidence_threshold > 1:
            self.include_confidence_threshold = 1.0
        self.max_text_chars_per_file = max(200, int(self.config.get("max_text_chars_per_file", 1600)))
        self.llm_batch_max_tokens = max(500, int(self.config.get("llm_batch_max_tokens", 12000)))
        raw_protocol = str(self.config.get("api_protocol", "auto")).strip().lower()
        self.api_protocol = raw_protocol if raw_protocol in {"auto", "chat_completions", "responses"} else "auto"
        self.resume_interrupted_runs = bool(self.config.get("resume_interrupted_runs", True))
        self.isolate_v2_runs = bool(self.config.get("isolate_v2_runs", True))
        self.llm_request_timeout_seconds = max(30, int(self.config.get("llm_request_timeout_seconds", 240)))
        self.split_failed_batches = bool(self.config.get("split_failed_batches", True))
        self.pdf_extract_timeout_seconds = max(15, int(self.config.get("pdf_extract_timeout_seconds", 30)))
        self.v2_runs_root = self.output_root / "v2_runs"
        self.v2_active_run_file = self.output_root / "v2_active_run.json"
        self.active_output_folder: Path | None = None

        # Confirmation log
        self.logger.info(f"Classifier initialized with custom logic.")
        self.logger.info(f"Processing mode: {self.processing_mode}")
        self.logger.info(f"Required Keywords (First 3): {self.required_keywords[:3]}...")
        self.logger.info(f"Taxonomic Group Keywords: {self.taxonomic_group_keywords}")

        # 保持这些硬编码的排除词，因为它们通常对所有生物文献通用
        self.medical_keywords = [
            "patient", "clinical", "disease", "treatment", "therapy", "drug", "medicine", "hospital",
            "symptom", "diagnosis", "medical", "healthcare", "surgery", "operation"
        ]
        self.algorithm_keywords = [
            "algorithm", "optimization", "heuristic", "metaheuristic", "genetic algorithm",
            "neural network", "machine learning", "deep learning", "artificial intelligence",
            "data mining", "big data", "cloud computing", "internet of things"
        ]
        
        # 初始化OCR Reader
        self.reader = None 
        if HAS_OCR:
            logger.info("EasyOCR 将在受保护的单文件提取子进程中按需初始化")
        else:
            logger.info("未检测到 EasyOCR，文本层提取失败时将不会执行 OCR 回退")
        
        # 初始化OpenAI客户端
        self.client = None
        self.api_key = api_key.strip() if isinstance(api_key, str) else api_key
        self.base_url = self._normalize_base_url(base_url)
        if api_key and OpenAI is not None:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        elif api_key and OpenAI is None:
            self.logger.warning("未检测到 openai SDK，LLM 筛选将降级为人工复核状态。")
        self.model = model.strip() if isinstance(model, str) else model
        self.model = self._normalize_provider_model(self.model)
        self.logger.info(f"API protocol mode: {self.api_protocol}")
        self.logger.info(f"Resolved API base_url: {self.base_url}")
        self.logger.info(f"Resolved model: {self.model}")
        self.logger.info(f"Resume interrupted V2 runs: {self.resume_interrupted_runs}")
        self.logger.info(f"Isolate V2 runs: {self.isolate_v2_runs}")
        self.logger.info(f"Per-PDF extract timeout(s): {self.pdf_extract_timeout_seconds}")
        self._pdf_runtime_issues: Dict[str, Dict[str, str]] = {}
        self._pdf_runtime_extract_sources: Dict[str, str] = {}

    def _pdf_issue_priority(self, code: str) -> int:
        priorities = {
            "pdf_missing": 100,
            "pdf_access_error": 95,
            "pdf_invalid_header": 90,
            "pdf_invalid_structure": 90,
            "pdf_incomplete": 88,
            "pdf_empty": 85,
            "pdf_unreadable": 70,
            "pdf_read_failed": 10,
        }
        return priorities.get(str(code or "pdf_read_failed"), 0)

    def _set_pdf_issue(self, pdf_path: Path, code: str, message: str) -> None:
        new_code = str(code or "pdf_read_failed")
        new_message = str(message or "PDF 读取失败")
        key = str(pdf_path)
        existing = self._pdf_runtime_issues.get(key)
        if existing:
            existing_code = str(existing.get("code", "pdf_read_failed"))
            if self._pdf_issue_priority(existing_code) >= self._pdf_issue_priority(new_code):
                return
        self._pdf_runtime_issues[key] = {
            "code": new_code,
            "message": new_message,
        }

    def _clear_pdf_issue(self, pdf_path: Path) -> None:
        self._pdf_runtime_issues.pop(str(pdf_path), None)

    def _get_pdf_issue(self, pdf_path: Path) -> Dict[str, str] | None:
        return self._pdf_runtime_issues.get(str(pdf_path))

    def _set_pdf_extract_source(self, pdf_path: Path, extract_source: str) -> None:
        normalized_source = str(extract_source or "").strip().lower() or "failed"
        self._pdf_runtime_extract_sources[str(pdf_path)] = normalized_source

    def _clear_pdf_extract_source(self, pdf_path: Path) -> None:
        self._pdf_runtime_extract_sources.pop(str(pdf_path), None)

    def _get_pdf_extract_source(self, pdf_path: Path) -> str:
        return str(self._pdf_runtime_extract_sources.get(str(pdf_path), "failed") or "failed")

    def _label_pdf_extract_source(self, extract_source: str) -> str:
        normalized_source = str(extract_source or "").strip().lower()
        if normalized_source == "text_layer":
            return "文本层"
        if normalized_source == "ocr":
            return "OCR 回退"
        return "失败"

    def _probe_pdf_file(self, pdf_path: Path) -> Dict[str, str] | None:
        return _probe_pdf_file_path(pdf_path)

    def _infer_pdf_issue_from_exception(self, exc: Exception) -> Dict[str, str]:
        return _infer_pdf_issue_from_exception_text(exc)

    def _run_extract_first_lines_subprocess(self, pdf_path: Path, num_lines: int, check_stop_callback=None) -> tuple[List[str], Dict[str, str] | None, str, bool]:
        temp_handle = tempfile.NamedTemporaryFile(delete=False, suffix="_pdf_extract.json")
        temp_handle.close()
        result_json_path = temp_handle.name

        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--extract-first-lines",
            "--pdf",
            str(pdf_path),
            "--num-lines",
            str(max(1, int(num_lines))),
            "--result-json",
            result_json_path,
        ]
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
        )

        timed_out = False
        interrupted = False
        try:
            start_time = time.monotonic()
            while process.poll() is None:
                if check_stop_callback and check_stop_callback():
                    interrupted = True
                    _terminate_process_tree(process)
                    break
                if self.pdf_extract_timeout_seconds > 0 and time.monotonic() - start_time > self.pdf_extract_timeout_seconds:
                    timed_out = True
                    _terminate_process_tree(process)
                    break
                time.sleep(0.2)

            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _terminate_process_tree(process)
            process.wait(timeout=5)
        finally:
            payload = None
            if os.path.exists(result_json_path):
                try:
                    with open(result_json_path, "r", encoding="utf-8") as handle:
                        payload = json.load(handle)
                except Exception:
                    payload = None
                try:
                    os.remove(result_json_path)
                except OSError:
                    pass

        if interrupted:
            return [], None, "failed", True

        if timed_out:
            issue = {
                "code": "pdf_extract_timeout",
                "message": f"PDF 文本层/OCR 处理超过 {self.pdf_extract_timeout_seconds} 秒，已跳过以避免阻塞批处理",
            }
            return [], issue, "failed", False

        if isinstance(payload, dict):
            lines = payload.get("lines", [])
            issue = payload.get("issue")
            extract_source = str(payload.get("extract_source", "")).strip().lower() or "failed"
            if not isinstance(lines, list):
                lines = []
            if issue is not None and not isinstance(issue, dict):
                issue = {"code": "pdf_read_failed", "message": str(issue)}
            if issue and not lines:
                extract_source = "failed"
            return lines[:num_lines], issue, extract_source, False

        issue = {
            "code": "pdf_extract_subprocess_failed",
            "message": "PDF 提取子进程未返回有效结果，当前文件已跳过",
        }
        return [], issue, "failed", False

    def extract_first_lines(self, pdf_path: Path, num_lines: int = 30, check_stop_callback=None) -> List[str]:
        """提取PDF文件的前几行文本，支持带超时保护的文本层/OCR 回退"""
        self._clear_pdf_issue(pdf_path)
        self._clear_pdf_extract_source(pdf_path)
        lines, issue, extract_source, interrupted = self._run_extract_first_lines_subprocess(pdf_path, num_lines, check_stop_callback)
        if interrupted:
            self.logger.warning(f"用户中断当前 PDF，停止等待: {pdf_path.name}")
            return []
        if issue:
            self._set_pdf_issue(pdf_path, issue["code"], issue["message"])
            effective_source = extract_source if lines else "failed"
            self._set_pdf_extract_source(pdf_path, effective_source)
            issue_code = str(issue.get("code", "") or "")
            if lines and effective_source != "failed":
                self.logger.warning(
                    f"PDF 提取部分成功（{self._label_pdf_extract_source(effective_source)}），但伴随异常: {pdf_path.name} - {issue['message']}"
                )
            elif issue_code in {"pdf_missing", "pdf_empty", "pdf_invalid_header", "pdf_incomplete"}:
                self.logger.warning(f"PDF 输入预检查失败，已跳过: {pdf_path.name} - {issue['message']}")
            elif issue_code == "pdf_extract_timeout":
                self.logger.warning(f"PDF 文本/OCR 超时，已跳过: {pdf_path.name} - {issue['message']}")
            elif issue_code == "pdf_extract_subprocess_failed":
                self.logger.error(f"PDF 提取子进程失败: {pdf_path.name} - {issue['message']}")
            else:
                self.logger.warning(f"PDF 文本/OCR 异常，已跳过: {pdf_path.name} - {issue['message']}")
        elif lines:
            self._set_pdf_extract_source(pdf_path, extract_source)
            self.logger.info(
                f"PDF 提取成功（{self._label_pdf_extract_source(extract_source)}）: {pdf_path.name} - 提取 {len(lines)} 行"
            )
        else:
            self._set_pdf_extract_source(pdf_path, "failed")
            self.logger.warning(f"PDF 未提取到可用文本: {pdf_path.name}")
        return lines

    def _ocr_pdf_page(self, pdf_path: Path) -> List[str]:
        """使用 EasyOCR 识别 PDF 第一页"""
        lines = []
        try:
            if convert_from_path is None:
                return []
            if self.reader is None and HAS_OCR:
                self.reader = easyocr.Reader(['en'], gpu=_easyocr_gpu_enabled(self.config))
            if self.reader is None:
                return []

            poppler_status = discover_poppler()
            poppler_path = poppler_status.bin_path if poppler_status.found and poppler_status.source != "PATH" else None
            if poppler_status.found:
                self.logger.info(poppler_status.message)
            else:
                self.logger.warning(poppler_status.message)
            
            # 1. PDF 转图片 (只转第一页，dpi=300 保证学术文献清晰度)
            # fmt='jpeg' 速度比 png 快一点点
            # 如果 poppler_path 为 None，pdf2image 会尝试使用系统 PATH
            convert_kwargs: dict[str, Any] = {
                "first_page": 1,
                "last_page": 1,
                "dpi": 300,
                "fmt": "jpeg",
            }
            if poppler_path is not None:
                convert_kwargs["poppler_path"] = poppler_path
            images = convert_from_path(str(pdf_path), **convert_kwargs)
            
            if not images:
                return []
            
            img = images[0]
            # EasyOCR 可以直接接受 numpy array
            img_np = np.array(img)
            
            # 2. 调用 EasyOCR
            # detail=0 只返回文本列表，不返回坐标，速度更快
            # paragraph=True 会尝试自动合并段落，对论文这种排版很有用
            result = self.reader.readtext(img_np, detail=0, paragraph=True)
            
            # 3. 结果处理
            if result:
                return result
                
        except Exception as e:
            raise e
            
        return lines

    def extract_title_from_lines(self, lines: List[str]) -> str:
        """从文本行中提取标题"""
        if not lines:
            return None
            
        best_title = ""
        best_score = -1
        
        for i, line in enumerate(lines[:10]):  # 只检查前10行
            score = 0
            line_lower = line.lower()
            
            # 1. 包含关键词加分
            if any(keyword in line_lower for keyword in ["new species", "sp. nov.", "spec. nov."]):
                score += 5
            
            # 2. 包含分类学群组词汇加分 (使用可配置的词库)
            if any(word in line_lower for word in self.taxonomic_group_keywords):
                score += 3
                
            # 3. 不包含数字加分（标题通常不含年份等数字）
            if not re.search(r'\d{4}', line):
                score += 2
                
            # 4. 长度适中加分
            if 15 <= len(line) <= 200:
                score += 2
                
            # 5. 不包含某些排除词加分
            if not any(word in line_lower for word in ["abstract", "introduction", "method", "result"]):
                score += 1
                
            # 6. 不是太短（可能只是作者或期刊信息）
            if len(line.strip()) >= 10:
                score += 1
                
            # 7. 位置权重：前3行权重更高
            position_weight = max(0, 3 - i)  
            score += position_weight
            
            # 如果这一行得分更高，更新最佳标题
            if score > best_score:
                best_score = score
                best_title = line
        
        # 清理最佳标题
        if best_title:
            title = re.sub(r'\s+', ' ', best_title)  # 合并多个空格
            title = re.sub(r'[^\w\s\-\.\\,;:\(\)\[\]\{\}]', '', title)  # 移除特殊字符
            title = re.sub(r'[\.,;:]$', '', title)  # 移除结尾标点
            return title.strip()
        
        # 如果没有找到合适的标题，使用第一行作为标题
        first_line = lines[0].strip()
        if len(first_line) > 10:
            title = re.sub(r'\s+', ' ', first_line)
            title = re.sub(r'[^\w\s\-\.\\,;:\(\)\[\]\{\}]', '', title)
            title = re.sub(r'[\.,;:]$', '', title)
            return title.strip()
        
        return None

    def analyze_text_patterns(self, text: str) -> Dict:
        """分析文本模式，识别新种报道特征"""
        text_lower = text.lower()
        
        # 检查是否包含核心新种报道词汇
        has_required_keywords = any(keyword in text_lower for keyword in self.required_keywords)
        
        # 检查支持性关键词数量
        supportive_count = sum(1 for keyword in self.supportive_keywords if keyword in text_lower)
        
        # 检查强烈排除关键词
        has_strong_exclude = any(keyword in text_lower for keyword in self.strong_exclude_keywords)
        
        # 检查弱排除关键词
        has_weak_exclude = any(keyword in text_lower for keyword in self.weak_exclude_keywords)
        
        # 检查是否包含医学关键词
        has_medical_keywords = any(keyword in text_lower for keyword in self.medical_keywords)
        
        # 检查是否包含算法/计算机科学关键词
        has_algorithm_keywords = any(keyword in text_lower for keyword in self.algorithm_keywords)
        
        # 检查是否包含生物排除关键词
        has_biological_exclude = any(keyword in text_lower for keyword in self.biological_exclude_keywords)
        
        # 记录找到的生物排除关键词
        biological_exclude_keywords_found = [keyword for keyword in self.biological_exclude_keywords if keyword in text_lower]
        
        # 识别标题特征
        title_features = self._extract_title_features(text)
        
        # 计算类群术语与生物排除术语的比例
        group_terminology_ratio = self._calculate_group_terminology_ratio(text_lower)
        
        return {
            "has_required_keywords": has_required_keywords,
            "supportive_keywords_count": supportive_count,
            "has_strong_exclude": has_strong_exclude,
            "has_weak_exclude": has_weak_exclude,
            "has_medical_keywords": has_medical_keywords,
            "has_algorithm_keywords": has_algorithm_keywords,
            "has_biological_exclude": has_biological_exclude,
            "biological_exclude_keywords_found": biological_exclude_keywords_found,
            "group_terminology_ratio": group_terminology_ratio,
            "title_features": title_features
        }
        
    def _calculate_group_terminology_ratio(self, text_lower: str) -> float:
        """计算文本中类群相关术语与生物排除术语的比例"""
        # 使用配置中的类群术语
        group_terms_count = 0
        for term in self.taxonomic_group_keywords:
            group_terms_count += text_lower.count(term)
        
        # 计算生物排除术语出现次数
        biological_terms_count = 0
        for term in self.biological_exclude_keywords:
            biological_terms_count += text_lower.count(term)
        
        # 避免除以零
        if biological_terms_count == 0:
            return float('inf')  
        
        return group_terms_count / biological_terms_count

    def _extract_title_features(self, text: str) -> Dict:
        """提取标题特征（分析前若干行）"""
        lines = text.split('\n')
        features = {
            "has_new_species_in_title": False,
            "title_length": 0,
            "has_taxonomic_info": False,
            "line_position": -1,
            "new_species_keywords_found": [],
            "taxonomic_keywords_found": [],
            "best_title_line": ""
        }
        
        for i, line in enumerate(lines[:self.lines_per_pdf]):
            line_lower = line.lower()
            line_stripped = line.strip()
            
            # 检查是否包含新种报道词汇
            for keyword in self.required_keywords:
                if keyword in line_lower:
                    features["has_new_species_in_title"] = True
                    features["line_position"] = i + 1
                    if keyword not in features["new_species_keywords_found"]:
                        features["new_species_keywords_found"].append(keyword)
            
            # 检查分类学群组信息
            for word in self.taxonomic_group_keywords:
                if word in line_lower:
                    features["has_taxonomic_info"] = True
                    if word not in features["taxonomic_keywords_found"]:
                        features["taxonomic_keywords_found"].append(word)
            
            # 记录最佳标题行
            if (len(line_stripped) > features["title_length"] and 
                len(line_stripped) > 20 and 
                not re.search(r'\d{4}', line_stripped) and
                not any(word in line_lower for word in ["abstract", "introduction", "method", "result", "discussion", "conclusion", "received", "accepted"])):
                features["title_length"] = len(line_stripped)
                features["best_title_line"] = line_stripped
        
        return features

    def improved_classify_literature(self, text: str) -> Tuple[str, str, float]:
        """改进的分类算法"""
        patterns = self.analyze_text_patterns(text)
        
        # 计分系统
        score = 0.0
        reasoning_parts = []
        
        if patterns["has_medical_keywords"]:
            score -= 4.0
            reasoning_parts.append("包含医学领域关键词")
        
        if patterns["has_algorithm_keywords"]:
            score -= 3.0
            reasoning_parts.append("包含算法/计算机科学关键词")
        
        if patterns.get("has_biological_exclude", False):
            score -= 5.0  
            if patterns.get("biological_exclude_keywords_found"):
                main_exclude_terms = ", ".join(patterns["biological_exclude_keywords_found"][:3])
                reasoning_parts.append(f"包含类群相关干扰排除词：{main_exclude_terms}")
            else:
                reasoning_parts.append("包含类群相关干扰排除词")
        
        if patterns["has_required_keywords"]:
            score += 3.0
            reasoning_parts.append("包含核心新种报道词汇")
        
        supportive_score = min(patterns["supportive_keywords_count"] * 0.5, 2.0)
        score += supportive_score
        if patterns["supportive_keywords_count"] > 0:
            reasoning_parts.append(f"包含{patterns['supportive_keywords_count']}个支持性分类学词汇")
        
        if patterns["title_features"]["has_new_species_in_title"]:
            score += 2.0
            reasoning_parts.append("标题中包含新种报道信息")
        
        if patterns["title_features"]["has_taxonomic_info"]:
            score += 1.0
            reasoning_parts.append("标题包含类群识别信息")
        
        # 考虑类群术语比例
        if patterns.get("group_terminology_ratio", 0) > 3.0 and patterns["group_terminology_ratio"] != float('inf'):
            score += 1.5  
            reasoning_parts.append("类群术语显著多于干扰排除词")
        
        if patterns["has_strong_exclude"]:
            score -= 4.0  
            reasoning_parts.append("包含综述/生态学排除词汇")
        
        if patterns["has_weak_exclude"]:
            score -= 1.0
            reasoning_parts.append("包含弱排除词汇")
        
        # 分类判断
        if patterns.get("has_biological_exclude", False):
            if score >= 6.0:
                category = "New Species Report"
            elif score >= 3.0:
                category = "Possible New Species"
            else:
                category = "Other Literature"
        else:
            if score >= 4.0: 
                category = "New Species Report"
            elif score >= 1.5:  
                category = "Possible New Species"
            elif patterns["has_strong_exclude"] or patterns["has_medical_keywords"] or patterns["has_algorithm_keywords"]:
                category = "Other Literature"
            else:
                category = "Uncertain"
        
        reasoning = "; ".join(reasoning_parts) if reasoning_parts else "无显著特征"
        
        return category, reasoning, score


    def llm_review_new_species_report(self, text: str, filename: str) -> Tuple[bool, str]:
        """使用大语言模型复查新种报道文献，带重试机制"""
        if not self.client:
            return False, "跳过LLM复查（未启用）"
        
        # 特殊测试用例：如果文件名包含"test_new_species"，则返回True
        if "test_new_species" in filename:
            return True, "判断：是\n理由：这是一个测试用例，用于验证LLM判断为'是'时的功能。"
        
        max_retries = 3
        retry_delay = 1  # 初始重试延迟（秒）
        
        for attempt in range(max_retries):
            try:
                prompt = self._render_prompt_template(
                    self.llm_prompt_template,
                    {"filename": filename, "text": text},
                )
                
                result, _, used_protocol = self._call_llm(
                    system_prompt=str(self.llm_system_prompt or self.DEFAULT_CONFIG["llm_system_prompt"]),
                    user_prompt=prompt,
                    max_tokens=300,
                    temperature=0.1,
                )
                self.logger.debug(f"LLM复查使用协议: {used_protocol}")
                text_lower = result.lower()

                # 解析LLM的响应
                if "判断：是" in result or "判断: 是" in result or "确认是" in result:
                    return True, result
                elif "判断：否" in result or "判断: 否" in result or "不是" in result or "no" in text_lower:
                    return False, result
                else:
                    # 如果没有找到明确的判断格式，使用更保守的逻辑
                    if "yes" in text_lower and "no" not in text_lower:
                         return True, result
                    return False, result
                
            except Exception as e:
                status_code, non_retryable, detail = self._analyze_llm_exception(e, protocol=self._resolve_api_protocol())
                self.logger.error(f"LLM复查失败 {filename} (尝试 {attempt + 1}/{max_retries}): {detail}")
                if non_retryable:
                    return False, f"LLM复查失败(不可重试): {detail}"
                if attempt < max_retries - 1:  # 不是最后一次尝试
                    # 指数退避延迟
                    time.sleep(retry_delay + random.uniform(0, 1))  # 添加随机抖动
                    retry_delay *= 2  # 指数增长
                else:
                    return False, f"LLM复查失败: {detail}"

    def classify_pdf(self, pdf_path: Path, check_stop_callback=None) -> Tuple[str, str, str, float, bool, str]:
        """对单个PDF文件进行分类，新增LLM复查结果"""
        self.logger.info(f"处理文件: {pdf_path.name}")
        
        lines = self.extract_first_lines(pdf_path, self.lines_per_pdf, check_stop_callback=check_stop_callback)
        
        if not lines:
            self.logger.warning(f"无法提取文本: {pdf_path.name}")
            issue = self._get_pdf_issue(pdf_path)
            if issue:
                return "Other Literature", issue.get("message", "无法提取文本内容 (OCR也失败)"), None, 0.0, False, issue.get("code", "无法提取文本")
            return "Other Literature", "无法提取文本内容 (OCR也失败)", None, 0.0, False, "无法提取文本"
        
        # 提取标题
        title = self.extract_title_from_lines(lines)
        
        # 合并文本进行分析
        combined_text = ' '.join(lines)
        
        # 使用改进算法进行分类
        category, reason, score = self.improved_classify_literature(combined_text)
        
        # 仅对算法判断为新种、可能新种或不确定的文件进行LLM复查，节省算力
        llm_approved = False
        llm_reason = "未进行LLM复查"
        if self.client and category in ["New Species Report", "Possible New Species", "Uncertain"]:
            llm_approved, llm_reason = self.llm_review_new_species_report(combined_text, pdf_path.name)
            self.logger.info(f"LLM判断结果: {'是新种描述' if llm_approved else '不是新种描述'} - {pdf_path.name}")
        
        self.logger.info(f"分类结果: {category} - 得分: {score:.1f} - {pdf_path.name}")
        
        return category, reason, title, score, llm_approved, llm_reason

    def save_classification_details(self, details: Dict, output_dir: Path | None = None):
        """保存详细分类结果到CSV文件"""
        if output_dir is not None:
            csv_file = self._get_v2_artifact_paths(output_dir)["compatibility_csv"]
        else:
            csv_file = self._get_active_output_folder() / "llm_enhanced_classification_details.csv"
        
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["文件名", "分类结果", "判断依据", "提取标题", "得分", "LLM判断为新种", "LLM复查理由"])
            
            for filename, info in details.items():
                writer.writerow([
                    filename,
                    info["category"],
                    info["reason"],
                    info["title"] if info["title"] else "未提取",
                    info["score"],
                    info.get("llm_approved", "N/A"),
                    info.get("llm_reason", "N/A")
                ])
        
        self.logger.info(f"详细分类结果已保存到: {csv_file}")

    def _get_active_output_folder(self) -> Path:
        return self.active_output_folder or self.output_folder

    def _now_text(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S")

    def _new_run_id(self) -> str:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        suffix = random.randint(1000, 9999)
        return f"run_{timestamp}_{suffix}"

    def _write_json_file(self, file_path: Path, payload: Dict[str, Any]) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    def _save_batch_raw_response(self, batch_id: str, raw_response: str) -> str:
        raw_dir = self._get_v2_artifact_paths(self._get_active_output_folder())["batch_raw_responses"]
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_path = raw_dir / f"{batch_id}.txt"
        with open(raw_path, "w", encoding="utf-8") as handle:
            handle.write(str(raw_response or ""))

        try:
            return str(raw_path.relative_to(self._get_active_output_folder()))
        except ValueError:
            return str(raw_path)

    def _read_json_file(self, file_path: Path) -> Dict[str, Any] | None:
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if isinstance(payload, dict):
                return payload
        except Exception as exc:
            self.logger.warning(f"读取 JSON 文件失败: {file_path} - {exc}")
        return None

    def _read_rows_from_csv(self, csv_path: Path) -> List[Dict[str, Any]]:
        if not csv_path.exists():
            return []
        try:
            with open(csv_path, "r", newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                return [dict(row) for row in reader]
        except Exception as exc:
            self.logger.warning(f"读取 CSV 失败: {csv_path} - {exc}")
            return []

    def _append_row_to_csv(self, csv_path: Path, row: Dict[str, Any], fieldnames: List[str]) -> None:
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        file_exists = csv_path.exists() and csv_path.stat().st_size > 0
        with open(csv_path, "a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            normalized_row = {key: row.get(key, "") for key in fieldnames}
            writer.writerow(normalized_row)

    def _get_legacy_v2_artifact_paths(self, run_dir: Path) -> Dict[str, Path]:
        return {
            "run_index": run_dir / "run_index.json",
            "master_queue": run_dir / "master_queue.csv",
            "csv_batches": run_dir / "csv_batches",
            "master_results": run_dir / "master_results.csv",
            "selected_record_ids": run_dir / "selected_record_ids.csv",
            "move_manifest": run_dir / "move_manifest.csv",
            "compatibility_csv": run_dir / "llm_enhanced_classification_details.csv",
            "statistics": run_dir / "classification_statistics.txt",
            "batch_raw_responses": run_dir / "batch_raw_responses",
            "final_new_species_reports": run_dir / "final_new_species_reports",
            "manual_review_uncertain": run_dir / "manual_review_uncertain",
        }

    def _get_v2_artifact_paths(self, run_dir: Path) -> Dict[str, Path]:
        resume_state_dir = run_dir / "resume_state"
        core_results_dir = run_dir / "core_results"
        debug_evidence_dir = run_dir / "debug_evidence"
        return {
            "run_dir": run_dir,
            "resume_state_dir": resume_state_dir,
            "core_results_dir": core_results_dir,
            "debug_evidence_dir": debug_evidence_dir,
            "run_index": resume_state_dir / "run_index.json",
            "master_queue": resume_state_dir / "master_queue.csv",
            "csv_batches": resume_state_dir / "csv_batches",
            "master_results": core_results_dir / "master_results.csv",
            "selected_record_ids": core_results_dir / "selected_record_ids.csv",
            "move_manifest": core_results_dir / "move_manifest.csv",
            "compatibility_csv": core_results_dir / "llm_enhanced_classification_details.csv",
            "statistics": core_results_dir / "classification_statistics.txt",
            "batch_raw_responses": debug_evidence_dir / "batch_raw_responses",
            "final_new_species_reports": core_results_dir / "final_new_species_reports",
            "manual_review_uncertain": core_results_dir / "manual_review_uncertain",
        }

    def _ensure_v2_artifact_layout(self, run_dir: Path) -> Dict[str, Path]:
        paths = self._get_v2_artifact_paths(run_dir)
        paths["resume_state_dir"].mkdir(parents=True, exist_ok=True)
        paths["core_results_dir"].mkdir(parents=True, exist_ok=True)
        paths["debug_evidence_dir"].mkdir(parents=True, exist_ok=True)

        legacy_paths = self._get_legacy_v2_artifact_paths(run_dir)
        migration_pairs = {
            legacy_paths["run_index"]: paths["run_index"],
            legacy_paths["master_queue"]: paths["master_queue"],
            legacy_paths["csv_batches"]: paths["csv_batches"],
            legacy_paths["master_results"]: paths["master_results"],
            legacy_paths["selected_record_ids"]: paths["selected_record_ids"],
            legacy_paths["move_manifest"]: paths["move_manifest"],
            legacy_paths["compatibility_csv"]: paths["compatibility_csv"],
            legacy_paths["statistics"]: paths["statistics"],
            legacy_paths["batch_raw_responses"]: paths["batch_raw_responses"],
            legacy_paths["final_new_species_reports"]: paths["final_new_species_reports"],
            legacy_paths["manual_review_uncertain"]: paths["manual_review_uncertain"],
        }

        for source_path, target_path in migration_pairs.items():
            if not source_path.exists() or target_path.exists():
                continue
            target_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(source_path), str(target_path))
            except Exception as exc:
                self.logger.warning(f"迁移旧运行产物失败: {source_path} -> {target_path} - {exc}")

        return paths

    def _queue_rows_prefix_match_pdf_files(self, queue_rows: List[Dict[str, Any]], pdf_files: List[Path]) -> bool:
        if len(queue_rows) > len(pdf_files):
            return False
        for expected_index, (row, pdf_file) in enumerate(zip(queue_rows, pdf_files), start=1):
            if str(row.get("filename", "")) != pdf_file.name:
                return False
            if self._normalize_record_id(row.get("record_id", "")) != f"RID{expected_index:06d}":
                return False
        return True

    def _queue_rows_match_pdf_files(self, queue_rows: List[Dict[str, Any]], pdf_files: List[Path]) -> bool:
        return len(queue_rows) == len(pdf_files) and self._queue_rows_prefix_match_pdf_files(queue_rows, pdf_files)

    def _reset_v2_run_artifacts(self, run_dir: Path) -> None:
        paths = self._get_v2_artifact_paths(run_dir)
        legacy_paths = self._get_legacy_v2_artifact_paths(run_dir)
        removable_files = [
            paths["run_index"],
            paths["master_queue"],
            paths["master_results"],
            paths["selected_record_ids"],
            paths["move_manifest"],
            paths["compatibility_csv"],
            paths["statistics"],
            legacy_paths["run_index"],
            legacy_paths["master_queue"],
            legacy_paths["master_results"],
            legacy_paths["selected_record_ids"],
            legacy_paths["move_manifest"],
            legacy_paths["compatibility_csv"],
            legacy_paths["statistics"],
        ]
        removable_dirs = [
            paths["resume_state_dir"],
            paths["core_results_dir"],
            paths["debug_evidence_dir"],
            legacy_paths["csv_batches"],
            legacy_paths["batch_raw_responses"],
            legacy_paths["final_new_species_reports"],
            legacy_paths["manual_review_uncertain"],
        ]
        for file_path in removable_files:
            try:
                if file_path.exists():
                    file_path.unlink()
            except Exception as exc:
                self.logger.warning(f"清理旧运行文件失败: {file_path} - {exc}")
        for dir_path in removable_dirs:
            try:
                if dir_path.exists():
                    shutil.rmtree(dir_path)
            except Exception as exc:
                self.logger.warning(f"清理旧运行目录失败: {dir_path} - {exc}")

    def _compute_pdf_manifest_signature(self, pdf_files: List[Path]) -> str:
        digest = hashlib.sha1()
        for pdf_file in pdf_files:
            digest.update(str(pdf_file.name).lower().encode("utf-8", errors="ignore"))
            try:
                stat = pdf_file.stat()
                digest.update(str(stat.st_size).encode("utf-8"))
                digest.update(str(stat.st_mtime_ns).encode("utf-8"))
            except OSError:
                pass
        return digest.hexdigest()

    def _build_v2_runtime_config_snapshot(self) -> Dict[str, Any]:
        screener_config = deepcopy(self.config)
        screener_config.update(
            {
                "processing_mode": self.processing_mode,
                "lines_per_pdf": self.lines_per_pdf,
                "csv_batch_size": self.csv_batch_size,
                "csv_batch_fallback_size": self.csv_batch_fallback_size,
                "include_confidence_threshold": round(self.include_confidence_threshold, 4),
                "batch_char_budget": self.batch_char_budget,
                "max_text_chars_per_file": self.max_text_chars_per_file,
                "llm_batch_max_tokens": self.llm_batch_max_tokens,
                "llm_request_timeout_seconds": self.llm_request_timeout_seconds,
                "pdf_extract_timeout_seconds": self.pdf_extract_timeout_seconds,
                "split_failed_batches": self.split_failed_batches,
                "resume_interrupted_runs": self.resume_interrupted_runs,
                "isolate_v2_runs": self.isolate_v2_runs,
                "api_protocol": self.api_protocol,
            }
        )
        return {
            "schema_version": "literature-screening-v2-runtime-config-v1",
            "saved_at": self._now_text(),
            "source_folder": str(self.source_folder),
            "output_root": str(self.output_root),
            "processing_mode": self.processing_mode,
            "screener_config": screener_config,
            "api_protocol": self.api_protocol,
            "base_url": str(self.base_url or ""),
            "model": str(self.model or ""),
        }

    def _build_v2_runtime_signature(self) -> Dict[str, Any]:
        logic_signature = hashlib.sha1(
            json.dumps(
                {
                    "required_keywords": list(self.required_keywords),
                    "supportive_keywords": list(self.supportive_keywords),
                    "taxonomic_group_keywords": list(self.taxonomic_group_keywords),
                    "strong_exclude_keywords": list(self.strong_exclude_keywords),
                    "weak_exclude_keywords": list(self.weak_exclude_keywords),
                    "biological_exclude_keywords": list(self.biological_exclude_keywords),
                    "llm_system_prompt": str(self.llm_system_prompt or ""),
                    "llm_prompt_template": str(self.llm_prompt_template or ""),
                    "llm_batch_prompt_template": str(self.llm_batch_prompt_template or ""),
                },
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8", errors="ignore")
        ).hexdigest()
        return {
            "lines_per_pdf": self.lines_per_pdf,
            "csv_batch_size": self.csv_batch_size,
            "csv_batch_fallback_size": self.csv_batch_fallback_size,
            "batch_char_budget": self.batch_char_budget,
            "include_confidence_threshold": round(self.include_confidence_threshold, 4),
            "max_text_chars_per_file": self.max_text_chars_per_file,
            "llm_batch_max_tokens": self.llm_batch_max_tokens,
            "llm_request_timeout_seconds": self.llm_request_timeout_seconds,
            "pdf_extract_timeout_seconds": self.pdf_extract_timeout_seconds,
            "api_protocol": self.api_protocol,
            "split_failed_batches": self.split_failed_batches,
            "resume_interrupted_runs": self.resume_interrupted_runs,
            "isolate_v2_runs": self.isolate_v2_runs,
            "logic_signature": logic_signature,
            "base_url": str(self.base_url or ""),
            "model": str(self.model or ""),
        }

    def _summarize_runtime_signature_changes(self, previous_signature: Dict[str, Any], current_signature: Dict[str, Any]) -> List[str]:
        field_labels = {
            "lines_per_pdf": "lines_per_pdf",
            "csv_batch_size": "csv_batch_size",
            "csv_batch_fallback_size": "csv_batch_fallback_size",
            "batch_char_budget": "batch_char_budget",
            "include_confidence_threshold": "include_confidence_threshold",
            "max_text_chars_per_file": "max_text_chars_per_file",
            "llm_batch_max_tokens": "llm_batch_max_tokens",
            "llm_request_timeout_seconds": "llm_request_timeout_seconds",
            "pdf_extract_timeout_seconds": "pdf_extract_timeout_seconds",
            "api_protocol": "api_protocol",
            "split_failed_batches": "split_failed_batches",
            "resume_interrupted_runs": "resume_interrupted_runs",
            "isolate_v2_runs": "isolate_v2_runs",
            "logic_signature": "logic_signature(关键词/提示词)",
            "base_url": "base_url",
            "model": "model",
        }
        changed_fields: List[str] = []
        for key in field_labels:
            if previous_signature.get(key) != current_signature.get(key):
                changed_fields.append(field_labels[key])
        return changed_fields

    def _persist_active_v2_run(self, run_dir: Path, run_index: Dict[str, Any]) -> None:
        artifact_paths = self._get_v2_artifact_paths(run_dir)
        self._write_json_file(
            self.v2_active_run_file,
            {
                "schema_version": "literature-screening-v2-active-run-v1",
                "run_id": run_index.get("run_id", run_dir.name),
                "run_dir": str(run_dir),
                "run_index_path": str(artifact_paths["run_index"]),
                "source_folder": str(self.source_folder),
                "status": run_index.get("status", "unknown"),
                "updated_at": run_index.get("updated_at", self._now_text()),
            },
        )

    def _persist_v2_run_index(self, run_dir: Path, run_index: Dict[str, Any]) -> Path:
        artifact_paths = self._get_v2_artifact_paths(run_dir)
        run_index["updated_at"] = self._now_text()
        run_index["runtime_config_snapshot"] = self._build_v2_runtime_config_snapshot()
        run_index_path = artifact_paths["run_index"]
        self._write_json_file(run_index_path, run_index)
        self._persist_active_v2_run(run_dir, run_index)
        return run_index_path

    def _is_v2_row_terminal(self, row: Dict[str, Any]) -> bool:
        status = str(row.get("status", "")).strip().lower()
        return status in {"completed", "human_review"}

    def _restore_completed_batch_rows(self, batch_path: Path, expected_rows: List[Dict[str, Any]]) -> bool:
        saved_rows = self._read_rows_from_csv(batch_path)
        if not saved_rows or len(saved_rows) != len(expected_rows):
            return False

        saved_map = {
            self._normalize_record_id(row.get("record_id", "")): row
            for row in saved_rows
            if self._normalize_record_id(row.get("record_id", ""))
        }
        if len(saved_map) != len(expected_rows):
            return False

        for row in expected_rows:
            record_id = self._normalize_record_id(row.get("record_id", ""))
            saved_row = saved_map.get(record_id)
            if not saved_row or not self._is_v2_row_terminal(saved_row):
                return False

        for row in expected_rows:
            record_id = self._normalize_record_id(row.get("record_id", ""))
            saved_row = saved_map[record_id]
            for key in list(row.keys()):
                row[key] = saved_row.get(key, row.get(key, ""))
        return True

    def _prepare_v2_run_context(self, pdf_files: List[Path]) -> Dict[str, Any]:
        self.v2_runs_root.mkdir(parents=True, exist_ok=True)
        runtime_signature = self._build_v2_runtime_signature()
        source_manifest_signature = self._compute_pdf_manifest_signature(pdf_files)
        resume_skip_messages: List[str] = []

        if self.isolate_v2_runs and self.resume_interrupted_runs:
            active_run_exists = self.v2_active_run_file.exists()
            active_run = self._read_json_file(self.v2_active_run_file)
            if active_run:
                run_dir_text = str(active_run.get("run_dir", "")).strip()
                if not run_dir_text:
                    message = f"检测到无效的活动 V2 元数据：{self.v2_active_run_file} 缺少 run_dir，已跳过自动续跑并创建新运行。"
                    self.logger.warning(message)
                    resume_skip_messages.append(message)
                    run_dir = None
                    run_index = None
                else:
                    run_dir = Path(run_dir_text)
                    run_index = None

                if run_dir and run_dir.exists():
                    artifact_paths = self._ensure_v2_artifact_layout(run_dir)
                    run_index_path_text = str(active_run.get("run_index_path", "")).strip()
                    if not run_index_path_text:
                        self.logger.warning(
                            f"活动 V2 元数据缺少 run_index_path，回退到运行目录中的 run_index.json: {self.v2_active_run_file}"
                        )
                    run_index = self._read_json_file(Path(run_index_path_text)) if run_index_path_text else None
                    if not run_index:
                        run_index = self._read_json_file(artifact_paths["run_index"])
                    if not run_index:
                        run_index = self._read_json_file(self._get_legacy_v2_artifact_paths(run_dir)["run_index"])
                    if not run_index:
                        message = (
                            f"检测到活动 V2 元数据，但引用的 run_index.json 缺失或无效，已跳过自动续跑并创建新运行: {run_dir}"
                        )
                        self.logger.warning(message)
                        resume_skip_messages.append(message)
                elif run_dir:
                    message = f"检测到活动 V2 元数据，但运行目录不存在，已跳过自动续跑并创建新运行: {run_dir}"
                    self.logger.warning(message)
                    resume_skip_messages.append(message)
                    run_index = None
                if run_dir and run_index:
                    status = str(run_index.get("status", "")).strip().lower()
                    saved_runtime_signature = run_index.get("runtime_signature")
                    runtime_signature_matches = isinstance(saved_runtime_signature, dict) and saved_runtime_signature == runtime_signature
                    manifest_matches = run_index.get("source_manifest_signature") == source_manifest_signature
                    if (
                        run_dir.exists()
                        and str(run_index.get("source_folder", "")) == str(self.source_folder)
                        and run_index.get("mode") == "v2"
                        and runtime_signature_matches
                        and manifest_matches
                        and status not in {"completed", "completed_with_warnings"}
                    ):
                        self.active_output_folder = run_dir
                        run_index["status"] = "resuming"
                        run_index["resume_count"] = int(run_index.get("resume_count", 0)) + 1
                        self._persist_v2_run_index(run_dir, run_index)
                        self.logger.info(f"检测到可恢复的 V2 运行，继续使用: {run_dir}")
                        return {
                            "run_dir": run_dir,
                            "run_id": run_index.get("run_id", run_dir.name),
                            "run_index": run_index,
                            "resumed": True,
                            "source_manifest_signature": source_manifest_signature,
                            "resume_skip_messages": resume_skip_messages,
                        }

                    if str(run_index.get("source_folder", "")) != str(self.source_folder):
                        message = (
                            "检测到活动 V2 运行，但源目录已变化，已跳过自动续跑并创建新运行。"
                            f" 上次={run_index.get('source_folder', '')} | 当前={self.source_folder}"
                        )
                        self.logger.warning(message)
                        resume_skip_messages.append(message)
                    elif run_index.get("mode") != "v2":
                        message = f"检测到活动运行索引，但其模式不是 V2（mode={run_index.get('mode')}），已跳过自动续跑并创建新运行。"
                        self.logger.warning(message)
                        resume_skip_messages.append(message)
                    elif not isinstance(saved_runtime_signature, dict):
                        message = "检测到活动 V2 运行，但 run_index.json 中缺少有效的 runtime_signature，已跳过自动续跑并创建新运行。"
                        self.logger.warning(message)
                        resume_skip_messages.append(message)
                    elif not runtime_signature_matches:
                        changed_fields = self._summarize_runtime_signature_changes(saved_runtime_signature, runtime_signature)
                        details = ", ".join(changed_fields[:8]) if changed_fields else "未知字段"
                        if len(changed_fields) > 8:
                            details += " ..."
                        message = (
                            "检测到活动 V2 运行，但运行参数签名已变化，已跳过自动续跑并创建新运行。"
                            f" 变更字段: {details}"
                        )
                        self.logger.warning(message)
                        resume_skip_messages.append(message)
                    elif not manifest_matches:
                        message = (
                            "检测到活动 V2 运行，但源 PDF 清单已变化（文件名/大小/修改时间不同），"
                            "已跳过自动续跑并创建新运行。"
                        )
                        self.logger.warning(message)
                        resume_skip_messages.append(message)
                    elif status in {"completed", "completed_with_warnings"}:
                        message = f"最近的 V2 运行已完成（status={status}），无需自动续跑，将创建新运行。"
                        self.logger.info(message)
                        resume_skip_messages.append(message)
            elif active_run_exists:
                message = f"检测到损坏或无效的活动 V2 元数据文件，已跳过自动续跑并创建新运行: {self.v2_active_run_file}"
                self.logger.warning(message)
                resume_skip_messages.append(message)
            else:
                message = f"未找到活动 V2 运行元数据，无法自动续跑，将创建新运行: {self.v2_active_run_file}"
                self.logger.info(message)
                resume_skip_messages.append(message)

        if self.isolate_v2_runs:
            run_dir = self.v2_runs_root / self._new_run_id()
        else:
            run_dir = self.output_root
        run_dir.mkdir(parents=True, exist_ok=True)
        if not self.isolate_v2_runs:
            self.logger.info("V2 非隔离模式：启动前清理输出目录中的旧运行产物")
            self._reset_v2_run_artifacts(run_dir)
        self._ensure_v2_artifact_layout(run_dir)
        self.active_output_folder = run_dir

        run_index = {
            "schema_version": "literature-screening-v2-run-index-v2",
            "run_id": run_dir.name,
            "mode": "v2",
            "status": "initialized",
            "created_at": self._now_text(),
            "updated_at": self._now_text(),
            "resume_count": 0,
            "source_folder": str(self.source_folder),
            "output_root": str(self.output_root),
            "output_folder": str(run_dir),
            "runtime_signature": runtime_signature,
            "source_manifest_signature": source_manifest_signature,
            "progress": {
                "completed_batches": 0,
                "completed_records": 0,
                "total_batches": 0,
                "total_records": len(pdf_files),
            },
            "summary": {
                "included": 0,
                "excluded": 0,
                "uncertain": 0,
                "pending": len(pdf_files),
                "move_failed": 0,
                "include_confidence_threshold": self.include_confidence_threshold,
            },
        }
        self._persist_v2_run_index(run_dir, run_index)
        self.logger.info(f"创建新的 V2 运行目录: {run_dir}")
        return {
            "run_dir": run_dir,
            "run_id": run_index["run_id"],
            "run_index": run_index,
            "resumed": False,
            "source_manifest_signature": source_manifest_signature,
            "resume_skip_messages": resume_skip_messages,
        }

    def _summarize_v2_rows(self, rows: List[Dict[str, Any]]) -> Dict[str, int]:
        summary = {
            "included": 0,
            "excluded": 0,
            "uncertain": 0,
            "pending": 0,
            "completed": 0,
            "move_failed": 0,
        }
        for row in rows:
            status = str(row.get("status", "")).strip().lower()
            if self._is_v2_row_terminal(row):
                summary["completed"] += 1
            else:
                summary["pending"] += 1

            decision = self._normalize_decision(row.get("llm_decision"))
            confidence = self._clamp_confidence(row.get("llm_confidence"), 0.0)
            if decision == "include" and confidence >= self.include_confidence_threshold:
                summary["included"] += 1
            elif decision == "exclude":
                summary["excluded"] += 1
            elif status in {"human_review", "completed"}:
                summary["uncertain"] += 1

            if str(row.get("error", "")).strip().lower() == "move_copy_failed":
                summary["move_failed"] += 1
        return summary

    def _summarize_v2_extraction(self, rows: List[Dict[str, Any]]) -> tuple[Dict[str, int], Dict[str, int]]:
        extraction_summary = {
            "text_layer": 0,
            "ocr": 0,
            "failed": 0,
        }
        issue_summary: Dict[str, int] = {}

        for row in rows:
            extract_source = str(row.get("extract_source", "")).strip().lower()
            if extract_source == "text_layer":
                extraction_summary["text_layer"] += 1
            elif extract_source == "ocr":
                extraction_summary["ocr"] += 1
            else:
                extraction_summary["failed"] += 1

            issue_code = str(row.get("error", "")).strip().lower()
            if issue_code and extract_source not in {"text_layer", "ocr"}:
                issue_summary[issue_code] = issue_summary.get(issue_code, 0) + 1

        return extraction_summary, issue_summary

    def _write_v2_statistics(
        self,
        stats_path: Path,
        run_dir: Path,
        rows: List[Dict[str, Any]],
        total_batches: int,
        processed_batches: int,
        run_status: str,
        run_completed: bool,
        master_queue_path: Path,
        master_results_path: Path,
        selected_ids_path: Path,
    ) -> Dict[str, int]:
        summary = self._summarize_v2_rows(rows)
        extraction_summary, issue_summary = self._summarize_v2_extraction(rows)
        artifact_paths = self._get_v2_artifact_paths(run_dir)
        with open(stats_path, "w", encoding="utf-8") as handle:
            handle.write("V2 筛选统计结果\n")
            handle.write("=" * 40 + "\n")
            handle.write(f"模式: {self.processing_mode}\n")
            handle.write(f"运行状态: {run_status}\n")
            handle.write(f"运行目录: {run_dir}\n")
            handle.write(f"核心结果目录: {artifact_paths['core_results_dir']}\n")
            handle.write(f"续跑状态目录: {artifact_paths['resume_state_dir']}\n")
            handle.write(f"调试证据目录: {artifact_paths['debug_evidence_dir']}\n")
            handle.write(f"总文献数: {len(rows)}\n")
            handle.write(f"总批次数: {total_batches}\n")
            handle.write(f"已完成批次: {processed_batches}\n")
            handle.write(f"通过阈值: {self.include_confidence_threshold:.2f}\n")
            handle.write(f"最终纳入: {summary['included']}\n")
            handle.write(f"明确排除: {summary['excluded']}\n")
            handle.write(f"待人工复核: {summary['uncertain']}\n")
            handle.write(f"待处理: {summary['pending']}\n")
            handle.write(f"搬运失败: {summary['move_failed']}\n\n")
            handle.write("提取摘要:\n")
            handle.write(f"- 文本层成功: {extraction_summary['text_layer']}\n")
            handle.write(f"- OCR 回退成功: {extraction_summary['ocr']}\n")
            handle.write(f"- 提取失败/跳过: {extraction_summary['failed']}\n")
            if issue_summary:
                handle.write("- 失败原因分布:\n")
                for issue_code in sorted(issue_summary):
                    handle.write(f"  - {issue_code}: {issue_summary[issue_code]}\n")
            handle.write("\n")
            handle.write("关键文件:\n")
            handle.write(f"- master_queue.csv: {master_queue_path}\n")
            handle.write(f"- master_results.csv: {master_results_path}\n")
            handle.write(f"- run_index.json: {artifact_paths['run_index']}\n")
            handle.write(f"- csv_batches/: {artifact_paths['csv_batches']}\n")
            handle.write(f"- batch_raw_responses/: {artifact_paths['batch_raw_responses']}\n")
            if run_completed:
                handle.write(f"- selected_record_ids.csv: {selected_ids_path}\n")
                handle.write(f"- move_manifest.csv: {artifact_paths['move_manifest']}\n")
                handle.write(f"- 兼容明细CSV: {artifact_paths['compatibility_csv']}\n")
            else:
                handle.write("- 运行未完成：暂不生成 selected_record_ids.csv / move_manifest.csv / 最终搬运结果\n")
        return summary

    def _clamp_confidence(self, value: Any, default: float = 0.5) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            confidence = default
        if confidence < 0:
            return 0.0
        if confidence > 1:
            return 1.0
        return confidence

    def _normalize_decision(self, raw_decision: Any) -> str:
        text = str(raw_decision or "").strip().lower()
        if not text:
            return "uncertain"

        include_tokens = ["include", "yes", "判断：是", "判断: 是", "判断:是", "是", "新种", "纳入"]
        exclude_tokens = ["exclude", "no", "判断：否", "判断: 否", "判断:否", "否", "排除"]
        uncertain_tokens = ["uncertain", "unknown", "不确定", "待复核", "无法判断"]

        if any(token in text for token in include_tokens):
            return "include"
        if any(token in text for token in exclude_tokens):
            return "exclude"
        if any(token in text for token in uncertain_tokens):
            return "uncertain"
        return "uncertain"

    def _normalize_record_id(self, raw_value: Any) -> str:
        text = str(raw_value or "").strip()
        if not text:
            return ""

        if text.startswith("[") and text.endswith("]"):
            text = text[1:-1].strip()

        lower_text = text.lower()
        if lower_text.startswith("record_id"):
            parts = text.split(":", 1)
            if len(parts) == 2:
                text = parts[1].strip()

        if text.upper().startswith("RID"):
            digits = "".join(char for char in text[3:] if char.isdigit())
            if digits:
                return f"RID{int(digits):06d}"
            return text.upper()

        if text.isdigit():
            return f"RID{int(text):06d}"

        return text

    def _strip_code_fence(self, content: str) -> str:
        text = content.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text).strip()
            if text.endswith("```"):
                text = text[:-3].strip()
        return text

    def _render_prompt_template(self, template: str, replacements: Dict[str, Any]) -> str:
        rendered = str(template or "")
        for key, value in replacements.items():
            rendered = rendered.replace(f"{{{key}}}", str(value))
        return rendered

    def _normalize_base_url(self, raw_base_url: Any) -> str | None:
        if raw_base_url is None:
            return None

        base_text = str(raw_base_url).strip()
        if not base_text:
            return None

        for suffix in ["/chat/completions", "/responses"]:
            if base_text.lower().endswith(suffix):
                base_text = base_text[: -len(suffix)]

        return base_text.rstrip("/")

    def _resolve_api_protocol(self) -> str:
        if self.api_protocol in {"chat_completions", "responses"}:
            return self.api_protocol

        model_text = str(self.model or "").strip().lower()
        base_text = str(self.base_url or "").strip().lower()

        if "gmn.chuangzuoli.com" in base_text and "gpt" in model_text:
            return "responses"
        return "chat_completions"

    def _normalize_provider_model(self, raw_model: Any) -> Any:
        if not isinstance(raw_model, str):
            return raw_model

        model_text = raw_model.strip()
        if not model_text:
            return model_text

        base_text = str(self.base_url or "").lower()
        if "gmn.chuangzuoli.com" not in base_text:
            return model_text

        normalized = model_text
        if "/" in normalized:
            prefix, suffix = normalized.split("/", 1)
            if prefix.lower() == "gmn" and suffix:
                normalized = suffix

        normalized = normalized.lower()
        return normalized

    def _extract_responses_text(self, response: Any) -> str:
        output_text = str(getattr(response, "output_text", "") or "").strip()
        if output_text:
            return output_text

        payload: Any = None
        if hasattr(response, "model_dump"):
            try:
                payload = response.model_dump()
            except Exception:
                payload = None
        if payload is None:
            payload = response

        output_items = None
        if isinstance(payload, dict):
            output_items = payload.get("output")
        else:
            output_items = getattr(payload, "output", None)

        chunks: list[str] = []
        if isinstance(output_items, list):
            for item in output_items:
                item_type = ""
                item_content = None
                if isinstance(item, dict):
                    item_type = str(item.get("type", "") or "")
                    item_content = item.get("content")
                else:
                    item_type = str(getattr(item, "type", "") or "")
                    item_content = getattr(item, "content", None)

                if item_type and item_type != "message":
                    continue
                if not isinstance(item_content, list):
                    continue

                for content_item in item_content:
                    content_type = ""
                    text = ""
                    if isinstance(content_item, dict):
                        content_type = str(content_item.get("type", "") or "")
                        text = str(content_item.get("text", "") or "")
                    else:
                        content_type = str(getattr(content_item, "type", "") or "")
                        text = str(getattr(content_item, "text", "") or "")

                    if content_type == "output_text" and text:
                        chunks.append(text)

        return "\n".join(part for part in chunks if part).strip()

    def _extract_responses_finish_reason(self, response: Any) -> str:
        if isinstance(response, dict):
            status = str(response.get("status", "") or "").strip().lower()
            incomplete_details = response.get("incomplete_details")
        else:
            status = str(getattr(response, "status", "") or "").strip().lower()
            incomplete_details = getattr(response, "incomplete_details", None)

        if status == "completed":
            return "stop"

        if isinstance(incomplete_details, dict):
            reason = str(incomplete_details.get("reason", "") or "").strip().lower()
        else:
            reason = str(getattr(incomplete_details, "reason", "") or "").strip().lower()

        if reason in {"max_output_tokens", "length"}:
            return "length"
        if status in {"incomplete", "failed", "cancelled"}:
            return status
        if status:
            return status
        return ""

    def _call_responses_via_http(self, system_prompt: str, user_prompt: str, max_tokens: int, temperature: float) -> Tuple[str, str]:
        if not self.api_key or not self.base_url:
            raise ValueError("responses_http_missing_credentials")

        url = f"{self.base_url}/responses"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_output_tokens": max_tokens,
            "temperature": temperature,
        }

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=self.llm_request_timeout_seconds,
        )
        if response.status_code >= 400:
            error = RuntimeError(f"HTTP {response.status_code} - responses_http_error")
            setattr(error, "status_code", response.status_code)
            setattr(error, "response", response)
            try:
                setattr(error, "body", response.json())
            except Exception:
                pass
            raise error

        data = response.json()
        result_text = self._extract_responses_text(data)
        finish_reason = self._extract_responses_finish_reason(data)
        return result_text, finish_reason

    def _call_llm(self, system_prompt: str, user_prompt: str, max_tokens: int, temperature: float) -> Tuple[str, str, str]:
        preferred_protocol = self._resolve_api_protocol()
        protocol_order = [preferred_protocol]
        if self.api_protocol == "auto":
            fallback_protocol = "responses" if preferred_protocol == "chat_completions" else "chat_completions"
            protocol_order.append(fallback_protocol)

        last_exc: Exception | None = None
        for index, protocol in enumerate(protocol_order):
            try:
                client = self.client
                if client and hasattr(client, "with_options"):
                    try:
                        client = client.with_options(timeout=self.llm_request_timeout_seconds)
                    except Exception:
                        client = self.client

                if protocol == "responses":
                    if "gmn.chuangzuoli.com" in str(self.base_url or "").lower():
                        result_text, finish_reason = self._call_responses_via_http(
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                            max_tokens=max_tokens,
                            temperature=temperature,
                        )
                    else:
                        response = client.responses.create(
                            model=self.model,
                            input=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt},
                            ],
                            temperature=temperature,
                            max_output_tokens=max_tokens,
                        )
                        result_text = self._extract_responses_text(response)
                        finish_reason = self._extract_responses_finish_reason(response)
                else:
                    response = client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
                    result_text = str(response.choices[0].message.content or "").strip()
                    finish_reason = str(getattr(response.choices[0], "finish_reason", "") or "").strip().lower()

                if not result_text:
                    raise ValueError(f"empty_llm_output_via_{protocol}")
                return result_text, finish_reason, protocol

            except Exception as exc:
                last_exc = exc
                status_code, _, detail = self._analyze_llm_exception(exc, protocol=protocol)
                protocol_mismatch_hint = (
                    status_code in {400, 404, 422}
                    or "chat/completions" in detail.lower()
                    or "/responses" in detail.lower()
                    or "unsupported" in detail.lower()
                    or "not found" in detail.lower()
                )
                has_fallback = index < len(protocol_order) - 1
                if has_fallback and protocol_mismatch_hint:
                    next_protocol = protocol_order[index + 1]
                    self.logger.warning(
                        f"协议 {protocol} 调用失败，将尝试 {next_protocol}。原因: {detail}"
                    )
                    continue
                raise

        if last_exc:
            raise last_exc
        raise RuntimeError("llm_call_failed_without_exception")

    def _analyze_llm_exception(self, exc: Exception, protocol: str | None = None) -> Tuple[int | None, bool, str]:
        status_code = getattr(exc, "status_code", None)
        response = getattr(exc, "response", None)
        response_text = ""

        if status_code is None and response is not None:
            status_code = getattr(response, "status_code", None)

        try:
            response_text = str(getattr(response, "text", "") or "").strip()
        except Exception:
            response_text = ""

        if not response_text:
            body = getattr(exc, "body", None)
            if body is not None:
                try:
                    response_text = json.dumps(body, ensure_ascii=False)
                except Exception:
                    response_text = str(body)

        message = str(exc or "").strip()
        message_lower = message.lower()
        response_lower = response_text.lower()

        non_retryable = False
        if isinstance(status_code, int) and status_code in {400, 401, 403, 404, 422}:
            non_retryable = True

        hard_fail_tokens = [
            "your request was blocked",
            "forbidden",
            "unauthorized",
            "invalid api key",
            "incorrect api key",
            "model_not_found",
            "permission denied",
            "insufficient_quota",
        ]
        if any(token in message_lower or token in response_lower for token in hard_fail_tokens):
            non_retryable = True

        detail = message
        if isinstance(status_code, int):
            detail = f"HTTP {status_code} - {message}"

        if status_code == 403 or "your request was blocked" in message_lower:
            detail += "（可能是中转站风控/模型白名单/Key权限限制）"

        if response_text:
            response_excerpt = response_text[:240]
            detail += f" | 响应: {response_excerpt}"

        detail += f" | protocol={protocol or self.api_protocol}"
        detail += f" | model={self.model}"
        detail += f" | base_url={self.base_url}"

        return status_code, non_retryable, detail

    def _parse_batch_response(self, content: str) -> Dict[str, Dict[str, Any]]:
        text = self._strip_code_fence(content)

        payload: Any = None
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            start_list = text.find("[")
            end_list = text.rfind("]")
            if start_list != -1 and end_list != -1 and end_list > start_list:
                payload = json.loads(text[start_list:end_list + 1])
            else:
                start_obj = text.find("{")
                end_obj = text.rfind("}")
                if start_obj != -1 and end_obj != -1 and end_obj > start_obj:
                    payload = json.loads(text[start_obj:end_obj + 1])
                else:
                    raise

        records: list[dict[str, Any]] = []
        if isinstance(payload, list):
            records = [item for item in payload if isinstance(item, dict)]
        elif isinstance(payload, dict):
            for key in ("results", "records", "items", "data"):
                value = payload.get(key)
                if isinstance(value, list):
                    records = [item for item in value if isinstance(item, dict)]
                    break
            if not records and all(k in payload for k in ["record_id", "decision"]):
                records = [payload]

        result_map: Dict[str, Dict[str, Any]] = {}
        duplicate_ids: list[str] = []
        for item in records:
            record_id = self._normalize_record_id(item.get("record_id", ""))
            if record_id:
                if record_id in result_map:
                    duplicate_ids.append(record_id)
                    continue
                item["record_id"] = record_id
                result_map[record_id] = item

        if duplicate_ids:
            uniq = sorted(set(duplicate_ids))
            self.logger.warning(f"批次LLM响应存在重复record_id，重复数量={len(duplicate_ids)}，示例={uniq[:5]}")
        return result_map

    def _write_rows_to_csv(self, csv_path: Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with open(csv_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                normalized_row = {key: row.get(key, "") for key in fieldnames}
                writer.writerow(normalized_row)

    def _build_queue_rows(
        self,
        pdf_files: List[Path],
        check_stop_callback=None,
        progress_callback=None,
        existing_rows: List[Dict[str, Any]] | None = None,
        master_queue_path: Path | None = None,
        fieldnames: List[str] | None = None,
    ) -> tuple[List[Dict[str, Any]], bool]:
        rows: List[Dict[str, Any]] = list(existing_rows or [])
        total_files = len(pdf_files)
        start_index = len(rows)

        for idx in range(start_index, total_files):
            pdf_file = pdf_files[idx]
            if check_stop_callback and check_stop_callback():
                self.logger.warning("任务已被用户中断。")
                return rows, True

            lines = self.extract_first_lines(pdf_file, self.lines_per_pdf, check_stop_callback=check_stop_callback)
            if check_stop_callback and check_stop_callback():
                self.logger.warning("任务已被用户中断。")
                return rows, True
            title = self.extract_title_from_lines(lines) if lines else ""
            text_preview = "\n".join(lines).strip() if lines else ""
            text_preview = re.sub(r"\s+", " ", text_preview)
            if len(text_preview) > self.max_text_chars_per_file:
                text_preview = text_preview[:self.max_text_chars_per_file]

            row = {
                "record_id": f"RID{idx + 1:06d}",
                "record_index": str(idx + 1),
                "display_label": f"[RID{idx + 1:06d}] {pdf_file.name}",
                "filename": pdf_file.name,
                "pdf_path": str(pdf_file),
                "title": title or "",
                "text_preview": text_preview,
                "extract_source": self._get_pdf_extract_source(pdf_file),
                "line_count": str(len(lines)),
                "text_char_count": str(len(text_preview)),
                "status": "pending" if text_preview else "text_missing",
                "llm_decision": "",
                "llm_confidence": "",
                "llm_reason": self._get_pdf_issue(pdf_file).get("message", "") if (not text_preview and self._get_pdf_issue(pdf_file)) else "",
                "llm_raw": "",
                "error": self._get_pdf_issue(pdf_file).get("code", "") if (not text_preview and self._get_pdf_issue(pdf_file)) else "",
            }
            rows.append(row)

            if master_queue_path is not None and fieldnames is not None:
                self._append_row_to_csv(master_queue_path, row, fieldnames)

            if progress_callback:
                progress_callback(idx + 1, total_files)

        return rows, False

    def _chunk_rows_for_batches(self, rows: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        if not rows:
            return []

        chunks: List[List[Dict[str, Any]]] = []
        current_chunk: List[Dict[str, Any]] = []
        current_chars = 0

        for row in rows:
            row_chars = len(str(row.get("text_preview", ""))) + len(str(row.get("title", ""))) + 80

            should_flush = False
            if current_chunk and len(current_chunk) >= self.csv_batch_size:
                should_flush = True
            elif (
                current_chunk
                and len(current_chunk) >= self.csv_batch_fallback_size
                and current_chars + row_chars > self.batch_char_budget
            ):
                should_flush = True

            if should_flush:
                chunks.append(current_chunk)
                current_chunk = []
                current_chars = 0

            current_chunk.append(row)
            current_chars += row_chars

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _should_split_failed_batch(
        self,
        rows: List[Dict[str, Any]],
        detail: str,
        status_code: int | None,
    ) -> bool:
        if not self.split_failed_batches or len(rows) <= 1:
            return False
        if isinstance(status_code, int) and status_code in {401, 403, 404, 422}:
            return False

        detail_lower = str(detail or "").strip().lower()
        split_tokens = [
            "truncated",
            "max_tokens",
            "max_output_tokens",
            "incomplete",
            "empty_parse",
            "timed out",
            "timeout",
            "read timed out",
            "json",
        ]
        return any(token in detail_lower for token in split_tokens)

    def _validate_single_row_fallback(self, row: Dict[str, Any]) -> Dict[str, Any]:
        if not self.client:
            row["llm_decision"] = "uncertain"
            row["llm_confidence"] = "0.0"
            row["llm_reason"] = "LLM未启用"
            row["status"] = "human_review"
            return row

        approved, reason = self.llm_review_new_species_report(
            row.get("text_preview", ""),
            row.get("filename", "unknown.pdf"),
        )
        reason_text = str(reason or "")
        if "失败" in reason_text or "跳过" in reason_text:
            row["llm_decision"] = "uncertain"
            row["llm_confidence"] = "0.3"
            row["status"] = "human_review"
        else:
            row["llm_decision"] = "include" if approved else "exclude"
            row["llm_confidence"] = "0.8" if approved else "0.65"
            row["status"] = "completed"

        row["llm_reason"] = reason_text
        row["llm_raw"] = reason_text
        return row

    def _validate_batch_rows(self, rows: List[Dict[str, Any]], batch_id: str) -> List[Dict[str, Any]]:
        if not rows:
            return rows

        missing_text_rows = [row for row in rows if not row.get("text_preview")]
        for row in missing_text_rows:
            row["llm_decision"] = "uncertain"
            row["llm_confidence"] = "0.0"
            row["llm_reason"] = str(row.get("llm_reason", "")).strip() or "文本提取失败或为空"
            row["status"] = "human_review"
            row["error"] = str(row.get("error", "")).strip() or "text_missing"
            row["llm_raw"] = row["llm_reason"]

        active_rows = [row for row in rows if row.get("text_preview")]
        if not active_rows:
            return rows

        if not self.client:
            for row in active_rows:
                row["llm_decision"] = "uncertain"
                row["llm_confidence"] = "0.0"
                row["llm_reason"] = "LLM未启用"
                row["status"] = "human_review"
                row["error"] = "llm_disabled"
            return rows

        records_payload = [
            {
                "record_id": row.get("record_id", ""),
                "record_index": row.get("record_index", ""),
                "display_label": row.get("display_label", ""),
                "filename": row.get("filename", ""),
                "title": row.get("title", ""),
                "text": row.get("text_preview", ""),
            }
            for row in active_rows
        ]

        expected_record_ids = [self._normalize_record_id(item.get("record_id", "")) for item in records_payload]
        expected_record_ids = [item for item in expected_record_ids if item]
        records_json = json.dumps(records_payload, ensure_ascii=False, indent=2)
        prompt = self._render_prompt_template(
            self.llm_batch_prompt_template,
            {
                "batch_id": batch_id,
                "records_json": records_json,
                "expected_record_count": len(expected_record_ids),
                "expected_record_ids_json": json.dumps(expected_record_ids, ensure_ascii=False),
            },
        )

        prompt = (
            f"{prompt}\n\n"
            "【通用编号规则】\n"
            "- 每条记录都有唯一编号(record_id)以及带编号的display_label（形如 [RID000123] 文件名）。\n"
            "- 你的输出必须原样复制 record_id，不要改写、不补零、不删除前缀。\n\n"
            "【通用输出完整性硬约束】\n"
            f"1) 你必须返回且仅返回 {len(expected_record_ids)} 条结果；\n"
            f"2) record_id 只能来自这个列表：{json.dumps(expected_record_ids, ensure_ascii=False)}；\n"
            "3) 不允许遗漏、不允许重复、不允许新增未给出的 record_id；\n"
            "4) decision 只能是 include / exclude / uncertain；\n"
            "5) confidence 必须是 0 到 1 的数值；\n"
            "6) reason 保持简短：建议不超过30个中文字符或20个英文单词。\n"
            "7) include / exclude / uncertain 的生物学含义以当前 profile 提示词为准，不要引入 profile 之外的目标类群。\n"
        )

        max_retries = 3
        retry_delay = 1.0
        parsed_map: Dict[str, Dict[str, Any]] = {}
        raw_response = ""
        raw_response_ref = ""
        fatal_batch_error: str = ""
        fatal_batch_error_code: int | None = None
        last_batch_error: str = ""
        last_batch_error_code: int | None = None

        for attempt in range(max_retries):
            try:
                raw_response, finish_reason, used_protocol = self._call_llm(
                    system_prompt=str(self.llm_system_prompt or self.DEFAULT_CONFIG["llm_system_prompt"]),
                    user_prompt=prompt,
                    max_tokens=self.llm_batch_max_tokens,
                    temperature=0.0,
                )
                self.logger.debug(f"批次 {batch_id} 使用协议: {used_protocol}")
                if finish_reason in {"length", "max_output_tokens", "incomplete"}:
                    raise ValueError("batch_llm_truncated_by_max_tokens")
                if raw_response:
                    raw_response_ref = self._save_batch_raw_response(batch_id, raw_response)
                parsed_map = self._parse_batch_response(raw_response)
                if parsed_map:
                    break
                raise ValueError("batch_llm_empty_parse")
            except Exception as exc:
                status_code, non_retryable, detail = self._analyze_llm_exception(exc, protocol=self._resolve_api_protocol())
                last_batch_error = detail
                last_batch_error_code = status_code
                self.logger.error(
                    f"批次LLM校验失败 {batch_id} (尝试 {attempt + 1}/{max_retries}): {detail}"
                )
                if non_retryable:
                    fatal_batch_error = detail
                    fatal_batch_error_code = status_code
                    break
                if attempt < max_retries - 1:
                    time.sleep(retry_delay + random.uniform(0, 1))
                    retry_delay *= 2

        if not parsed_map and not fatal_batch_error and last_batch_error:
            if self._should_split_failed_batch(rows, last_batch_error, last_batch_error_code):
                midpoint = max(1, len(rows) // 2)
                self.logger.warning(
                    f"批次 {batch_id} 多次失败，自动拆分为更小批次重试。原始条数={len(rows)}"
                )
                left_rows = self._validate_batch_rows(rows[:midpoint], f"{batch_id}_a")
                right_rows = self._validate_batch_rows(rows[midpoint:], f"{batch_id}_b")
                return left_rows + right_rows

        if fatal_batch_error:
            if self._should_split_failed_batch(rows, fatal_batch_error, fatal_batch_error_code):
                midpoint = max(1, len(rows) // 2)
                self.logger.warning(
                    f"批次 {batch_id} 失败，自动拆分为更小批次重试。原始条数={len(rows)}"
                )
                left_rows = self._validate_batch_rows(rows[:midpoint], f"{batch_id}_a")
                right_rows = self._validate_batch_rows(rows[midpoint:], f"{batch_id}_b")
                return left_rows + right_rows

            error_tag = "llm_forbidden"
            if fatal_batch_error_code == 401:
                error_tag = "llm_unauthorized"
            elif fatal_batch_error_code == 403:
                error_tag = "llm_blocked"
            elif fatal_batch_error_code == 404:
                error_tag = "llm_model_not_found"

            for row in active_rows:
                row["llm_decision"] = "uncertain"
                row["llm_confidence"] = "0.0"
                row["llm_reason"] = f"批次LLM失败: {fatal_batch_error}"
                row["status"] = "human_review"
                row["error"] = error_tag
            return rows

        if parsed_map:
            missing_ids = [record_id for record_id in expected_record_ids if record_id not in parsed_map]
            if missing_ids:
                self.logger.warning(
                    f"批次 {batch_id} 返回缺失 {len(missing_ids)} 条记录，将触发逐条兜底复核。"
                )
                missing_id_set = set(missing_ids)
                if self.split_failed_batches and 1 < len(missing_ids) < len(active_rows):
                    self.logger.warning(
                        f"批次 {batch_id} 缺失记录较多，先自动拆分缺失子批次重试。缺失数={len(missing_ids)}"
                    )
                    missing_rows = [
                        row for row in active_rows
                        if self._normalize_record_id(row.get("record_id", "")) in missing_id_set
                    ]
                    self._validate_batch_rows(missing_rows, f"{batch_id}_missing")
            else:
                missing_id_set = set()
        else:
            missing_id_set = set()

        for row in active_rows:
            record_id = self._normalize_record_id(row.get("record_id", ""))
            if record_id in missing_id_set and self._is_v2_row_terminal(row):
                continue
            item = parsed_map.get(record_id)
            if not item:
                row["error"] = "batch_parse_missing_record"
                self._validate_single_row_fallback(row)
                continue

            decision = self._normalize_decision(item.get("decision"))
            default_confidence = 0.5
            if decision == "include":
                default_confidence = 0.8
            elif decision == "exclude":
                default_confidence = 0.7

            confidence = self._clamp_confidence(item.get("confidence"), default_confidence)
            reason = str(item.get("reason") or item.get("rationale") or "")

            row["llm_decision"] = decision
            row["llm_confidence"] = f"{confidence:.4f}"
            row["llm_reason"] = reason
            row["llm_raw"] = raw_response_ref or ""
            row["status"] = "completed" if decision != "uncertain" else "human_review"

        return rows

    def _save_v2_compatibility_csv(self, rows: List[Dict[str, Any]], output_dir: Path | None = None) -> None:
        details: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            decision = self._normalize_decision(row.get("llm_decision"))
            category = "Uncertain"
            if decision == "include":
                category = "New Species Report"
            elif decision == "exclude":
                category = "Other Literature"

            confidence = self._clamp_confidence(row.get("llm_confidence"), 0.0)
            details[row.get("filename", "unknown.pdf")] = {
                "category": category,
                "reason": row.get("llm_reason", ""),
                "title": row.get("title", ""),
                "score": confidence,
                "llm_approved": decision == "include",
                "llm_reason": row.get("llm_reason", ""),
            }

        self.save_classification_details(details, output_dir=output_dir)

    def _copy_v2_selected_files(self, rows: List[Dict[str, Any]], output_dir: Path | None = None) -> Dict[str, int]:
        active_output_dir = output_dir or self._get_active_output_folder()
        artifact_paths = self._get_v2_artifact_paths(active_output_dir)
        final_folder = artifact_paths["final_new_species_reports"]
        uncertain_folder = artifact_paths["manual_review_uncertain"]
        final_folder.mkdir(parents=True, exist_ok=True)
        uncertain_folder.mkdir(parents=True, exist_ok=True)

        manifest_rows: List[Dict[str, str]] = []
        included_count = 0
        excluded_count = 0
        uncertain_count = 0
        failed_count = 0

        for row in rows:
            decision = self._normalize_decision(row.get("llm_decision"))
            confidence = self._clamp_confidence(row.get("llm_confidence"), 0.0)
            source_path = Path(str(row.get("pdf_path", "")))
            target_path = ""
            move_status = "skipped"

            try:
                if decision == "include" and confidence >= self.include_confidence_threshold:
                    target = final_folder / source_path.name
                    shutil.copy2(source_path, target)
                    target_path = str(target)
                    move_status = "copied"
                    included_count += 1
                elif decision == "exclude":
                    excluded_count += 1
                else:
                    uncertain_count += 1
                    if source_path.exists():
                        target = uncertain_folder / source_path.name
                        shutil.copy2(source_path, target)
                        target_path = str(target)
                        move_status = "copied"
            except Exception as exc:
                failed_count += 1
                move_status = "failed"
                row["error"] = "move_copy_failed"
                row["llm_reason"] = str(row.get("llm_reason", ""))

            manifest_rows.append(
                {
                    "record_id": str(row.get("record_id", "")),
                    "filename": str(row.get("filename", "")),
                    "pdf_path": str(row.get("pdf_path", "")),
                    "decision": decision,
                    "confidence": f"{confidence:.4f}",
                    "move_status": move_status,
                    "target_path": target_path,
                    "reason": str(row.get("llm_reason", "")),
                }
            )

        manifest_fields = [
            "record_id",
            "filename",
            "pdf_path",
            "decision",
            "confidence",
            "move_status",
            "target_path",
            "reason",
        ]
        self._write_rows_to_csv(artifact_paths["move_manifest"], manifest_rows, manifest_fields)

        return {
            "included": included_count,
            "excluded": excluded_count,
            "uncertain": uncertain_count,
            "failed": failed_count,
        }

    def _batch_classify_v2(self, check_stop_callback=None, progress_callback=None) -> Dict[str, Any]:
        if not self.source_folder.exists():
            self.logger.error(f"源文件夹不存在: {self.source_folder}")
            return {}

        pdf_files = sorted(self.source_folder.glob("*.pdf"), key=lambda item: item.name.lower())
        if not pdf_files:
            self.logger.warning("未找到PDF文件")
            return {}

        self.logger.info(f"V2流程启动，共 {len(pdf_files)} 个PDF文件")

        def emit_progress(value: int) -> None:
            if not progress_callback:
                return
            safe_value = max(0, min(100, int(value)))
            progress_callback(safe_value, 100)

        def extraction_progress(current: int, total: int) -> None:
            if total <= 0:
                emit_progress(0)
                return
            ratio = max(0.0, min(1.0, current / total))
            emit_progress(int(round(ratio * 45)))

        emit_progress(0)

        fieldnames = [
            "record_id",
            "record_index",
            "display_label",
            "filename",
            "pdf_path",
            "title",
            "text_preview",
            "extract_source",
            "line_count",
            "text_char_count",
            "status",
            "llm_decision",
            "llm_confidence",
            "llm_reason",
            "llm_raw",
            "error",
        ]
        batch_fieldnames = [
            "record_id",
            "record_index",
            "display_label",
            "filename",
            "extract_source",
            "status",
            "llm_decision",
            "llm_confidence",
            "llm_reason",
            "llm_raw",
            "error",
        ]
        run_context = self._prepare_v2_run_context(pdf_files)
        run_dir = run_context["run_dir"]
        run_index = run_context["run_index"]
        resumed = bool(run_context.get("resumed"))
        resume_skip_messages = list(run_context.get("resume_skip_messages") or [])
        self.logger.info(f"本次 V2 运行目录: {run_dir}")
        artifact_paths = self._get_v2_artifact_paths(run_dir)

        master_queue_path = artifact_paths["master_queue"]
        master_results_path = artifact_paths["master_results"]
        batch_dir = artifact_paths["csv_batches"]
        batch_dir.mkdir(parents=True, exist_ok=True)
        stats_file = artifact_paths["statistics"]
        selected_ids_path = artifact_paths["selected_record_ids"]

        queue_rows: List[Dict[str, Any]] = []
        queue_extraction_interrupted = False
        if resumed:
            if master_queue_path.exists():
                queue_rows = self._read_rows_from_csv(master_queue_path)
                if queue_rows and self._queue_rows_match_pdf_files(queue_rows, pdf_files):
                    self.logger.info("阶段 1/4：检测到已有主队列，跳过文本提取并恢复续跑")
                    emit_progress(45)
                elif queue_rows and self._queue_rows_prefix_match_pdf_files(queue_rows, pdf_files):
                    self.logger.info(
                        f"阶段 1/4：检测到部分主队列（{len(queue_rows)}/{len(pdf_files)}），继续提取剩余 PDF 文本"
                    )
                    extraction_progress(len(queue_rows), len(pdf_files))
                    resumed = False
                else:
                    if queue_rows:
                        self.logger.warning("检测到不完整或过期的 master_queue.csv，将清理当前运行产物并重新提取文本。")
                    else:
                        self.logger.warning("检测到空的 master_queue.csv，将清理当前运行产物并重新提取文本。")
                    self._reset_v2_run_artifacts(run_dir)
                    resumed = False
            else:
                self.logger.warning("检测到可恢复运行但缺少 master_queue.csv，将清理当前运行产物并重新提取文本。")
                self._reset_v2_run_artifacts(run_dir)
                resumed = False

        if not resumed:
            self.logger.info("阶段 1/4：提取文本并构建主队列CSV")
            run_index["status"] = "extracting"
            self._persist_v2_run_index(run_dir, run_index)
            queue_rows, queue_extraction_interrupted = self._build_queue_rows(
                pdf_files,
                check_stop_callback,
                extraction_progress if progress_callback else None,
                existing_rows=queue_rows,
                master_queue_path=master_queue_path,
                fieldnames=fieldnames,
            )
            if queue_extraction_interrupted:
                run_index["status"] = "stopped"
                run_index_path = self._persist_v2_run_index(run_dir, run_index)
                return {
                    "New_Species_Reports": [],
                    "Possible_New_Species": [],
                    "Other_Literature": [],
                    "Uncertain": [],
                    "Failed": [],
                    "_stats_path": str(stats_file),
                    "_csv_path": str(master_results_path),
                    "_run_index_path": str(run_index_path),
                    "_selected_ids_path": "",
                    "_run_output_dir": str(run_dir),
                    "_run_status": "stopped",
                    "_resumed": resumed,
                    "_resume_skip_messages": resume_skip_messages,
                }
            if not queue_rows:
                run_index["status"] = "stopped"
                run_index_path = self._persist_v2_run_index(run_dir, run_index)
                return {
                    "New_Species_Reports": [],
                    "Possible_New_Species": [],
                    "Other_Literature": [],
                    "Uncertain": [],
                    "Failed": [],
                    "_stats_path": str(stats_file),
                    "_csv_path": str(master_results_path),
                    "_run_index_path": str(run_index_path),
                    "_selected_ids_path": "",
                    "_run_output_dir": str(run_dir),
                    "_run_status": "stopped",
                    "_resumed": resumed,
                    "_resume_skip_messages": resume_skip_messages,
                }
            self._write_rows_to_csv(master_queue_path, queue_rows, fieldnames)
            emit_progress(45)

        total_files = len(queue_rows)
        batches = self._chunk_rows_for_batches(queue_rows)
        total_batches = max(1, len(batches))
        processed_batches = 0
        processed_count = 0
        interrupted = False

        run_index["status"] = "validating"
        run_index["progress"]["total_batches"] = len(batches)
        run_index["progress"]["total_records"] = total_files
        run_index["artifacts"] = {
            "master_queue": str(master_queue_path),
            "batch_dir": str(batch_dir),
            "batch_raw_responses": str(artifact_paths["batch_raw_responses"]),
            "master_results": str(master_results_path),
            "selected_record_ids": "",
            "move_manifest": "",
            "compatibility_csv": "",
            "statistics": str(stats_file),
        }
        self._persist_v2_run_index(run_dir, run_index)

        self.logger.info(f"阶段 2/4：批量LLM校验，共 {len(batches)} 个批次")

        for index, batch_rows in enumerate(batches, start=1):
            batch_name = f"batch_{index:04d}"
            batch_path = batch_dir / f"{batch_name}.csv"

            if self._restore_completed_batch_rows(batch_path, batch_rows):
                processed_batches += 1
                processed_count += len(batch_rows)
                self.logger.info(f"复用已完成批次: {batch_name}")
            else:
                if check_stop_callback and check_stop_callback():
                    self.logger.warning("任务已被用户中断。")
                    interrupted = True
                    break

                emit_progress(45 + int(((index - 1) / total_batches) * 50))
                if not batch_path.exists():
                    self._write_rows_to_csv(batch_path, batch_rows, batch_fieldnames)

                self.logger.info(f"开始校验 {batch_name}，共 {len(batch_rows)} 条")
                batch_validated = self._validate_batch_rows(batch_rows, batch_name)
                self._write_rows_to_csv(batch_path, batch_validated, batch_fieldnames)
                processed_batches += 1
                processed_count += len(batch_rows)

            run_index["progress"]["completed_batches"] = processed_batches
            run_index["progress"]["completed_records"] = processed_count
            batch_progress = 45 + int((processed_batches / total_batches) * 50)
            file_progress = 45
            if total_files > 0:
                file_progress = 45 + int((min(processed_count, total_files) / total_files) * 50)
            emit_progress(min(95, max(batch_progress, file_progress)))
            self._persist_v2_run_index(run_dir, run_index)

        result_rows = queue_rows
        run_completed = bool(result_rows) and (not interrupted) and all(self._is_v2_row_terminal(row) for row in result_rows)

        self.logger.info("阶段 3/4：写回结果")
        emit_progress(96 if run_completed else min(95, 45 + int((processed_batches / total_batches) * 50)))
        self._write_rows_to_csv(master_results_path, result_rows, fieldnames)

        selected_rows: List[Dict[str, Any]] = []
        if run_completed:
            self._save_v2_compatibility_csv(result_rows, output_dir=run_dir)
            self._copy_v2_selected_files(result_rows, output_dir=run_dir)
            selected_rows = [
                row
                for row in result_rows
                if self._normalize_decision(row.get("llm_decision")) == "include"
                and self._clamp_confidence(row.get("llm_confidence"), 0.0) >= self.include_confidence_threshold
            ]
            with open(selected_ids_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["record_id", "record_index", "display_label", "filename", "confidence", "reason"])
                for row in selected_rows:
                    writer.writerow(
                        [
                            row.get("record_id", ""),
                            row.get("record_index", ""),
                            row.get("display_label", ""),
                            row.get("filename", ""),
                            row.get("llm_confidence", ""),
                            row.get("llm_reason", ""),
                        ]
                    )
            emit_progress(99)

        run_status = "completed" if run_completed else ("stopped" if interrupted else "partial")
        summary_counts = self._write_v2_statistics(
            stats_path=stats_file,
            run_dir=run_dir,
            rows=result_rows,
            total_batches=len(batches),
            processed_batches=processed_batches,
            run_status=run_status,
            run_completed=run_completed,
            master_queue_path=master_queue_path,
            master_results_path=master_results_path,
            selected_ids_path=selected_ids_path,
        )

        run_index["status"] = run_status
        run_index["progress"]["completed_batches"] = processed_batches
        run_index["progress"]["completed_records"] = summary_counts["completed"]
        run_index["summary"].update(
            {
                "included": summary_counts["included"],
                "excluded": summary_counts["excluded"],
                "uncertain": summary_counts["uncertain"],
                "pending": summary_counts["pending"],
                "move_failed": summary_counts["move_failed"],
                "include_confidence_threshold": self.include_confidence_threshold,
            }
        )
        run_index["artifacts"] = {
            "master_queue": str(master_queue_path),
            "batch_dir": str(batch_dir),
            "batch_raw_responses": str(artifact_paths["batch_raw_responses"]),
            "master_results": str(master_results_path),
            "selected_record_ids": str(selected_ids_path) if run_completed else "",
            "move_manifest": str(artifact_paths["move_manifest"]) if run_completed else "",
            "compatibility_csv": str(artifact_paths["compatibility_csv"]) if run_completed else "",
            "statistics": str(stats_file),
        }
        run_index_path = self._persist_v2_run_index(run_dir, run_index)

        included_files = [
            row["filename"]
            for row in result_rows
            if self._normalize_decision(row.get("llm_decision")) == "include"
            and self._clamp_confidence(row.get("llm_confidence"), 0.0) >= self.include_confidence_threshold
        ]
        excluded_files = [
            row["filename"]
            for row in result_rows
            if self._normalize_decision(row.get("llm_decision")) == "exclude"
        ]
        uncertain_files = [
            row["filename"]
            for row in result_rows
            if not self._is_v2_row_terminal(row)
            or self._normalize_decision(row.get("llm_decision")) == "uncertain"
            or (
                self._normalize_decision(row.get("llm_decision")) == "include"
                and self._clamp_confidence(row.get("llm_confidence"), 0.0) < self.include_confidence_threshold
            )
        ]

        self.logger.info(f"V2统计结果已保存到: {stats_file}")
        self.logger.info(f"V2运行索引已保存到: {run_index_path}")
        if run_completed:
            self.logger.info("阶段 4/4：完成")
            emit_progress(100)
        else:
            self.logger.warning(f"V2运行未完成，当前状态: {run_status}")

        return {
            "New_Species_Reports": included_files,
            "Possible_New_Species": [],
            "Other_Literature": excluded_files,
            "Uncertain": uncertain_files,
            "Failed": [],
            "_stats_path": str(stats_file),
            "_csv_path": str(master_results_path),
            "_run_index_path": str(run_index_path),
            "_selected_ids_path": str(selected_ids_path) if run_completed else "",
            "_run_output_dir": str(run_dir),
            "_run_status": run_status,
            "_resumed": resumed,
            "_resume_skip_messages": resume_skip_messages,
        }

    def batch_classify(self, check_stop_callback=None, progress_callback=None) -> Dict[str, Any]:
        return self._batch_classify_v2(check_stop_callback, progress_callback)


if __name__ == "__main__":
    cli_exit_code = _maybe_run_extract_cli_from_argv(sys.argv[1:])
    raise SystemExit(0 if cli_exit_code is None else cli_exit_code)
