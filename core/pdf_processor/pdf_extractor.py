"""
Figure 提取器 V2.0。

设计原则：
1. 以整张 figure 区域为候选单位，而不是 PDF 原始 image object。
2. 使用分层文本证据（figure_local / species_core / species_extended）。
3. 批量多模态复核多个候选，减少总 API 调用次数。
4. 保持现有 UI 的 `EnhancedPDFExtractionSystem` 入口稳定。
"""

from __future__ import annotations

import hashlib
import csv
import json
import logging
import re
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import fitz

from .figure_profile import load_figure_profile, normalize_figure_profile, profile_display_name
from .multimodal_validator import FigureReviewResult, MultimodalValidator
from .part_description_extractor import PartExtractionResult, TextPartDescriptionExtractor
from .part_description_profile import (
    load_part_description_profile,
    normalize_part_description_profile,
    profile_display_name as part_profile_display_name,
)


class EnhancedPDFExtractionSystem:
    """面向整张分类学 figure 的 PDF 提取器 V2.0。"""

    MIN_RECT_WIDTH = 40.0
    MIN_RECT_HEIGHT = 40.0
    MIN_RECT_AREA = 2400.0
    FIGURE_MARGIN = 10.0
    CLIP_MARGIN = 6.0
    EDGE_TEXT_TRIM_GAP = 3.0
    EDGE_TEXT_ZONE_RATIO = 0.18
    EDGE_TEXT_MIN_WIDTH_RATIO = 0.28
    MIN_CLIP_RETAIN_RATIO = 0.72
    CAPTION_MAX_DISTANCE = 140.0
    LOCAL_TEXT_MAX_DISTANCE = 180.0
    DEFAULT_ACCEPT_THRESHOLD = 0.75
    MAX_LOCAL_CHARS = 1200
    MAX_CORE_CHARS = 2200
    MAX_EXTENDED_CHARS = 2200

    TAXONOMIC_KEYWORDS = [
        "formicidae",
        "ant",
        "ants",
        "worker",
        "queen",
        "male",
        "holotype",
        "paratype",
        "diagnosis",
        "description",
        "measurements",
        "material examined",
        "type material",
        "type locality",
        "distribution",
        "remarks",
        "biology",
        "sp. nov",
        "sp. n",
        "gen. nov",
    ]
    CORE_SECTION_HINTS = {
        "diagnosis",
        "description",
        "measurements",
        "material_examined",
        "type_material",
        "distribution",
        "remarks",
        "biology",
        "etymology",
        "species_account",
    }

    EXTENDED_SECTION_HINTS = {
        "identification_key",
        "key_to_species",
        "taxonomic_treatment",
        "species_account",
        "synoptic_list",
    }

    def __init__(
        self,
        output_db_path: str = "pdf_extraction.db",
        save_images_to_files: bool = False,
        image_naming_strategy: str = "figure_title",
        per_pdf_database: bool = False,
        enable_multimodal_validation: bool = True,
        multimodal_config: Dict[str, Any] | None = None,
        text_part_config: Dict[str, Any] | None = None,
        figure_profile: Dict[str, Any] | None = None,
        figure_profile_path: str | None = None,
        part_description_profile: Dict[str, Any] | None = None,
        part_description_profile_path: str | None = None,
        two_stage_validation: bool = False,
        resume_completed_pdfs: bool = True,
    ):
        self.logger = logging.getLogger(__name__)
        self.output_db_path = Path(output_db_path).resolve()
        self.output_dir = self.output_db_path.parent
        self.save_images_to_files = save_images_to_files
        self.image_naming_strategy = image_naming_strategy
        self.per_pdf_database = per_pdf_database
        self.enable_multimodal_validation = enable_multimodal_validation
        self.multimodal_config = multimodal_config or {}
        self.text_part_config = text_part_config or {}
        self.figure_profile = self._load_runtime_figure_profile(figure_profile, figure_profile_path)
        self.figure_profile_name = profile_display_name(self.figure_profile) or "内置默认方案"
        self.part_description_profile = self._load_runtime_part_description_profile(
            part_description_profile,
            part_description_profile_path,
        )
        self.part_description_profile_name = part_profile_display_name(self.part_description_profile) or "内置默认部位描述方案"
        self.part_description_profile_path = str(part_description_profile_path or "").strip()
        self._apply_figure_profile(self.figure_profile)
        self.two_stage_validation = two_stage_validation
        self.resume_completed_pdfs = bool(resume_completed_pdfs)
        profile_threshold = (
            self.figure_profile.get("review_rules", {})
            .get("decision_thresholds", {})
            .get("accept_threshold", self.DEFAULT_ACCEPT_THRESHOLD)
        )
        self.review_accept_threshold = float(self.multimodal_config.get("accept_threshold", profile_threshold))
        self.db_conn: sqlite3.Connection | None = None

        self.artifacts_dir = self.output_dir / f"{self.output_db_path.stem}_v2_artifacts"
        self.figures_dir = self.artifacts_dir / "figure_images"
        self.accepted_figures_dir = self.artifacts_dir / "accepted_figures"
        self.review_figures_dir = self.artifacts_dir / "needs_review_figures"
        self.batch_dir = self.artifacts_dir / "review_batches"
        self.batch_raw_dir = self.artifacts_dir / "batch_raw_responses"
        self.stats_dir = self.artifacts_dir / "stats"

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.batch_dir.mkdir(parents=True, exist_ok=True)
        self.batch_raw_dir.mkdir(parents=True, exist_ok=True)
        self.stats_dir.mkdir(parents=True, exist_ok=True)
        if self.save_images_to_files:
            self.figures_dir.mkdir(parents=True, exist_ok=True)

        self.validator: MultimodalValidator | None = None
        self.multimodal_init_error: str = ""
        if self.enable_multimodal_validation:
            try:
                validator_config = dict(self.multimodal_config)
                validator_config.setdefault("figure_profile", self.figure_profile)
                self.validator = MultimodalValidator(validator_config)
                self.logger.info("Figure 多模态验证器初始化成功")
            except Exception as exc:
                self.multimodal_init_error = str(exc)
                self.logger.warning(f"Figure 多模态验证器初始化失败，将退化为本地启发式复核: {exc}")
                self.validator = None
        self.multimodal_startup_state: dict[str, object] = self._build_multimodal_startup_state()
        self.text_part_extractor = TextPartDescriptionExtractor(
            self.text_part_config,
            self.figure_profile,
            self.part_description_profile,
            self.part_description_profile_path,
        )
        if self.text_part_extractor.is_configured():
            self.logger.info(f"PDF 纯文本部位描述抽取器已配置 | profile={self.part_description_profile_name}")
        else:
            self.logger.info(
                f"PDF 纯文本部位描述抽取器未配置或关闭；提取时将跳过部位描述结构化 | profile={self.part_description_profile_name}"
            )

        self._init_database()

    def _load_runtime_figure_profile(
        self,
        figure_profile: Dict[str, Any] | None,
        figure_profile_path: str | None,
    ) -> Dict[str, Any]:
        if figure_profile_path:
            return load_figure_profile(figure_profile_path)
        if figure_profile is not None:
            return normalize_figure_profile(figure_profile)
        config_profile_path = str(self.multimodal_config.get("figure_profile_path", "") or "").strip()
        if config_profile_path:
            return load_figure_profile(config_profile_path)
        config_profile = self.multimodal_config.get("figure_profile")
        if isinstance(config_profile, dict):
            return normalize_figure_profile(config_profile)
        return normalize_figure_profile(None)

    def _load_runtime_part_description_profile(
        self,
        part_description_profile: Dict[str, Any] | None,
        part_description_profile_path: str | None,
    ) -> Dict[str, Any]:
        if part_description_profile_path:
            return load_part_description_profile(part_description_profile_path)
        if part_description_profile is not None:
            return normalize_part_description_profile(part_description_profile)
        config_profile_path = str(
            self.text_part_config.get("part_description_profile_path", self.text_part_config.get("profile_path", "")) or ""
        ).strip()
        if config_profile_path:
            return load_part_description_profile(config_profile_path)
        config_profile = self.text_part_config.get("part_description_profile", self.text_part_config.get("profile"))
        if isinstance(config_profile, dict):
            return normalize_part_description_profile(config_profile)
        return normalize_part_description_profile(None)

    def _apply_figure_profile(self, profile: Dict[str, Any]) -> None:
        extraction_rules = profile.get("extraction_rules", {})
        review_rules = profile.get("review_rules", {})
        view_schema = review_rules.get("view_schema", {})

        self.taxonomic_keywords = [str(item).lower() for item in profile.get("taxonomy_terms", [])]
        self.rejection_terms = [str(item).lower() for item in profile.get("rejection_terms", [])]
        self.auxiliary_terms = [str(item).lower() for item in profile.get("auxiliary_terms", [])]
        self.caption_patterns = list(extraction_rules.get("caption_patterns", []))
        self.figure_reference_patterns = list(extraction_rules.get("figure_reference_patterns", []))
        self.section_hint_map = dict(extraction_rules.get("section_hint_map", {}))
        self.core_section_hints = set(extraction_rules.get("core_section_hints", []))
        self.extended_section_hints = set(extraction_rules.get("extended_section_hints", []))
        limits = extraction_rules.get("evidence_text_limits", {})
        self.max_local_chars = int(limits.get("figure_local_chars", self.MAX_LOCAL_CHARS))
        self.max_core_chars = int(limits.get("species_core_chars", self.MAX_CORE_CHARS))
        self.max_extended_chars = int(limits.get("species_extended_chars", self.MAX_EXTENDED_CHARS))
        self.species_name_patterns = list(extraction_rules.get("species_name_patterns", []))
        self.blocked_genus_words = set(extraction_rules.get("blocked_genus_words", []))
        self.blocked_species_words = set(extraction_rules.get("blocked_species_words", []))
        self.required_figure_parts = set(str(item).strip() for item in view_schema.get("required_or_expected_views", []) if str(item).strip())
        self.figure_acceptance_mode = str(view_schema.get("acceptance_mode", "require_all_expected_parts") or "require_all_expected_parts")
        if self.figure_acceptance_mode not in {"require_all_expected_parts", "model_accept_with_parts_recorded"}:
            self.figure_acceptance_mode = "require_all_expected_parts"
        self.logger.info(f"Figure extraction/review profile: {profile_display_name(profile)}")

    @staticmethod
    def _compose_multimodal_startup_state(
        enable_multimodal_validation: bool,
        validator: MultimodalValidator | None,
        multimodal_init_error: str = "",
    ) -> dict[str, object]:
        state: dict[str, object] = {
            "enabled": bool(enable_multimodal_validation),
            "status": "real",
            "reason": "",
            "real_multimodal_configured": False,
            "warning_message": "",
        }

        if not enable_multimodal_validation:
            state.update(
                {
                    "status": "disabled",
                    "reason": "multimodal validation checkbox is off",
                }
            )
        elif validator is None:
            state.update(
                {
                    "status": "init_failed",
                    "reason": multimodal_init_error or "validator initialization failed",
                }
            )
        else:
            startup_reasons: list[str] = []
            if str(getattr(validator, "default_provider", "") or "").strip().lower() == "mock":
                startup_reasons.append("provider is set to mock")
            if not str(getattr(validator, "api_key", "") or "").strip():
                startup_reasons.append("API key is missing")
            if not str(getattr(validator, "base_url", "") or "").strip():
                startup_reasons.append("base URL is missing")

            if startup_reasons:
                state.update(
                    {
                        "status": "misconfigured",
                        "reason": "; ".join(startup_reasons),
                    }
                )
            else:
                state["real_multimodal_configured"] = True

        status = str(state.get("status", "real") or "real")
        reason = str(state.get("reason", "") or "").strip()
        detail = f" ({reason})" if reason and status != "disabled" else ""
        if status == "disabled":
            state["warning_message"] = (
                "WARNING: At startup, real multimodal review is turned OFF for this extraction run. "
                "The extractor will use mock/default review instead of a real image+text model, "
                "and figures that depend on it will be placed into Review instead of true acceptance."
            )
        elif status == "misconfigured":
            state["warning_message"] = (
                f"WARNING: At startup, real multimodal review is not actually configured{detail}. "
                "The extractor will use mock/default review instead of a real image+text model, "
                "and figures that depend on it will be placed into Review instead of true acceptance."
            )
        elif status == "init_failed":
            state["warning_message"] = (
                f"WARNING: At startup, real multimodal review could not start{detail}. "
                "The extractor will use mock/default review instead of a real image+text model, "
                "and figures that depend on it will be placed into Review instead of true acceptance."
            )

        return state

    def _build_multimodal_startup_state(self) -> dict[str, object]:
        return self._compose_multimodal_startup_state(
            enable_multimodal_validation=self.enable_multimodal_validation,
            validator=self.validator,
            multimodal_init_error=self.multimodal_init_error,
        )

    @classmethod
    def preview_multimodal_startup_state(
        cls,
        enable_multimodal_validation: bool = False,
        multimodal_config: Dict[str, Any] | None = None,
    ) -> dict[str, object]:
        validator: MultimodalValidator | None = None
        multimodal_init_error = ""

        if enable_multimodal_validation:
            try:
                validator = MultimodalValidator(multimodal_config or {})
            except Exception as exc:
                multimodal_init_error = str(exc)

        return cls._compose_multimodal_startup_state(
            enable_multimodal_validation=enable_multimodal_validation,
            validator=validator,
            multimodal_init_error=multimodal_init_error,
        )

    @classmethod
    def get_prestart_mock_review_confirmation(
        cls,
        enable_multimodal_validation: bool = False,
        multimodal_config: Dict[str, Any] | None = None,
    ) -> dict[str, object] | None:
        startup_state = cls.preview_multimodal_startup_state(
            enable_multimodal_validation=enable_multimodal_validation,
            multimodal_config=multimodal_config,
        )
        if bool(startup_state.get("real_multimodal_configured", False)):
            return None

        message = str(startup_state.get("warning_message", "") or "").strip()
        if not message:
            return None

        return {
            "startup_state": startup_state,
            "message": message,
            "status": str(startup_state.get("status", "") or "").strip().lower(),
            "reason": str(startup_state.get("reason", "") or "").strip(),
        }

    def get_multimodal_startup_state(self) -> dict[str, object]:
        return dict(self.multimodal_startup_state)

    def _startup_mock_review_source(self) -> str:
        status = str(self.multimodal_startup_state.get("status", "unknown") or "unknown").strip().lower()
        if status == "disabled":
            return "mock_startup_disabled"
        if status == "misconfigured":
            return "mock_startup_misconfigured"
        if status == "init_failed":
            return "mock_startup_init_failed"
        return "mock_startup_unavailable"

    # ------------------------------------------------------------------
    # Database / lifecycle
    # ------------------------------------------------------------------
    def _init_database(self) -> None:
        self.db_conn = sqlite3.connect(str(self.output_db_path))
        self.db_conn.execute("PRAGMA foreign_keys = ON")
        cursor = self.db_conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS pdf_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                file_name TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                total_pages INTEGER,
                file_size INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS figure_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pdf_file_id INTEGER NOT NULL,
                page_number INTEGER NOT NULL,
                figure_index INTEGER NOT NULL,
                candidate_id TEXT NOT NULL,
                figure_hash TEXT NOT NULL,
                figure_bbox TEXT NOT NULL,
                source_rects TEXT,
                raw_rect_count INTEGER DEFAULT 0,
                image_file_path TEXT,
                image_file_name TEXT,
                caption_text TEXT,
                local_context_text TEXT,
                species_candidate TEXT,
                species_confidence REAL DEFAULT 0.0,
                final_confidence REAL DEFAULT 0.0,
                category TEXT,
                accepted BOOLEAN DEFAULT FALSE,
                comparison_figure BOOLEAN DEFAULT FALSE,
                multiple_species BOOLEAN DEFAULT FALSE,
                has_auxiliary_inset BOOLEAN DEFAULT FALSE,
                detected_views TEXT,
                review_status TEXT DEFAULT 'pending',
                rejection_reason TEXT,
                multimodal_validated BOOLEAN DEFAULT FALSE,
                multimodal_review_mode TEXT DEFAULT 'none',
                multimodal_reasoning TEXT,
                multimodal_model_used TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pdf_file_id) REFERENCES pdf_files(id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS figure_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                figure_id INTEGER NOT NULL,
                evidence_level TEXT NOT NULL,
                evidence_type TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                section_title TEXT,
                text_content TEXT NOT NULL,
                match_score REAL DEFAULT 0.0,
                selection_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (figure_id) REFERENCES figure_records(id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS pdf_text_blocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pdf_file_id INTEGER NOT NULL,
                file_name TEXT,
                file_path TEXT,
                file_hash TEXT,
                block_ref TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                block_index INTEGER NOT NULL,
                section_hint TEXT,
                text_type TEXT,
                text_content TEXT NOT NULL,
                llm_role TEXT,
                llm_taxon_name TEXT,
                llm_confidence REAL DEFAULT 0.0,
                model_used TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pdf_file_id) REFERENCES pdf_files(id),
                UNIQUE(pdf_file_id, block_ref)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS taxon_part_descriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pdf_file_id INTEGER NOT NULL,
                file_name TEXT,
                file_path TEXT,
                file_hash TEXT,
                taxon_name TEXT,
                caste_or_stage TEXT,
                part_key TEXT NOT NULL,
                part_label TEXT NOT NULL,
                description_text TEXT NOT NULL,
                source_pages TEXT,
                source_block_refs TEXT,
                source_blocks TEXT,
                model_used TEXT,
                confidence REAL DEFAULT 0.0,
                review_status TEXT DEFAULT 'auto_extracted',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pdf_file_id) REFERENCES pdf_files(id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS part_extraction_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pdf_file_id INTEGER NOT NULL,
                file_name TEXT,
                file_path TEXT,
                file_hash TEXT,
                status TEXT NOT NULL,
                reason TEXT,
                model_used TEXT,
                used_protocol TEXT,
                profile_name TEXT,
                profile_schema_version TEXT,
                extracted_records INTEGER DEFAULT 0,
                labeled_blocks INTEGER DEFAULT 0,
                truncated_input BOOLEAN DEFAULT FALSE,
                raw_response TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pdf_file_id) REFERENCES pdf_files(id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS extraction_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pdf_file_id INTEGER NOT NULL,
                total_candidates INTEGER DEFAULT 0,
                accepted_figures INTEGER DEFAULT 0,
                rejected_figures INTEGER DEFAULT 0,
                review_queue_figures INTEGER DEFAULT 0,
                multimodal_validated_figures INTEGER DEFAULT 0,
                extraction_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pdf_file_id) REFERENCES pdf_files(id)
            )
            """
        )

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_figure_records_pdf_page ON figure_records(pdf_file_id, page_number)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_figure_evidence_figure ON figure_evidence(figure_id, evidence_level)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pdf_text_blocks_pdf_ref ON pdf_text_blocks(pdf_file_id, block_ref)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pdf_text_blocks_role ON pdf_text_blocks(pdf_file_id, llm_role)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_taxon_part_pdf_taxon ON taxon_part_descriptions(pdf_file_id, taxon_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_taxon_part_key ON taxon_part_descriptions(part_key)")
        self._ensure_column_exists("figure_records", "multimodal_review_mode", "TEXT DEFAULT 'none'")
        self._ensure_column_exists("part_extraction_runs", "profile_name", "TEXT")
        self._ensure_column_exists("part_extraction_runs", "profile_schema_version", "TEXT")

        self.db_conn.commit()
        self.logger.info(f"Figure V2.0 数据库初始化完成: {self.output_db_path}")

    def _ensure_column_exists(self, table_name: str, column_name: str, definition_sql: str) -> None:
        if self.db_conn is None:
            return
        cursor = self.db_conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = {str(row[1]) for row in cursor.fetchall()}
        if column_name in columns:
            return
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition_sql}")

    def close(self) -> None:
        if self.db_conn:
            self.db_conn.close()
            self.db_conn = None
            self.logger.info("Figure 提取器数据库连接已关闭")

    def __del__(self):
        self.close()

    def generate_sql_dump(self, output_path: str | None = None) -> None:
        output = Path(output_path) if output_path else self.stats_dir / "database_dump.sql"
        try:
            with open(output, "w", encoding="utf-8") as handle:
                subprocess.run(["sqlite3", str(self.output_db_path), ".dump"], stdout=handle, check=True)
            self.logger.info(f"数据库 SQL 转储文件已生成: {output}")
        except Exception as exc:
            self.logger.warning(f"生成数据库转储失败: {exc}")

    # ------------------------------------------------------------------
    # Main extraction flow
    # ------------------------------------------------------------------
    def extract_from_pdf(self, pdf_path: str) -> Dict[str, Any]:
        pdf_path_obj = Path(pdf_path)
        if not pdf_path_obj.exists():
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")
        if self.db_conn is None:
            raise RuntimeError("数据库连接未初始化")

        self.logger.info(f"开始执行 Figure V2.0 提取: {pdf_path_obj.name}")
        cursor = self.db_conn.cursor()

        file_hash = self._calculate_file_hash(pdf_path_obj)
        file_size = pdf_path_obj.stat().st_size

        if self.resume_completed_pdfs:
            existing_result = self._resume_existing_pdf_result(str(pdf_path_obj), file_hash)
            if existing_result is not None:
                return existing_result

        self._delete_existing_pdf_records(str(pdf_path_obj))

        try:
            doc = fitz.open(str(pdf_path_obj))
            total_pages = len(doc)
            cursor.execute(
                """
                INSERT INTO pdf_files (file_path, file_name, file_hash, total_pages, file_size)
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(pdf_path_obj), pdf_path_obj.name, file_hash, total_pages, file_size),
            )
            pdf_file_id = int(cursor.lastrowid or 0)

            document_blocks = self._extract_document_text_blocks(doc)
            part_extraction_result = self._extract_text_part_descriptions(
                pdf_file_id=pdf_file_id,
                file_name=pdf_path_obj.name,
                file_path=str(pdf_path_obj),
                file_hash=file_hash,
                document_blocks=document_blocks,
            )
            figure_candidates: List[Dict[str, Any]] = []

            for page_offset in range(total_pages):
                page_number = page_offset + 1
                page = doc[page_offset]
                page_blocks = [block for block in document_blocks if block["page_number"] == page_number]
                rect_entries = self._collect_page_visual_rects(page)
                clusters = self._cluster_image_rects(rect_entries)
                page_candidate_index = 1
                for cluster in clusters:
                    candidate = self._build_figure_candidate(
                        page=page,
                        page_number=page_number,
                        figure_index=page_candidate_index,
                        pdf_file_id=pdf_file_id,
                        pdf_filename=pdf_path_obj.name,
                        cluster=cluster,
                        page_blocks=page_blocks,
                        document_blocks=document_blocks,
                    )
                    if candidate is not None:
                        figure_candidates.append(candidate)
                        page_candidate_index += 1

            reviewed_candidates = self._review_all_candidates(figure_candidates, pdf_path_obj.stem)
            stats = self._persist_pdf_results(pdf_file_id, reviewed_candidates, part_extraction_result)
            export_stats = self._sync_import_ready_figure_exports(pdf_file_id)
            stats.update(export_stats)
            self.db_conn.commit()
            doc.close()

            self.logger.info(
                f"Figure V2.0 提取完成: {pdf_path_obj.name} | 候选={stats['total_figures']} | 通过={stats['accepted_figures']} | 拒绝={stats['rejected_figures']} | 复核={stats['review_queue_figures']} | 部位描述={stats.get('part_description_records', 0)} | 可导入通过图={stats.get('accepted_exported_figures', 0)}"
            )
            return {"status": "success", "file_id": pdf_file_id, "stats": stats}
        except Exception:
            self.db_conn.rollback()
            raise

    def _resume_existing_pdf_result(self, pdf_path: str, file_hash: str) -> Dict[str, Any] | None:
        if self.db_conn is None:
            return None
        cursor = self.db_conn.cursor()
        cursor.execute(
            """
            SELECT id, file_hash
            FROM pdf_files
            WHERE file_path = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (pdf_path,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        pdf_file_id = int(row[0])
        if str(row[1] or "") != str(file_hash or ""):
            return None

        stats = self._existing_pdf_completion_stats(pdf_file_id)
        if not stats:
            return None
        stats.update(self._sync_import_ready_figure_exports(pdf_file_id))
        stats["resumed_skip"] = True
        stats.setdefault("total_images", int(stats.get("total_figures", 0) or 0))
        stats.setdefault("taxonomic_images", int(stats.get("accepted_figures", 0) or 0))
        self.logger.info(
            f"Figure V2.0 已存在完整结果，跳过重跑: {Path(pdf_path).name} | "
            f"候选={stats.get('total_figures', 0)} | 通过={stats.get('accepted_figures', 0)} | "
            f"部位描述={stats.get('part_description_records', 0)}"
        )
        return {"status": "skipped_existing", "file_id": pdf_file_id, "stats": stats}

    def _existing_pdf_completion_stats(self, pdf_file_id: int) -> dict[str, int | str | bool] | None:
        if self.db_conn is None:
            return None
        cursor = self.db_conn.cursor()
        cursor.execute(
            """
            SELECT total_candidates, accepted_figures, rejected_figures,
                   review_queue_figures, multimodal_validated_figures
            FROM extraction_stats
            WHERE pdf_file_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (pdf_file_id,),
        )
        stats_row = cursor.fetchone()
        if not stats_row:
            return None

        cursor.execute("SELECT COUNT(*) FROM figure_records WHERE pdf_file_id = ?", (pdf_file_id,))
        figure_count = int(cursor.fetchone()[0] or 0)
        total_candidates = int(stats_row[0] or 0)
        if figure_count != total_candidates:
            return None

        cursor.execute(
            """
            SELECT status, reason, profile_name, extracted_records, labeled_blocks
            FROM part_extraction_runs
            WHERE pdf_file_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (pdf_file_id,),
        )
        part_row = cursor.fetchone()
        if not part_row:
            return None
        part_status = str(part_row[0] or "")
        if part_status in {"failed", "error"}:
            return None
        part_records = int(part_row[3] or 0)
        part_blocks = int(part_row[4] or 0)
        if part_blocks <= 0:
            return None

        return {
            "total_figures": total_candidates,
            "accepted_figures": int(stats_row[1] or 0),
            "rejected_figures": int(stats_row[2] or 0),
            "review_queue_figures": int(stats_row[3] or 0),
            "multimodal_validated_figures": int(stats_row[4] or 0),
            "non_real_multimodal_figures": 0,
            "startup_mock_review_figures": 0,
            "runtime_fallback_review_figures": 0,
            "multimodal_startup_status": str(self.multimodal_startup_state.get("status", "unknown") or "unknown"),
            "multimodal_startup_reason": str(self.multimodal_startup_state.get("reason", "") or ""),
            "real_multimodal_configured": bool(self.multimodal_startup_state.get("real_multimodal_configured", False)),
            "part_extraction_status": part_status,
            "part_extraction_reason": str(part_row[1] or ""),
            "part_description_profile_name": str(part_row[2] or ""),
            "part_description_records": part_records,
            "part_text_blocks": part_blocks,
        }

    def _delete_existing_pdf_records(self, pdf_path: str) -> None:
        if self.db_conn is None:
            return
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT id FROM pdf_files WHERE file_path = ?", (pdf_path,))
        existing = cursor.fetchone()
        if not existing:
            return
        pdf_file_id = int(existing[0])
        cursor.execute("DELETE FROM taxon_part_descriptions WHERE pdf_file_id = ?", (pdf_file_id,))
        cursor.execute("DELETE FROM pdf_text_blocks WHERE pdf_file_id = ?", (pdf_file_id,))
        cursor.execute("DELETE FROM part_extraction_runs WHERE pdf_file_id = ?", (pdf_file_id,))
        cursor.execute("DELETE FROM figure_evidence WHERE figure_id IN (SELECT id FROM figure_records WHERE pdf_file_id = ?)", (pdf_file_id,))
        cursor.execute("DELETE FROM figure_records WHERE pdf_file_id = ?", (pdf_file_id,))
        cursor.execute("DELETE FROM extraction_stats WHERE pdf_file_id = ?", (pdf_file_id,))
        cursor.execute("DELETE FROM pdf_files WHERE id = ?", (pdf_file_id,))
        self.db_conn.commit()

    # ------------------------------------------------------------------
    # Text extraction and evidence assembly
    # ------------------------------------------------------------------
    def _extract_document_text_blocks(self, doc: fitz.Document) -> List[Dict[str, Any]]:
        blocks: List[Dict[str, Any]] = []
        for page_offset in range(len(doc)):
            page_number = page_offset + 1
            page = doc[page_offset]
            page_text_payload = page.get_text("dict")
            if not isinstance(page_text_payload, dict):
                continue
            page_blocks = page_text_payload.get("blocks", [])
            if not isinstance(page_blocks, list):
                continue
            for block_index, block in enumerate(page_blocks):
                if "lines" not in block:
                    continue
                text_fragments: List[str] = []
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text_fragments.append(str(span.get("text", "") or ""))
                text_content = " ".join(fragment.strip() for fragment in text_fragments if fragment.strip()).strip()
                if not text_content:
                    continue
                bbox = list(block.get("bbox", [0.0, 0.0, 0.0, 0.0]))
                section_hint = self._detect_section_hint(text_content)
                taxonomic_score = self._score_taxonomic_text(text_content)
                text_type = self._classify_text_type(text_content, section_hint, taxonomic_score)
                blocks.append(
                    {
                        "page_number": page_number,
                        "block_index": block_index,
                        "text_content": text_content,
                        "bbox": bbox,
                        "section_hint": section_hint,
                        "text_type": text_type,
                        "contains_figure_ref": self._contains_figure_reference(text_content),
                        "taxonomic_score": taxonomic_score,
                        "species_mentions": self._extract_species_mentions(text_content),
                    }
                )
        return blocks

    def _extract_text_part_descriptions(
        self,
        *,
        pdf_file_id: int,
        file_name: str,
        file_path: str,
        file_hash: str,
        document_blocks: List[Dict[str, Any]],
    ) -> PartExtractionResult:
        try:
            result = self.text_part_extractor.extract(
                pdf_file_id=pdf_file_id,
                file_name=file_name,
                file_path=file_path,
                file_hash=file_hash,
                document_blocks=document_blocks,
            )
        except Exception as exc:
            self.logger.warning(f"PDF 纯文本部位描述抽取失败: {file_name} | {exc}")
            return PartExtractionResult(status="failed", reason=str(exc))

        if result.status in {"real", "mock"}:
            self.logger.info(
                f"PDF 纯文本部位描述抽取完成: {file_name} | profile={result.profile_name or self.part_description_profile_name} | records={len(result.records)} | blocks={len(result.block_labels)} | mode={result.status}"
            )
        else:
            self.logger.info(
                f"PDF 纯文本部位描述抽取跳过/未产出: {file_name} | profile={result.profile_name or self.part_description_profile_name} | status={result.status} | reason={result.reason}"
            )
        return result

    def _score_taxonomic_text(self, text: str) -> float:
        lowered = text.lower()
        hits = sum(1 for keyword in self.taxonomic_keywords if keyword in lowered)
        if hits <= 0:
            return 0.0
        return min(1.0, hits / 4.0)

    def _classify_text_type(self, text: str, section_hint: str, taxonomic_score: float) -> str:
        if self._is_valid_figure_title(text):
            return "caption"
        if section_hint != "other":
            return "heading"
        if taxonomic_score > 0:
            return "taxonomic"
        return "other"

    def _detect_section_hint(self, text: str) -> str:
        normalized = re.sub(r"\s+", " ", text.strip().lower())
        if not normalized:
            return "other"

        for prefix, label in self.section_hint_map.items():
            if normalized.startswith(prefix):
                return label

        if len(normalized.split()) <= 10 and ("sp. nov" in normalized or "sp. n" in normalized):
            return "species_account"
        if len(normalized.split()) <= 6 and self._extract_species_mentions(text):
            return "species_account"
        return "other"

    def _extract_species_mentions(self, text: str) -> List[str]:
        mentions: List[str] = []
        seen: set[str] = set()
        for pattern_text in self.species_name_patterns:
            try:
                pattern = re.compile(pattern_text)
            except re.error:
                self.logger.warning(f"Invalid species_name_pattern ignored: {pattern_text}")
                continue
            for match in pattern.findall(text or ""):
                if isinstance(match, tuple) and len(match) >= 2:
                    genus, species = str(match[0]), str(match[1])
                else:
                    parts = str(match).split()
                    if len(parts) < 2:
                        continue
                    genus, species = parts[0], parts[1]
                if genus.lower() in self.blocked_genus_words or species.lower() in self.blocked_species_words:
                    continue
                candidate = f"{genus} {species}"
                key = candidate.lower()
                if key in seen:
                    continue
                seen.add(key)
                mentions.append(candidate)
        return mentions[:8]

    def _contains_figure_reference(self, text: str) -> bool:
        lowered = text.lower()
        for pattern in self.figure_reference_patterns:
            try:
                if re.search(pattern, lowered, re.IGNORECASE):
                    return True
            except re.error:
                self.logger.warning(f"Invalid figure_reference_pattern ignored: {pattern}")
        return False

    def _extract_figure_reference_numbers(self, text: str) -> List[str]:
        numbers: List[str] = []
        for pattern in self.figure_reference_patterns:
            try:
                matches = re.findall(pattern, text or "", re.IGNORECASE)
            except re.error:
                self.logger.warning(f"Invalid figure_reference_pattern ignored: {pattern}")
                continue
            for match in matches:
                if isinstance(match, tuple):
                    match = next((item for item in match if item), "")
                normalized = str(match or "").strip().lower()
                if normalized and normalized not in numbers:
                    numbers.append(normalized)
        return numbers

    def _is_valid_figure_title(self, text: str) -> bool:
        cleaned = re.sub(r"\s+", " ", text.strip())
        if not cleaned:
            return False
        for pattern in self.caption_patterns:
            try:
                if re.match(pattern, cleaned, re.IGNORECASE):
                    return True
            except re.error:
                self.logger.warning(f"Invalid caption_pattern ignored: {pattern}")
        return False

    # ------------------------------------------------------------------
    # Figure candidate generation
    # ------------------------------------------------------------------
    def _collect_page_visual_rects(self, page: fitz.Page) -> List[Dict[str, Any]]:
        rect_entries: List[Dict[str, Any]] = []
        seen: set[Tuple[int, int, int, int]] = set()
        page_area = max(1.0, self._rect_area(page.rect))

        def append_rect(rect: fitz.Rect, source_type: str, source_ref: str) -> None:
            width = float(rect.width)
            height = float(rect.height)
            area = width * height
            if width < self.MIN_RECT_WIDTH or height < self.MIN_RECT_HEIGHT or area < self.MIN_RECT_AREA:
                return
            if area / page_area > 0.97:
                return
            key = (round(rect.x0), round(rect.y0), round(rect.x1), round(rect.y1))
            if key in seen:
                return
            seen.add(key)
            rect_entries.append({"source_type": source_type, "source_ref": source_ref, "rect": fitz.Rect(rect), "area": area})

        for image_info in page.get_images(full=True):
            xref = int(image_info[0])
            try:
                image_rects = page.get_image_rects(xref)
            except Exception:
                continue
            for rect in image_rects:
                append_rect(fitz.Rect(rect), "image", f"xref:{xref}")

        try:
            drawings = page.get_drawings()
        except Exception:
            drawings = []
        for index, drawing in enumerate(drawings):
            if not isinstance(drawing, dict):
                continue
            rect = drawing.get("rect")
            if rect is None:
                continue
            append_rect(fitz.Rect(rect), "drawing", f"drawing:{index}")
        return rect_entries

    def _cluster_image_rects(self, rect_entries: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        if not rect_entries:
            return []

        parent = list(range(len(rect_entries)))

        def find(index: int) -> int:
            while parent[index] != index:
                parent[index] = parent[parent[index]]
                index = parent[index]
            return index

        def union(left: int, right: int) -> None:
            root_left = find(left)
            root_right = find(right)
            if root_left != root_right:
                parent[root_right] = root_left

        for left in range(len(rect_entries)):
            left_rect = rect_entries[left]["rect"]
            left_expanded = self._expand_rect(left_rect, 28.0)
            for right in range(left + 1, len(rect_entries)):
                right_rect = rect_entries[right]["rect"]
                right_expanded = self._expand_rect(right_rect, 28.0)
                if left_expanded.intersects(right_expanded) or right_expanded.intersects(left_expanded):
                    union(left, right)

        grouped: Dict[int, List[Dict[str, Any]]] = {}
        for index, entry in enumerate(rect_entries):
            grouped.setdefault(find(index), []).append(entry)
        return list(grouped.values())

    def _build_figure_candidate(
        self,
        page: fitz.Page,
        page_number: int,
        figure_index: int,
        pdf_file_id: int,
        pdf_filename: str,
        cluster: List[Dict[str, Any]],
        page_blocks: List[Dict[str, Any]],
        document_blocks: List[Dict[str, Any]],
    ) -> Dict[str, Any] | None:
        union_rect = self._union_rects([entry["rect"] for entry in cluster])
        context_bbox = self._expand_rect(union_rect, self.FIGURE_MARGIN, page.rect)
        coverage_ratio = self._rect_area(context_bbox) / max(1.0, self._rect_area(page.rect))

        caption_block = self._select_caption_block(page_blocks, context_bbox)
        if coverage_ratio > 0.92 and len(page_blocks) >= 6 and caption_block is None:
            return None

        clip_bbox = self._build_clip_bbox(union_rect, page_blocks, caption_block, page.rect)

        image_file_path = ""
        image_file_name = ""
        figure_hash = self._hash_candidate(page_number, figure_index, clip_bbox, cluster)
        if self.save_images_to_files:
            image_file_name = self._generate_figure_filename(pdf_filename, page_number, figure_index, caption_block, figure_hash)
            image_file_path = str(self.figures_dir / image_file_name)
            self._save_figure_clip(page, clip_bbox, image_file_path)

        caption_text = str(caption_block.get("text_content", "") if caption_block else "")
        figure_numbers = self._extract_figure_reference_numbers(caption_text)
        local_blocks = self._select_local_blocks(page_blocks, context_bbox, caption_block, figure_numbers)
        figure_local_text = self._join_blocks_text(local_blocks, self.max_local_chars)
        species_candidate, species_confidence = self._infer_primary_species(caption_text, figure_local_text, page_blocks, document_blocks)

        candidate = {
            "pdf_file_id": pdf_file_id,
            "candidate_id": f"fig_p{page_number:03d}_{figure_index:03d}",
            "page_number": page_number,
            "figure_index": figure_index,
            "figure_hash": figure_hash,
            "figure_bbox": self._rect_to_payload(clip_bbox),
            "context_bbox": self._rect_to_payload(context_bbox),
            "source_rects": [self._rect_to_payload(entry["rect"]) for entry in cluster],
            "raw_rect_count": len(cluster),
            "image_path": image_file_path,
            "image_file_name": image_file_name,
            "caption_text": caption_text,
            "figure_numbers": figure_numbers,
            "figure_local_text": figure_local_text,
            "caption_block": caption_block,
            "local_blocks": local_blocks,
            "species_candidate": species_candidate,
            "species_confidence": species_confidence,
            "has_auxiliary_inset": self._has_auxiliary_inset(cluster, caption_text, figure_local_text),
        }

        candidate["core_blocks"] = self._select_species_core_blocks(candidate, document_blocks)
        candidate["extended_blocks"] = self._select_species_extended_blocks(candidate, document_blocks)
        candidate["species_core_text"] = self._join_blocks_text(candidate["core_blocks"], self.max_core_chars)
        candidate["species_extended_text"] = self._join_blocks_text(candidate["extended_blocks"], self.max_extended_chars)
        return candidate

    def _build_clip_bbox(
        self,
        union_rect: fitz.Rect,
        page_blocks: List[Dict[str, Any]],
        caption_block: Dict[str, Any] | None,
        page_rect: fitz.Rect,
    ) -> fitz.Rect:
        clip_bbox = self._expand_rect(union_rect, self.CLIP_MARGIN, page_rect)
        clip_bbox = self._trim_clip_bbox_against_text(clip_bbox, page_blocks, caption_block, page_rect, union_rect)
        return clip_bbox

    def _trim_clip_bbox_against_text(
        self,
        clip_bbox: fitz.Rect,
        page_blocks: List[Dict[str, Any]],
        caption_block: Dict[str, Any] | None,
        page_rect: fitz.Rect,
        union_rect: fitz.Rect,
    ) -> fitz.Rect:
        if not page_blocks:
            return clip_bbox

        top_limit = clip_bbox.y0 + clip_bbox.height * self.EDGE_TEXT_ZONE_RATIO
        bottom_limit = clip_bbox.y1 - clip_bbox.height * self.EDGE_TEXT_ZONE_RATIO
        left_limit = clip_bbox.x0 + clip_bbox.width * self.EDGE_TEXT_ZONE_RATIO
        right_limit = clip_bbox.x1 - clip_bbox.width * self.EDGE_TEXT_ZONE_RATIO

        trim_top_to = clip_bbox.y0
        trim_bottom_to = clip_bbox.y1
        trim_left_to = clip_bbox.x0
        trim_right_to = clip_bbox.x1

        caption_identity = None
        if caption_block is not None:
            caption_identity = (caption_block.get("page_number"), caption_block.get("block_index"))

        for block in page_blocks:
            block_rect = fitz.Rect(block.get("bbox", [0.0, 0.0, 0.0, 0.0]))
            if not clip_bbox.intersects(block_rect):
                continue

            width_overlap = max(0.0, min(block_rect.x1, clip_bbox.x1) - max(block_rect.x0, clip_bbox.x0))
            height_overlap = max(0.0, min(block_rect.y1, clip_bbox.y1) - max(block_rect.y0, clip_bbox.y0))
            width_ratio = width_overlap / max(1.0, clip_bbox.width)
            height_ratio = height_overlap / max(1.0, clip_bbox.height)

            identity = (block.get("page_number"), block.get("block_index"))
            is_caption = identity == caption_identity or block.get("text_type") == "caption"
            is_trim_candidate = is_caption or width_ratio >= self.EDGE_TEXT_MIN_WIDTH_RATIO or block.get("contains_figure_ref")
            if not is_trim_candidate:
                continue

            extends_above_union = block_rect.y1 <= union_rect.y0 + self.EDGE_TEXT_TRIM_GAP
            extends_below_union = block_rect.y0 >= union_rect.y1 - self.EDGE_TEXT_TRIM_GAP
            extends_left_of_union = block_rect.x1 <= union_rect.x0 + self.EDGE_TEXT_TRIM_GAP
            extends_right_of_union = block_rect.x0 >= union_rect.x1 - self.EDGE_TEXT_TRIM_GAP

            if block_rect.y0 <= top_limit and width_ratio >= self.EDGE_TEXT_MIN_WIDTH_RATIO and (is_caption or extends_above_union):
                trim_top_to = max(trim_top_to, min(block_rect.y1 + self.EDGE_TEXT_TRIM_GAP, clip_bbox.y1))
            if block_rect.y1 >= bottom_limit and width_ratio >= self.EDGE_TEXT_MIN_WIDTH_RATIO and (is_caption or extends_below_union):
                trim_bottom_to = min(trim_bottom_to, max(block_rect.y0 - self.EDGE_TEXT_TRIM_GAP, clip_bbox.y0))
            if block_rect.x0 <= left_limit and height_ratio >= 0.12 and (is_caption or extends_left_of_union):
                trim_left_to = max(trim_left_to, min(block_rect.x1 + self.EDGE_TEXT_TRIM_GAP, clip_bbox.x1))
            if block_rect.x1 >= right_limit and height_ratio >= 0.12 and (is_caption or extends_right_of_union):
                trim_right_to = min(trim_right_to, max(block_rect.x0 - self.EDGE_TEXT_TRIM_GAP, clip_bbox.x0))

        trimmed = fitz.Rect(trim_left_to, trim_top_to, trim_right_to, trim_bottom_to)
        if trimmed.width <= 1 or trimmed.height <= 1:
            return clip_bbox
        if trimmed.width < union_rect.width * self.MIN_CLIP_RETAIN_RATIO:
            trimmed.x0 = clip_bbox.x0
            trimmed.x1 = clip_bbox.x1
        if trimmed.height < union_rect.height * self.MIN_CLIP_RETAIN_RATIO:
            trimmed.y0 = clip_bbox.y0
            trimmed.y1 = clip_bbox.y1
        trimmed = fitz.Rect(
            max(page_rect.x0, trimmed.x0),
            max(page_rect.y0, trimmed.y0),
            min(page_rect.x1, trimmed.x1),
            min(page_rect.y1, trimmed.y1),
        )
        if trimmed.width <= 1 or trimmed.height <= 1:
            return clip_bbox
        return trimmed

    def _select_caption_block(self, page_blocks: List[Dict[str, Any]], bbox: fitz.Rect) -> Dict[str, Any] | None:
        best_block: Dict[str, Any] | None = None
        best_score = float("-inf")
        for block in page_blocks:
            if block.get("text_type") != "caption" and not block.get("contains_figure_ref"):
                continue
            block_rect = fitz.Rect(block.get("bbox", [0.0, 0.0, 0.0, 0.0]))
            overlap = max(0.0, min(block_rect.x1, bbox.x1) - max(block_rect.x0, bbox.x0))
            width = max(1.0, min(block_rect.width, bbox.width))
            overlap_ratio = overlap / width
            below_distance = block_rect.y0 - bbox.y1
            above_distance = bbox.y0 - block_rect.y1
            score = overlap_ratio * 2.0
            if 0 <= below_distance <= self.CAPTION_MAX_DISTANCE:
                score += 2.0 - (below_distance / self.CAPTION_MAX_DISTANCE)
            elif 0 <= above_distance <= self.CAPTION_MAX_DISTANCE * 0.75:
                score += 1.2 - (above_distance / (self.CAPTION_MAX_DISTANCE * 0.75))
            else:
                score -= 1.0
            if block.get("text_type") == "caption":
                score += 0.8
            if score > best_score:
                best_score = score
                best_block = block
        return best_block if best_score > 0 else None

    def _select_local_blocks(
        self,
        page_blocks: List[Dict[str, Any]],
        bbox: fitz.Rect,
        caption_block: Dict[str, Any] | None,
        candidate_figure_numbers: List[str],
    ) -> List[Dict[str, Any]]:
        selected: List[Tuple[float, Dict[str, Any]]] = []
        caption_identity = None
        if caption_block is not None:
            caption_identity = (caption_block.get("page_number"), caption_block.get("block_index"))

        for block in page_blocks:
            identity = (block.get("page_number"), block.get("block_index"))
            if identity == caption_identity:
                continue
            if self._block_references_other_figure(block, bbox=None, candidate_figure_numbers=candidate_figure_numbers):
                continue
            block_rect = fitz.Rect(block.get("bbox", [0.0, 0.0, 0.0, 0.0]))
            overlap = max(0.0, min(block_rect.x1, bbox.x1) - max(block_rect.x0, bbox.x0))
            width = max(1.0, min(block_rect.width, bbox.width))
            overlap_ratio = overlap / width
            vertical_distance = min(abs(block_rect.y0 - bbox.y1), abs(bbox.y0 - block_rect.y1), abs(block_rect.y0 - bbox.y0))
            if vertical_distance > self.LOCAL_TEXT_MAX_DISTANCE and overlap_ratio < 0.2:
                continue
            score = overlap_ratio
            score += 0.8 * float(block.get("taxonomic_score", 0.0))
            if block.get("contains_figure_ref"):
                score += 0.6
            if block.get("text_type") == "taxonomic":
                score += 0.4
            score += max(0.0, 1.0 - vertical_distance / max(self.LOCAL_TEXT_MAX_DISTANCE, 1.0))
            if score >= 0.45:
                enriched = dict(block)
                enriched["selection_reason"] = f"local_score={score:.3f}"
                selected.append((score, enriched))
        selected.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in selected[:6]]

    def _infer_primary_species(
        self,
        caption_text: str,
        figure_local_text: str,
        page_blocks: List[Dict[str, Any]],
        document_blocks: List[Dict[str, Any]],
    ) -> Tuple[str, float]:
        local_mentions = self._extract_species_mentions(f"{caption_text}\n{figure_local_text}")
        if local_mentions:
            return local_mentions[0], 0.82 if len(local_mentions) == 1 else 0.55

        heading_mentions: List[str] = []
        for block in page_blocks:
            if block.get("section_hint") == "species_account":
                heading_mentions.extend(block.get("species_mentions", []))
        if heading_mentions:
            return heading_mentions[0], 0.55

        for block in document_blocks:
            if block.get("section_hint") == "species_account" and block.get("species_mentions"):
                return block["species_mentions"][0], 0.35
        return "", 0.0

    def _select_species_core_blocks(self, candidate: Dict[str, Any], document_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        species_name = str(candidate.get("species_candidate", "") or "")
        page_number = int(candidate.get("page_number", 0) or 0)
        selected: List[Tuple[float, Dict[str, Any]]] = []
        for block in document_blocks:
            if block.get("text_type") == "caption":
                continue
            if self._block_references_other_figure(block, bbox=None, candidate_figure_numbers=list(candidate.get("figure_numbers", []))):
                continue
            block_text_lower = str(block.get("text_content", "") or "").lower()
            if any(token in block_text_lower for token in self.rejection_terms):
                continue
            score = 0.0
            if block.get("section_hint") in self.core_section_hints:
                score += 2.6
            if species_name and species_name.lower() in str(block.get("text_content", "")).lower():
                score += 3.0
            elif species_name and species_name.lower().split(" ")[0] in str(block.get("text_content", "")).lower():
                score += 1.2
            score += float(block.get("taxonomic_score", 0.0)) * 1.2
            page_delta = abs(int(block.get("page_number", 0) or 0) - page_number)
            if page_delta > 2:
                continue
            score += max(0.0, 1.0 - (page_delta / 3.0))
            if score < 2.3:
                continue
            enriched = dict(block)
            enriched["selection_reason"] = f"species_core_score={score:.3f}"
            selected.append((score, enriched))
        selected.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in selected[:8]]

    def _select_species_extended_blocks(self, candidate: Dict[str, Any], document_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        species_name = str(candidate.get("species_candidate", "") or "")
        page_number = int(candidate.get("page_number", 0) or 0)
        selected: List[Tuple[float, Dict[str, Any]]] = []
        for block in document_blocks:
            if block.get("text_type") == "caption":
                continue
            if self._block_references_other_figure(block, bbox=None, candidate_figure_numbers=list(candidate.get("figure_numbers", []))):
                continue
            block_text_lower = str(block.get("text_content", "") or "").lower()
            if any(token in block_text_lower for token in self.rejection_terms):
                continue
            score = 0.0
            if block.get("section_hint") in self.extended_section_hints:
                score += 2.0
            if block.get("contains_figure_ref"):
                score += 0.6
            if species_name and species_name.lower() in str(block.get("text_content", "")).lower():
                score += 1.5
            score += float(block.get("taxonomic_score", 0.0)) * 0.8
            page_delta = abs(int(block.get("page_number", 0) or 0) - page_number)
            if page_delta > 3:
                continue
            score += max(0.0, 0.8 - (page_delta / 5.0))
            if score < 1.6:
                continue
            enriched = dict(block)
            enriched["selection_reason"] = f"species_extended_score={score:.3f}"
            selected.append((score, enriched))
        selected.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in selected[:8]]

    def _join_blocks_text(self, blocks: List[Dict[str, Any]], max_chars: int) -> str:
        seen: set[Tuple[int, int]] = set()
        parts: List[str] = []
        current_length = 0
        for block in blocks:
            identity = (int(block.get("page_number", 0) or 0), int(block.get("block_index", 0) or 0))
            if identity in seen:
                continue
            seen.add(identity)
            text = str(block.get("text_content", "") or "").strip()
            if not text:
                continue
            prefix = ""
            section_hint = str(block.get("section_hint", "") or "").strip()
            if section_hint and section_hint != "other":
                prefix = f"[{section_hint}] "
            chunk = prefix + text
            if current_length + len(chunk) > max_chars and parts:
                break
            parts.append(chunk)
            current_length += len(chunk)
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Batch review
    # ------------------------------------------------------------------
    def _review_all_candidates(self, candidates: List[Dict[str, Any]], batch_scope: str = "") -> List[Dict[str, Any]]:
        if not candidates:
            return []
        batches = self._chunk_candidates_for_review(candidates)
        scope_prefix = self._safe_batch_scope(batch_scope)
        reviewed: List[Dict[str, Any]] = []
        for index, batch in enumerate(batches, start=1):
            batch_name = f"{scope_prefix}_batch_{index:04d}" if scope_prefix else f"batch_{index:04d}"
            reviewed.extend(self._review_candidate_batch(batch, batch_name))
        return reviewed

    def _safe_batch_scope(self, value: str) -> str:
        text = re.sub(r"[^A-Za-z0-9_\-]+", "_", str(value or "")).strip("_")
        return text[:60].strip("_")

    def _chunk_candidates_for_review(self, candidates: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        if not candidates:
            return []
        batch_size = self.validator.review_batch_size if self.validator else 4
        fallback_size = self.validator.review_batch_fallback_size if self.validator else 2
        char_budget = self.validator.batch_char_budget if self.validator else 10000

        chunks: List[List[Dict[str, Any]]] = []
        current_chunk: List[Dict[str, Any]] = []
        current_chars = 0
        for candidate in candidates:
            candidate_chars = (
                len(str(candidate.get("caption_text", "") or ""))
                + len(str(candidate.get("figure_local_text", "") or ""))
                + len(str(candidate.get("species_core_text", "") or ""))
                + len(str(candidate.get("species_extended_text", "") or ""))
                + 320
            )
            should_flush = False
            if current_chunk and len(current_chunk) >= batch_size:
                should_flush = True
            elif current_chunk and len(current_chunk) >= fallback_size and current_chars + candidate_chars > char_budget:
                should_flush = True
            if should_flush:
                chunks.append(current_chunk)
                current_chunk = []
                current_chars = 0
            current_chunk.append(candidate)
            current_chars += candidate_chars
        if current_chunk:
            chunks.append(current_chunk)
        return chunks

    def _review_candidate_batch(self, candidates: List[Dict[str, Any]], batch_id: str) -> List[Dict[str, Any]]:
        if not candidates:
            return []
        self._save_batch_manifest(batch_id, candidates)

        if not self.validator or not self.enable_multimodal_validation:
            results, raw_response, used_protocol = MultimodalValidator(
                {"default_provider": "mock", "figure_profile": self.figure_profile}
            ).review_triptych_batch_mock(candidates)
            self._save_batch_raw_response(batch_id, raw_response)
            return self._apply_review_results(
                candidates,
                results,
                used_protocol,
                review_source=self._startup_mock_review_source(),
            )

        max_retries = 3
        retry_delay = 1.0
        last_error = ""
        for attempt in range(max_retries):
            try:
                results, raw_response, used_protocol = self.validator.review_triptych_batch(candidates)
                self._save_batch_raw_response(batch_id, raw_response)
                review_source = "real_multimodal"
                if any(str(result.review_mode or "").strip().lower() != "real" for result in results):
                    review_source = self._startup_mock_review_source()
                return self._apply_review_results(
                    candidates,
                    results,
                    used_protocol,
                    review_source=review_source,
                )
            except Exception as exc:
                last_error = str(exc)
                raw_response = str(getattr(self.validator, "last_raw_response", "") or "")
                if raw_response:
                    self._save_batch_raw_response(f"{batch_id}_attempt_{attempt + 1}_failed", raw_response)
                self.logger.warning(f"Figure 批量复核失败 {batch_id} (尝试 {attempt + 1}/{max_retries}): {last_error}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2

        if self._should_split_failed_batch(candidates, last_error):
            midpoint = max(1, len(candidates) // 2)
            self.logger.warning(f"批次 {batch_id} 失败，自动拆分重试。原始条数={len(candidates)}")
            left = self._review_candidate_batch(candidates[:midpoint], f"{batch_id}_a")
            right = self._review_candidate_batch(candidates[midpoint:], f"{batch_id}_b")
            return left + right

        fallback_results, raw_response, used_protocol = self.validator.review_triptych_batch_mock(candidates, error_context=last_error)
        self._save_batch_raw_response(f"{batch_id}_fallback", raw_response)
        return self._apply_review_results(
            candidates,
            fallback_results,
            used_protocol,
            review_source="mock_runtime_fallback",
        )

    def _apply_review_results(
        self,
        candidates: List[Dict[str, Any]],
        results: List[FigureReviewResult],
        used_protocol: str,
        review_source: str = "real_multimodal",
    ) -> List[Dict[str, Any]]:
        result_map = {result.candidate_id: result for result in results}
        reviewed_candidates: List[Dict[str, Any]] = []
        for candidate in candidates:
            reviewed = dict(candidate)
            candidate_id = str(candidate.get("candidate_id", "") or "")
            result = result_map.get(candidate_id)
            candidate_review_source = review_source
            if result is None:
                result = FigureReviewResult(
                    candidate_id=candidate_id,
                    accept=False,
                    confidence_score=0.0,
                    category="uncertain",
                    reasoning="批量复核结果缺失",
                    model_used="missing_result",
                    review_mode="missing",
                )
                candidate_review_source = "missing_result"
            is_real_multimodal = str(result.review_mode or "").strip().lower() == "real"
            required_parts_ok = self._has_required_profile_parts(result.detected_views)
            category_ok = self._is_accept_category(result.category)
            accepted = (
                result.accept
                and result.confidence_score >= self.review_accept_threshold
                and category_ok
                and not result.comparison_figure
                and not result.multiple_species
                and required_parts_ok
                and is_real_multimodal
            )
            if accepted:
                review_status = "accepted"
                rejection_reason = ""
            elif not is_real_multimodal:
                review_status = "needs_review"
                rejection_reason = "mock_review_only"
            elif result.comparison_figure:
                review_status = "rejected"
                rejection_reason = "comparison_figure"
            elif result.multiple_species:
                review_status = "rejected"
                rejection_reason = "multiple_species"
            elif result.accept and not required_parts_ok:
                review_status = "rejected"
                rejection_reason = "missing_required_parts"
            elif result.accept and not category_ok:
                review_status = "rejected"
                rejection_reason = result.category or "blocked_category"
            elif result.accept and result.confidence_score < self.review_accept_threshold:
                review_status = "rejected"
                rejection_reason = "below_accept_threshold"
            elif result.category == "uncertain":
                review_status = "needs_review"
                rejection_reason = "uncertain"
            elif not result.accept:
                review_status = "rejected"
                rejection_reason = "model_rejected"
            else:
                review_status = "rejected"
                rejection_reason = "review_rules_not_met"

            reviewed.update(
                {
                    "accepted": accepted,
                    "final_confidence": result.confidence_score,
                    "category": result.category,
                    "review_status": review_status,
                    "rejection_reason": rejection_reason,
                    "multimodal_validated": is_real_multimodal,
                    "multimodal_reasoning": result.reasoning,
                    "multimodal_model_used": result.model_used or used_protocol,
                    "species_candidate": result.species_candidate or reviewed.get("species_candidate", ""),
                    "species_confidence": max(float(reviewed.get("species_confidence", 0.0) or 0.0), result.species_confidence),
                    "comparison_figure": result.comparison_figure,
                    "multiple_species": result.multiple_species,
                    "detected_views": result.detected_views,
                    "has_auxiliary_inset": bool(reviewed.get("has_auxiliary_inset")) or result.has_auxiliary_inset,
                    "multimodal_review_mode": result.review_mode,
                    "multimodal_review_source": candidate_review_source,
                }
            )
            reviewed_candidates.append(reviewed)
        return reviewed_candidates

    def _has_required_profile_parts(self, detected_views: List[str]) -> bool:
        if self.figure_acceptance_mode == "model_accept_with_parts_recorded":
            return True
        if not self.required_figure_parts:
            return True
        return self.required_figure_parts.issubset({str(view or "").strip() for view in detected_views})

    @staticmethod
    def _is_accept_category(category: str) -> bool:
        category_text = str(category or "").strip().lower()
        if not category_text:
            return False
        blocked_tokens = ("comparison", "multi", "uncertain", "non_", "non-", "other")
        return not any(token in category_text for token in blocked_tokens)

    def _block_references_other_figure(
        self,
        block: Dict[str, Any],
        bbox: fitz.Rect | None,
        candidate_figure_numbers: List[str],
    ) -> bool:
        _ = bbox
        if not block.get("contains_figure_ref"):
            return False
        if not candidate_figure_numbers:
            return False
        referenced_numbers = self._extract_figure_reference_numbers(str(block.get("text_content", "") or ""))
        if not referenced_numbers:
            return False
        candidate_set = {str(item).strip().lower() for item in candidate_figure_numbers if str(item).strip()}
        return candidate_set.isdisjoint({str(item).strip().lower() for item in referenced_numbers})

    def _should_split_failed_batch(self, candidates: List[Dict[str, Any]], detail: str) -> bool:
        if len(candidates) <= 1:
            return False
        lowered = str(detail or "").lower()
        tokens = ["truncated", "max_tokens", "length", "json", "timeout", "timed out", "missing_candidates"]
        return any(token in lowered for token in tokens)

    def _save_batch_manifest(self, batch_id: str, candidates: List[Dict[str, Any]]) -> str:
        manifest_path = self.batch_dir / f"{batch_id}.json"
        payload = {
            "batch_id": batch_id,
            "candidate_count": len(candidates),
            "candidates": [
                {
                    "candidate_id": candidate.get("candidate_id", ""),
                    "page_number": candidate.get("page_number", 0),
                    "image_path": candidate.get("image_path", ""),
                    "caption_text": candidate.get("caption_text", ""),
                    "species_candidate": candidate.get("species_candidate", ""),
                }
                for candidate in candidates
            ],
        }
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        return str(manifest_path)

    def _save_batch_raw_response(self, batch_id: str, raw_response: str) -> str:
        raw_path = self.batch_raw_dir / f"{batch_id}.txt"
        with open(raw_path, "w", encoding="utf-8") as handle:
            handle.write(str(raw_response or ""))
        return str(raw_path)

    def _sync_import_ready_figure_exports(self, pdf_file_id: int) -> dict[str, int | str]:
        if self.db_conn is None:
            return {}
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT file_name FROM pdf_files WHERE id = ?", (pdf_file_id,))
        pdf_row = cursor.fetchone()
        if not pdf_row:
            return {}
        pdf_stem = self._safe_batch_scope(Path(str(pdf_row[0] or "pdf")).stem) or f"pdf_{pdf_file_id}"
        self.accepted_figures_dir.mkdir(parents=True, exist_ok=True)
        self.review_figures_dir.mkdir(parents=True, exist_ok=True)
        self._remove_pdf_exported_files(self.accepted_figures_dir, pdf_stem)
        self._remove_pdf_exported_files(self.review_figures_dir, pdf_stem)

        cursor.execute(
            """
            SELECT
                id, page_number, image_file_path, image_file_name, species_candidate,
                final_confidence, category, review_status, accepted
            FROM figure_records
            WHERE pdf_file_id = ? AND (accepted = 1 OR review_status = 'needs_review')
            ORDER BY page_number ASC, figure_index ASC, id ASC
            """,
            (pdf_file_id,),
        )
        rows = cursor.fetchall()
        exported_rows: List[Dict[str, Any]] = []
        accepted_count = 0
        review_count = 0
        for row in rows:
            (
                figure_id,
                page_number,
                image_file_path,
                image_file_name,
                species_candidate,
                final_confidence,
                category,
                review_status,
                accepted,
            ) = row
            source_path = Path(str(image_file_path or ""))
            if not source_path.exists():
                continue
            target_dir = self.accepted_figures_dir if bool(accepted) else self.review_figures_dir
            status_prefix = "accepted" if bool(accepted) else "review"
            target_name = self._export_figure_filename(
                pdf_stem=pdf_stem,
                status_prefix=status_prefix,
                figure_id=int(figure_id),
                source_name=str(image_file_name or source_path.name),
            )
            target_path = target_dir / target_name
            shutil.copy2(source_path, target_path)
            if bool(accepted):
                accepted_count += 1
            else:
                review_count += 1
            exported_rows.append(
                {
                    "pdf_file_id": pdf_file_id,
                    "figure_id": int(figure_id),
                    "status": status_prefix,
                    "pdf_name": str(pdf_row[0] or ""),
                    "page_number": int(page_number or 0),
                    "species_candidate": str(species_candidate or ""),
                    "final_confidence": float(final_confidence or 0.0),
                    "category": str(category or ""),
                    "review_status": str(review_status or ""),
                    "source_image_path": str(source_path),
                    "exported_image_path": str(target_path),
                    "exported_image_name": target_name,
                }
            )

        manifest_path = self.stats_dir / f"{pdf_stem}_import_ready_figures.csv"
        self._write_import_ready_manifest(manifest_path, exported_rows)
        return {
            "accepted_exported_figures": accepted_count,
            "review_exported_figures": review_count,
            "accepted_figures_dir": str(self.accepted_figures_dir),
            "needs_review_figures_dir": str(self.review_figures_dir),
            "import_ready_manifest": str(manifest_path),
        }

    def _remove_pdf_exported_files(self, folder: Path, pdf_stem: str) -> None:
        if not folder.exists():
            return
        prefix = f"{pdf_stem}__"
        for path in folder.iterdir():
            if path.is_file() and path.name.startswith(prefix):
                path.unlink()

    def _export_figure_filename(self, *, pdf_stem: str, status_prefix: str, figure_id: int, source_name: str) -> str:
        suffix = Path(source_name).suffix or ".png"
        source_stem = re.sub(r"[^A-Za-z0-9_\-]+", "_", Path(source_name).stem).strip("_")[:80] or "figure"
        return f"{pdf_stem}__{status_prefix}_{figure_id:06d}__{source_stem}{suffix}"

    def _write_import_ready_manifest(self, manifest_path: Path, rows: List[Dict[str, Any]]) -> None:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "pdf_file_id",
            "figure_id",
            "status",
            "pdf_name",
            "page_number",
            "species_candidate",
            "final_confidence",
            "category",
            "review_status",
            "source_image_path",
            "exported_image_path",
            "exported_image_name",
        ]
        with open(manifest_path, "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _persist_pdf_results(
        self,
        pdf_file_id: int,
        candidates: List[Dict[str, Any]],
        part_extraction_result: PartExtractionResult | None = None,
    ) -> dict[str, int | str | bool]:
        if self.db_conn is None:
            raise RuntimeError("数据库连接未初始化")
        cursor = self.db_conn.cursor()

        accepted_count = 0
        rejected_count = 0
        review_count = 0
        validated_count = 0
        startup_mock_count = 0
        runtime_fallback_count = 0
        non_real_review_count = 0

        for candidate in candidates:
            review_source = str(candidate.get("multimodal_review_source", "") or "").strip().lower()
            cursor.execute(
                """
                INSERT INTO figure_records (
                    pdf_file_id, page_number, figure_index, candidate_id, figure_hash,
                    figure_bbox, source_rects, raw_rect_count, image_file_path, image_file_name,
                    caption_text, local_context_text, species_candidate, species_confidence,
                    final_confidence, category, accepted, comparison_figure, multiple_species,
                    has_auxiliary_inset, detected_views, review_status, rejection_reason,
                    multimodal_validated, multimodal_review_mode, multimodal_reasoning, multimodal_model_used
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pdf_file_id,
                    int(candidate.get("page_number", 0) or 0),
                    int(candidate.get("figure_index", 0) or 0),
                    str(candidate.get("candidate_id", "") or ""),
                    str(candidate.get("figure_hash", "") or ""),
                    json.dumps(candidate.get("figure_bbox", {}), ensure_ascii=False),
                    json.dumps(candidate.get("source_rects", []), ensure_ascii=False),
                    int(candidate.get("raw_rect_count", 0) or 0),
                    str(candidate.get("image_path", "") or ""),
                    str(candidate.get("image_file_name", "") or ""),
                    str(candidate.get("caption_text", "") or ""),
                    str(candidate.get("figure_local_text", "") or ""),
                    str(candidate.get("species_candidate", "") or ""),
                    float(candidate.get("species_confidence", 0.0) or 0.0),
                    float(candidate.get("final_confidence", 0.0) or 0.0),
                    str(candidate.get("category", "") or ""),
                    bool(candidate.get("accepted", False)),
                    bool(candidate.get("comparison_figure", False)),
                    bool(candidate.get("multiple_species", False)),
                    bool(candidate.get("has_auxiliary_inset", False)),
                    json.dumps(candidate.get("detected_views", []), ensure_ascii=False),
                    str(candidate.get("review_status", "pending") or "pending"),
                    str(candidate.get("rejection_reason", "") or ""),
                    bool(candidate.get("multimodal_validated", False)),
                    str(candidate.get("multimodal_review_mode", "none") or "none"),
                    str(candidate.get("multimodal_reasoning", "") or ""),
                    str(candidate.get("multimodal_model_used", "") or ""),
                ),
            )
            figure_id = int(cursor.lastrowid or 0)

            self._insert_evidence_rows(cursor, figure_id, candidate)

            if candidate.get("multimodal_validated"):
                validated_count += 1
            else:
                non_real_review_count += 1
            if review_source.startswith("mock_startup_"):
                startup_mock_count += 1
            elif review_source == "mock_runtime_fallback":
                runtime_fallback_count += 1
            if candidate.get("accepted"):
                accepted_count += 1
            elif candidate.get("review_status") == "needs_review":
                review_count += 1
            else:
                rejected_count += 1

        part_stats = self._persist_part_extraction_result(cursor, pdf_file_id, part_extraction_result)

        cursor.execute(
            """
            INSERT INTO extraction_stats (
                pdf_file_id, total_candidates, accepted_figures, rejected_figures,
                review_queue_figures, multimodal_validated_figures
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (pdf_file_id, len(candidates), accepted_count, rejected_count, review_count, validated_count),
        )

        return {
            "total_figures": len(candidates),
            "accepted_figures": accepted_count,
            "rejected_figures": rejected_count,
            "review_queue_figures": review_count,
            "multimodal_validated_figures": validated_count,
            "non_real_multimodal_figures": non_real_review_count,
            "startup_mock_review_figures": startup_mock_count,
            "runtime_fallback_review_figures": runtime_fallback_count,
            "multimodal_startup_status": str(self.multimodal_startup_state.get("status", "unknown") or "unknown"),
            "multimodal_startup_reason": str(self.multimodal_startup_state.get("reason", "") or ""),
            "real_multimodal_configured": bool(self.multimodal_startup_state.get("real_multimodal_configured", False)),
            "part_extraction_status": str(part_stats.get("status", "")),
            "part_extraction_reason": str(part_stats.get("reason", "")),
            "part_description_profile_name": str(part_stats.get("profile_name", "")),
            "part_description_records": int(part_stats.get("part_description_records", 0) or 0),
            "part_text_blocks": int(part_stats.get("part_text_blocks", 0) or 0),
            # 兼容旧 UI 日志字段
            "total_images": len(candidates),
            "taxonomic_images": accepted_count,
        }

    def _persist_part_extraction_result(
        self,
        cursor: sqlite3.Cursor,
        pdf_file_id: int,
        result: PartExtractionResult | None,
    ) -> dict[str, int | str | bool]:
        if result is None:
            result = PartExtractionResult(status="skipped", reason="not_run")
        if not result.profile_name:
            result.profile_name = self.part_description_profile_name
        if not result.profile_schema_version:
            result.profile_schema_version = str(self.part_description_profile.get("schema_version", "") or "")
        records = list(result.records or [])
        block_labels = list(result.block_labels or [])

        run_file_name = ""
        run_file_path = ""
        run_file_hash = ""
        for payload in block_labels:
            run_file_name = str(payload.get("file_name", "") or "")
            run_file_path = str(payload.get("file_path", "") or "")
            run_file_hash = str(payload.get("file_hash", "") or "")
            if run_file_name or run_file_path or run_file_hash:
                break
        if not run_file_name and records:
            first_block = (records[0].get("source_blocks") or [{}])[0]
            if isinstance(first_block, dict):
                run_file_name = str(first_block.get("file_name", "") or "")
                run_file_path = str(first_block.get("file_path", "") or "")
                run_file_hash = str(first_block.get("file_hash", "") or "")

        cursor.execute(
            """
            INSERT INTO part_extraction_runs (
                pdf_file_id, file_name, file_path, file_hash, status, reason,
                model_used, used_protocol, profile_name, profile_schema_version, extracted_records, labeled_blocks,
                truncated_input, raw_response
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pdf_file_id,
                run_file_name,
                run_file_path,
                run_file_hash,
                str(result.status or ""),
                str(result.reason or ""),
                str(result.model_used or ""),
                str(result.used_protocol or ""),
                str(result.profile_name or self.part_description_profile_name or ""),
                str(result.profile_schema_version or self.part_description_profile.get("schema_version", "") or ""),
                len(records),
                len(block_labels),
                bool(result.truncated_input),
                str(result.raw_response or ""),
            ),
        )

        for block in block_labels:
            cursor.execute(
                """
                INSERT OR REPLACE INTO pdf_text_blocks (
                    pdf_file_id, file_name, file_path, file_hash, block_ref,
                    page_number, block_index, section_hint, text_type, text_content,
                    llm_role, llm_taxon_name, llm_confidence, model_used
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pdf_file_id,
                    str(block.get("file_name", "") or ""),
                    str(block.get("file_path", "") or ""),
                    str(block.get("file_hash", "") or ""),
                    str(block.get("block_ref", "") or ""),
                    int(block.get("page_number", 0) or 0),
                    int(block.get("block_index", 0) or 0),
                    str(block.get("section_hint", "") or ""),
                    str(block.get("text_type", "") or ""),
                    str(block.get("text_content", "") or ""),
                    str(block.get("llm_role", "") or ""),
                    str(block.get("llm_taxon_name", "") or ""),
                    float(block.get("llm_confidence", 0.0) or 0.0),
                    str(block.get("model_used", "") or result.model_used or ""),
                ),
            )

        for record in records:
            source_blocks = record.get("source_blocks", [])
            if not isinstance(source_blocks, list):
                source_blocks = []
            first_block = next((block for block in source_blocks if isinstance(block, dict)), {})
            file_name = str(first_block.get("file_name", run_file_name) if isinstance(first_block, dict) else run_file_name)
            file_path = str(first_block.get("file_path", run_file_path) if isinstance(first_block, dict) else run_file_path)
            file_hash = str(first_block.get("file_hash", run_file_hash) if isinstance(first_block, dict) else run_file_hash)
            cursor.execute(
                """
                INSERT INTO taxon_part_descriptions (
                    pdf_file_id, file_name, file_path, file_hash, taxon_name,
                    caste_or_stage, part_key, part_label, description_text,
                    source_pages, source_block_refs, source_blocks, model_used,
                    confidence, review_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pdf_file_id,
                    file_name,
                    file_path,
                    file_hash,
                    str(record.get("taxon_name", "") or ""),
                    str(record.get("caste_or_stage", "unknown") or "unknown"),
                    str(record.get("part_key", "") or ""),
                    str(record.get("part_label", "") or ""),
                    str(record.get("description_text", "") or ""),
                    json.dumps(record.get("source_pages", []), ensure_ascii=False),
                    json.dumps(record.get("source_block_refs", []), ensure_ascii=False),
                    json.dumps(source_blocks, ensure_ascii=False),
                    str(record.get("model_used", "") or result.model_used or ""),
                    float(record.get("confidence", 0.0) or 0.0),
                    str(record.get("review_status", "auto_extracted") or "auto_extracted"),
                ),
            )

        return {
            "status": str(result.status or ""),
            "reason": str(result.reason or ""),
            "profile_name": str(result.profile_name or self.part_description_profile_name or ""),
            "part_description_records": len(records),
            "part_text_blocks": len(block_labels),
            "part_extraction_real": result.status == "real",
        }

    def _insert_evidence_rows(self, cursor: sqlite3.Cursor, figure_id: int, candidate: Dict[str, Any]) -> None:
        evidence_rows: List[Tuple[str, str, int, str, str, float, str]] = []

        if candidate.get("caption_text"):
            evidence_rows.append(
                (
                    "figure_local",
                    "caption",
                    int(candidate.get("page_number", 0) or 0),
                    "caption",
                    str(candidate.get("caption_text", "") or ""),
                    1.0,
                    "nearest_caption",
                )
            )

        for block in candidate.get("local_blocks", []):
            evidence_rows.append(
                (
                    "figure_local",
                    str(block.get("text_type", "local") or "local"),
                    int(block.get("page_number", 0) or 0),
                    str(block.get("section_hint", "") or ""),
                    str(block.get("text_content", "") or ""),
                    float(self._extract_score_from_reason(block.get("selection_reason", ""))),
                    str(block.get("selection_reason", "") or ""),
                )
            )

        for block in candidate.get("core_blocks", []):
            evidence_rows.append(
                (
                    "species_core",
                    str(block.get("section_hint", "core") or "core"),
                    int(block.get("page_number", 0) or 0),
                    str(block.get("section_hint", "") or ""),
                    str(block.get("text_content", "") or ""),
                    float(self._extract_score_from_reason(block.get("selection_reason", ""))),
                    str(block.get("selection_reason", "") or ""),
                )
            )

        for block in candidate.get("extended_blocks", []):
            evidence_rows.append(
                (
                    "species_extended",
                    str(block.get("section_hint", "extended") or "extended"),
                    int(block.get("page_number", 0) or 0),
                    str(block.get("section_hint", "") or ""),
                    str(block.get("text_content", "") or ""),
                    float(self._extract_score_from_reason(block.get("selection_reason", ""))),
                    str(block.get("selection_reason", "") or ""),
                )
            )

        for row in evidence_rows:
            cursor.execute(
                """
                INSERT INTO figure_evidence (
                    figure_id, evidence_level, evidence_type, page_number,
                    section_title, text_content, match_score, selection_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (figure_id, *row),
            )

    def _extract_score_from_reason(self, selection_reason: Any) -> float:
        text = str(selection_reason or "")
        match = re.search(r"([0-9]+\.[0-9]+)", text)
        if not match:
            return 0.0
        try:
            return float(match.group(1))
        except ValueError:
            return 0.0

    # ------------------------------------------------------------------
    # Geometry / file helpers
    # ------------------------------------------------------------------
    def _calculate_file_hash(self, file_path: Path) -> str:
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as handle:
            for chunk in iter(lambda: handle.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def _union_rects(self, rects: List[fitz.Rect]) -> fitz.Rect:
        x0 = min(rect.x0 for rect in rects)
        y0 = min(rect.y0 for rect in rects)
        x1 = max(rect.x1 for rect in rects)
        y1 = max(rect.y1 for rect in rects)
        return fitz.Rect(x0, y0, x1, y1)

    def _expand_rect(self, rect: fitz.Rect, padding: float, page_rect: fitz.Rect | None = None) -> fitz.Rect:
        expanded = fitz.Rect(rect.x0 - padding, rect.y0 - padding, rect.x1 + padding, rect.y1 + padding)
        if page_rect is None:
            return expanded
        return fitz.Rect(
            max(page_rect.x0, expanded.x0),
            max(page_rect.y0, expanded.y0),
            min(page_rect.x1, expanded.x1),
            min(page_rect.y1, expanded.y1),
        )

    def _rect_area(self, rect: fitz.Rect) -> float:
        return max(0.0, float(rect.width)) * max(0.0, float(rect.height))

    def _rect_to_payload(self, rect: fitz.Rect) -> Dict[str, float]:
        return {
            "x0": round(float(rect.x0), 3),
            "y0": round(float(rect.y0), 3),
            "x1": round(float(rect.x1), 3),
            "y1": round(float(rect.y1), 3),
            "width": round(float(rect.width), 3),
            "height": round(float(rect.height), 3),
        }

    def _hash_candidate(self, page_number: int, figure_index: int, bbox: fitz.Rect, cluster: List[Dict[str, Any]]) -> str:
        payload = {
            "page_number": page_number,
            "figure_index": figure_index,
            "bbox": self._rect_to_payload(bbox),
            "source_rects": [self._rect_to_payload(entry["rect"]) for entry in cluster],
        }
        return hashlib.md5(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    def _generate_figure_filename(
        self,
        pdf_filename: str,
        page_number: int,
        figure_index: int,
        caption_block: Dict[str, Any] | None,
        figure_hash: str,
    ) -> str:
        pdf_prefix = re.sub(r"[^A-Za-z0-9_\-]+", "_", Path(pdf_filename).stem)[:40].strip("_") or "pdf"
        if caption_block:
            caption = str(caption_block.get("text_content", "") or "")
            caption = re.sub(r"[^A-Za-z0-9_\-\s]+", "", caption).strip().replace(" ", "_")[:48]
        else:
            caption = "figure"
        return f"{pdf_prefix}_p{page_number:03d}_f{figure_index:03d}_{caption}_{figure_hash[:8]}.png"

    def _save_figure_clip(self, page: fitz.Page, bbox: fitz.Rect, file_path: str) -> None:
        matrix = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=matrix, clip=bbox, alpha=False)
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        pix.save(file_path)

    def _has_auxiliary_inset(self, cluster: List[Dict[str, Any]], caption_text: str, figure_local_text: str) -> bool:
        if len(cluster) <= 1:
            text_blob = f"{caption_text}\n{figure_local_text}".lower()
            return any(token in text_blob for token in self.auxiliary_terms)
        max_area = max(entry["area"] for entry in cluster)
        small_count = sum(1 for entry in cluster if entry["area"] < max_area * 0.25)
        if small_count > 0:
            return True
        text_blob = f"{caption_text}\n{figure_local_text}".lower()
        return any(token in text_blob for token in self.auxiliary_terms)
