"""Restricted agent API: read snapshots, export, or queue draft-only proposals."""
from __future__ import annotations

import json
import hashlib
import re
from pathlib import Path

from .instance_project import uid
from .safe_io import atomic_write_json

REQUEST_SCHEMA = "taxamask-instance-agent-request-v1"
RESULT_SCHEMA = "taxamask-instance-agent-result-v1"
MAX_REQUEST_BYTES = 16 * 1024 * 1024


def capabilities():
    return {"schema_version": "taxamask-instance-agent-capabilities-v1",
            "project_type": "species_instances_2d", "actions": ["inspect", "validate", "export", "propose_instances", "train", "predict"],
            "write_policy": "draft_only", "human_confirmation": "workbench_only",
            "cli": "tools/agentic/instance_workbench.py",
            "contract": "docs/contracts/instance_agent_contract_zh.md"}


def inspect_project(project):
    snapshot = project.snapshot()
    return {"capabilities": capabilities(), "project_id": project.project_id, "revision": snapshot["revision"],
            "categories": snapshot["categories"], "images": snapshot["images"], "instances": snapshot["instances"],
            "model_configuration": {"backend": project.settings().get("backend", "builtin"),
                                    "external_configured": bool(project.settings().get("external_backend"))}}


def validate_project(project):
    from .instance_project import digest, decode_mask
    issues = []
    for image in project.records("images"):
        try:
            if digest(project.image_path(image)) != image["hash"]:
                raise ValueError("图像内容已变化")
        except Exception as exc:
            issues.append({"image_id": image["id"], "reason": str(exc)})
    for record in project.records("instances"):
        if record.get("mask"):
            try:
                decode_mask(record["mask"])
            except Exception as exc:
                issues.append({"instance_id": record["id"], "reason": str(exc)})
    return {"project_id": project.project_id, "revision": project.revision, "issues": issues, "valid": not issues}


def validate_envelope(request, project, *, check_revision=True):
    expected_keys = {"schema_version", "request_id", "project_id", "expected_revision", "action", "instances"}
    if not isinstance(request, dict) or set(request) != expected_keys or request["schema_version"] != REQUEST_SCHEMA:
        raise ValueError("智能体请求契约无效或包含不支持字段")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", str(request["request_id"])):
        raise ValueError("请求 ID 无效")
    if request["project_id"] != project.project_id or (check_revision and request["expected_revision"] != project.revision):
        raise ValueError("项目或修订已变化，请重新读取上下文")
    if request["action"] != "propose_instances":
        raise ValueError("智能体不能确认真值、删除标注或直接修改项目配置")
    if not isinstance(request["instances"], list) or not 1 <= len(request["instances"]) <= 10000:
        raise ValueError("候选实例数量必须为 1–10000")
    return request


def request_hash(request):
    return hashlib.sha256(json.dumps(request, sort_keys=True, allow_nan=False).encode()).hexdigest()


def previous_result(project, request):
    validate_envelope(request, project, check_revision=False)
    previous = project.connection.execute("SELECT result FROM agent_requests WHERE id=?", (request["request_id"],)).fetchone()
    if previous:
        result = json.loads(previous[0])
        if result.get("request_hash") != request_hash(request):
            raise ValueError("请求 ID 已被不同内容使用")
        return result


def submit_request(project, request):
    previous = previous_result(project, request)
    if previous:
        return previous
    validate_envelope(request, project)
    root = project.root / "agent_requests"
    pending = root / "pending"
    pending.mkdir(parents=True, exist_ok=True)
    request_id = request["request_id"]
    target = pending / f"{request_id}.json"
    completed = root / "results" / f"{request_id}.json"
    if completed.exists():
        return json.loads(completed.read_text(encoding="utf-8"))
    if target.exists():
        if json.loads(target.read_text(encoding="utf-8")) != request:
            raise ValueError("请求 ID 已被不同内容使用")
    else:
        atomic_write_json(target, request)
    return {"schema_version": RESULT_SCHEMA, "request_id": request_id, "status": "queued", "result_file": str(completed)}


def apply_request(project, request):
    previous = previous_result(project, request)
    if previous:
        return previous
    validate_envelope(request, project)
    changes, ids = [], []
    checked_images = set()
    for candidate in request["instances"]:
        if not isinstance(candidate, dict) or set(candidate) - {"image_id", "category_id", "bbox_xyxy", "mask_rle", "score"}:
            raise ValueError("候选只能包含图像/类别、几何与置信度；不允许写确认状态")
        if candidate["image_id"] not in checked_images:
            from .instance_project import digest
            image = project.get("images", candidate["image_id"])
            if digest(project.image_path(image)) != image["hash"]:
                raise ValueError("原图已变化，拒绝应用智能体候选")
            checked_images.add(candidate["image_id"])
        ids.append(project.put_instance(candidate["image_id"], candidate.get("category_id"), candidate.get("bbox_xyxy"),
                                        mask=candidate.get("mask_rle"), source="agent", changes=changes, score=candidate.get("score")))
    result = {"schema_version": RESULT_SCHEMA, "request_id": request["request_id"], "status": "applied_as_drafts",
              "request_hash": request_hash(request),
              "instance_ids": ids, "project_id": project.project_id, "revision": project.revision + 1}
    project.change("agent_proposals", changes, agent_result=(request["request_id"], result))
    return result


def process_inbox(project):
    pending = project.root / "agent_requests" / "pending"
    if not pending.exists():
        return []
    results = []
    output = project.root / "agent_requests" / "results"
    output.mkdir(exist_ok=True)
    for path in sorted(pending.glob("*.json"))[:10]:
        try:
            if path.is_symlink() or path.stat().st_size > MAX_REQUEST_BYTES:
                raise ValueError("请求文件大小或路径无效")
            request = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(request, dict) or request.get("request_id") != path.stem:
                raise ValueError("请求文件名与 ID 不匹配")
            result = apply_request(project, request)
        except Exception as exc:
            result = {"schema_version": RESULT_SCHEMA, "request_id": path.stem, "status": "rejected", "error": str(exc)}
        atomic_write_json(output / path.name, result)
        path.unlink()
        results.append(result)
    return results
