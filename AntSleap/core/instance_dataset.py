"""Frozen, grouped datasets for object detection, classification and masks."""
from __future__ import annotations

import json
import math
import random
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

from .instance_project import InstanceProject, decode_mask, digest, encode_mask, uid
from .safe_io import atomic_write_json


class FrozenInstanceDataset:
    """Detach immutable input from the UI-owned SQLite connection for background export."""
    def __init__(self, project):
        self.root = project.root
        self.project_id = project.project_id
        self._snapshot = project.snapshot()

    def snapshot(self):
        import copy
        return copy.deepcopy(self._snapshot)

    image_path = InstanceProject.image_path
    trusted = staticmethod(InstanceProject.trusted)


def mask_polygon(rle):
    """YOLO cannot represent holes/disconnected regions; refuse lossy conversion."""
    import cv2
    mask = decode_mask(rle)
    contours, hierarchy = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    if len(contours) != 1 or hierarchy is None or len(contours[0]) < 3:
        raise ValueError("YOLO 分割不能无损表示此掩膜，请导出 COCO RLE")
    return contours[0].reshape(-1, 2).tolist()


def partition_images(snapshot, ratios=(0.8, 0.1, 0.1), seed=20261102):
    if len(ratios) != 3 or any(x < 0 for x in ratios) or not math.isclose(sum(ratios), 1.0):
        raise ValueError("划分比例必须非负且总和为 1")
    parent = {i["id"]: i["id"] for i in snapshot["images"]}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    owners = {}
    pairs = []
    for image in snapshot["images"]:
        pairs.extend((image["id"], tag) for tag in ("hash:" + image["source_hash"],
                     "pixels:" + image.get("hash", image["source_hash"]),
                     "group:" + image["source_group"] if image.get("source_group") else "") if tag)
    for item in snapshot["instances"]:
        if item.get("specimen_id"):
            pairs.append((item["image_id"], "specimen:" + item["specimen_id"]))
    for key, tag in pairs:
        if tag in owners:
            parent[find(key)] = find(owners[tag])
        else:
            owners[tag] = key
    groups = defaultdict(list)
    for key in parent:
        groups[find(key)].append(key)
    blocks = sorted(groups.values(), key=lambda b: sorted(b))
    random.Random(seed).shuffle(blocks)
    targets = [len(parent) * x for x in ratios]
    counts = [0, 0, 0]
    result = {}
    for block in blocks:
        slot = max((j for j in range(3) if ratios[j] > 0), key=lambda j: targets[j] - counts[j])
        counts[slot] += len(block)
        for key in block:
            result[key] = ("train", "val", "test")[slot]
    return result


def export_dataset(project, output, *, task="detect", format="coco", ratios=(0.8, 0.1, 0.1), seed=20261102, cancel_check=None):
    if task not in {"detect", "segment", "classify"} or format not in {"coco", "yolo", "classification"}:
        raise ValueError("不支持的任务或格式")
    if (task == "classify") != (format == "classification"):
        raise ValueError("分类任务必须使用分类目录格式")
    snapshot = project.snapshot()
    partitions = partition_images(snapshot, ratios, seed)
    categories = sorted(snapshot["categories"], key=lambda c: c["id"])
    mapping = {c["id"]: n for n, c in enumerate(categories)}
    if not mapping:
        raise ValueError("项目没有物种类别")
    by_image = defaultdict(list)
    for record in snapshot["instances"]:
        by_image[record["image_id"]].append(record)
    destination = Path(output).resolve() / uid("export")
    destination.mkdir(parents=True)
    atomic_write_json(destination / "INCOMPLETE.json", {"project_id": project.project_id})
    report = {"task": task, "format": format, "images": 0, "instances": 0, "negative_images": 0,
              "excluded": [], "coverage": {p: {} for p in ("train", "val", "test")}, "seed": seed}
    provenance = []
    coco = {s: {"images": [], "annotations": [], "categories": [{"id": n + 1, "name": c["name"], "supercategory": "taxon"} for n, c in enumerate(categories)]} for s in ("train", "val", "test")}
    for image_number, image in enumerate(snapshot["images"], 1):
        if cancel_check and cancel_check():
            raise InterruptedError("导出已取消；未完成目录保留 INCOMPLETE 标记，可安全删除")
        items = by_image[image["id"]]
        reason = None
        if image["review"] == "excluded":
            reason = "暂不用于训练"
        elif task != "classify" and (image["review"] not in {"complete", "confirmed_empty"} or any(not project.trusted(r) for r in items)):
            reason = "整图未完整检查或仍有待确认对象"
        elif task == "segment" and any(not r.get("mask") for r in items):
            reason = "仍有仅画框个体，分割标注不完整"
        try:
            path = project.image_path(image)
            if not path.is_file() or digest(path) != image["hash"]:
                reason = "图片缺失或内容变更"
        except ValueError:
            reason = "图片路径无效"
        if reason:
            report["excluded"].append({"image_id": image["id"], "reason": reason})
            continue
        split = partitions[image["id"]]
        selected = [r for r in items if project.trusted(r)]
        with Image.open(path) as source:
            rgb = source.convert("RGB")
            if task == "classify":
                written = 0
                for item in selected:
                    x1, y1, x2, y2 = item["box"]
                    x1, y1, x2, y2 = math.floor(x1), math.floor(y1), math.ceil(x2), math.ceil(y2)
                    # A second individual intersects this crop: never silently label it single-class.
                    if any(other["id"] != item["id"] and min(x2, other["box"][2]) > max(x1, other["box"][0])
                           and min(y2, other["box"][3]) > max(y1, other["box"][1]) for other in items):
                        report["excluded"].append({"instance_id": item["id"], "reason": "分类裁剪含其他已标注个体"})
                        continue
                    crop_path = destination / "dataset" / split / item["category_id"] / f"{item['id']}.png"
                    crop_path.parent.mkdir(parents=True, exist_ok=True)
                    rgb.crop((math.floor(x1), math.floor(y1), math.ceil(x2), math.ceil(y2))).save(crop_path)
                    written += 1
                    report["coverage"][split][item["category_id"]] = report["coverage"][split].get(item["category_id"], 0) + 1
                    provenance.append({"image_id": image["id"], "instance_id": item["id"], "crop": [x1, y1, x2, y2], "split": split})
                report["instances"] += written
                report["images"] += int(written > 0)
                continue
            image_path = destination / "dataset" / "images" / split / f"{image['id']}.png"
            image_path.parent.mkdir(parents=True, exist_ok=True)
            rgb.save(image_path)
        report["images"] += 1
        report["negative_images"] += int(not selected)
        coco[split]["images"].append({"id": image_number, "file_name": f"images/{split}/{image['id']}.png", "width": image["width"], "height": image["height"]})
        lines = []
        for item in selected:
            n = mapping[item["category_id"]]
            x1, y1, x2, y2 = item["box"]
            annotation = {"id": len(coco[split]["annotations"]) + 1, "image_id": image_number, "category_id": n + 1,
                          "bbox": [x1, y1, x2 - x1, y2 - y1], "area": (x2 - x1) * (y2 - y1), "iscrowd": 0}
            if task == "segment":
                annotation["segmentation"] = item["mask"]
                annotation["area"] = int(decode_mask(item["mask"]).sum())
            coco[split]["annotations"].append(annotation)
            if format == "yolo":
                if task == "segment":
                    coords = [v / (image["width"] if j % 2 == 0 else image["height"]) for p in mask_polygon(item["mask"]) for j, v in enumerate(p)]
                else:
                    coords = [(x1 + x2) / 2 / image["width"], (y1 + y2) / 2 / image["height"], (x2 - x1) / image["width"], (y2 - y1) / image["height"]]
                lines.append(str(n) + " " + " ".join(f"{v:.10g}" for v in coords))
            report["instances"] += 1
            report["coverage"][split][item["category_id"]] = report["coverage"][split].get(item["category_id"], 0) + 1
            provenance.append({"image_id": image["id"], "instance_id": item["id"], "annotation_id": annotation["id"], "split": split})
        if format == "yolo":
            label = destination / "dataset" / "labels" / split / f"{image['id']}.txt"
            label.parent.mkdir(parents=True, exist_ok=True)
            label.write_text("\n".join(lines), encoding="utf-8")
    for split, payload in coco.items():
        if format == "coco":
            atomic_write_json(destination / "dataset" / f"{split}.json", payload)
    if format == "yolo":
        import yaml
        data = {"path": str(destination / "dataset"), "train": "images/train", "val": "images/val", "test": "images/test", "names": {i: c["id"] for i, c in enumerate(categories)}}
        (destination / "dataset" / "data.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    atomic_write_json(destination / "snapshot.json", snapshot)
    atomic_write_json(destination / "category_map.json", categories)
    atomic_write_json(destination / "split_manifest.json", partitions)
    atomic_write_json(destination / "export_report.json", report)
    (destination / "provenance.jsonl").write_text("\n".join(json.dumps(p, ensure_ascii=False) for p in provenance), encoding="utf-8")
    (destination / "export_report_zh.md").write_text(f"# 数据集导出报告\n\n任务：{task}；图片：{report['images']}；实例：{report['instances']}；负样本图片：{report['negative_images']}。\n\n排除记录：{len(report['excluded'])}。分组实际覆盖见 export_report.json，未保证每类都有独立验证/测试样本。\n\n本目录含本地来源快照，分享前应检查并去除私有路径与备注。\n", encoding="utf-8")
    atomic_write_json(destination / "input_fingerprints.json", {
        p.relative_to(destination).as_posix(): digest(p)
        for p in destination.rglob("*") if p.is_file() and p.name != "INCOMPLETE.json"
    })
    atomic_write_json(destination / "COMPLETE.json", {"task": task, "format": format, "project_id": snapshot["project_id"], "revision": snapshot["revision"], "snapshot_hash": digest(destination / "snapshot.json")})
    (destination / "INCOMPLETE.json").unlink()
    return destination, report


def import_coco(project, annotation_file, image_root):
    """Validate complete batch before mutating; imports are always drafts."""
    from .instance_project import polygon_mask, mask_box
    payload = json.loads(Path(annotation_file).read_text(encoding="utf-8"))
    root = Path(image_root).resolve()
    for table in ("categories", "images", "annotations"):
        records = payload[table]
        if not isinstance(records, list) or any(not isinstance(r, dict) or "id" not in r for r in records):
            raise ValueError("COCO 记录必须包含 ID：" + table)
        if len({r["id"] for r in records}) != len(records):
            raise ValueError("COCO 包含重复 ID：" + table)
    cats = {c["id"]: c["name"] for c in payload["categories"]}
    images = {i["id"]: i for i in payload["images"]}
    parsed = []
    for info in images.values():
        path = (root / info["file_name"]).resolve()
        if not path.is_relative_to(root):
            raise ValueError("导入图像路径越过所选目录")
        with Image.open(path) as image:
            if image.size != (info["width"], info["height"]) or image.getexif().get(274, 1) != 1:
                raise ValueError("COCO 尺寸/方向与图片不一致，请先统一方向")
        info["resolved"] = path
    for item in payload["annotations"]:
        info = images[item["image_id"]]
        if item["category_id"] not in cats or item.get("iscrowd"):
            raise ValueError("未知类别或 crowd 标注需要先人工拆分")
        x, y, w, h = map(float, item["bbox"])
        if not all(math.isfinite(v) for v in (x, y, w, h)) or not (w > 0 and h > 0 and x >= 0 and y >= 0 and x + w <= info["width"] and y + h <= info["height"]):
            raise ValueError("导入框越界或为空")
        segmentation = item.get("segmentation")
        mask = None
        if isinstance(segmentation, dict):
            mask = encode_mask(decode_mask(segmentation))
        elif segmentation:
            combined = np.zeros((info["height"], info["width"]), np.uint8)
            for poly in segmentation:
                if len(poly) % 2:
                    raise ValueError("多边形坐标不成对")
                combined |= decode_mask(polygon_mask(list(zip(poly[::2], poly[1::2])), info["width"], info["height"]))
            mask = encode_mask(combined)
        if mask and mask["size"] != [info["height"], info["width"]]:
            raise ValueError("导入掩膜尺寸不匹配")
        parsed.append((item, mask, mask_box(mask) if mask else [x, y, x + w, y + h]))
    batch_hash = digest(annotation_file)
    existing = project.records("instances")
    if any(r.get("import_batch") == batch_hash for r in existing):
        raise ValueError("该标注批次已导入，未重复添加")
    # Build the complete edit before writing; one transaction owns the whole batch.
    changes, category_ids, image_ids = [], {}, {}
    current_categories = {c["name"].casefold(): c["id"] for c in project.records("categories")}
    current_images = {i["source_hash"]: i["id"] for i in project.records("images")}
    added_files = []
    try:
        for key, name in cats.items():
            if not str(name).strip():
                raise ValueError("空类别名称")
            cid = current_categories.get(name.casefold())
            if not cid:
                cid = uid("category")
                current_categories[name.casefold()] = cid
                changes.append(("categories", cid, {"id": cid, "name": name, "rank": "species", "identification_status": "provisional"}))
            category_ids[key] = cid
        media = project.root / "media"
        media.mkdir(exist_ok=True)
        for key, info in images.items():
            fingerprint = digest(info["resolved"])
            iid = current_images.get(fingerprint)
            if iid:
                if any(r["id"] == iid for r in project.records("images")):
                    changes.append(project._dirty_image(iid))
            else:
                iid = uid("image")
                output = media / f"{iid}.png"
                with Image.open(info["resolved"]) as im:
                    im.convert("RGB").save(output)
                added_files.append(output)
                current_images[fingerprint] = iid
                changes.append(("images", iid, {"id": iid, "name": info["file_name"], "path": output.relative_to(project.root).as_posix(), "source_path": str(info["resolved"]), "source_hash": fingerprint, "hash": digest(output), "width": info["width"], "height": info["height"], "source_group": "", "review": "in_progress", "revision": 1}))
            image_ids[key] = iid
        for item, mask, box in parsed:
            key = uid("instance")
            record = {"id": key, "image_id": image_ids[item["image_id"]], "category_id": category_ids[item["category_id"]], "box": box, "mask": mask, "source": "import", "review": "draft", "revision": 1, "import_batch": batch_hash, "external_id": item["id"]}
            changes.append(("instances", key, record))
        project.change("import_coco", changes)
    except Exception:
        for path in added_files:
            path.unlink(missing_ok=True)
        raise
    return len(parsed)


def import_directory(project, folder, *, task="detect"):
    """Normalize YOLO or class folders into the validated COCO import transaction."""
    root = Path(folder).resolve()
    payload = {"images": [], "categories": [], "annotations": []}
    if task not in {"detect", "segment", "classify"}:
        raise ValueError("不支持的导入任务")
    if task == "classify":
        class_roots = [p for p in root.iterdir() if p.is_dir()]
        if any(p.name in {"train", "val", "test"} for p in class_roots):
            class_roots = [c for split in class_roots if split.name in {"train", "val", "test"} for c in split.iterdir() if c.is_dir()]
        names = sorted({p.name for p in class_roots})
        payload["categories"] = [{"id": i, "name": name} for i, name in enumerate(names)]
        pairs = [(p, names.index(c.name)) for c in class_roots for p in sorted(c.rglob("*")) if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".webp"}]
    else:
        import yaml
        configs = [p for p in (root / "data.yaml", root / "dataset.yaml") if p.is_file()]
        if not configs:
            raise ValueError("YOLO 根目录需要 data.yaml 或 dataset.yaml")
        data = yaml.safe_load(configs[0].read_text(encoding="utf-8"))
        names = data["names"]
        names = dict(enumerate(names)) if isinstance(names, list) else {int(k): v for k, v in names.items()}
        payload["categories"] = [{"id": i, "name": str(name)} for i, name in names.items()]
        pairs = [(p, None) for p in sorted((root / "images").rglob("*")) if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".webp"}]
    if not pairs:
        raise ValueError("目录中没有可导入图片")
    for image_number, (path, class_id) in enumerate(pairs, 1):
        with Image.open(path) as im:
            w, h = im.size
        payload["images"].append({"id": image_number, "file_name": path.relative_to(root).as_posix(), "width": w, "height": h})
        if task == "classify":
            payload["annotations"].append({"id": len(payload["annotations"]) + 1, "image_id": image_number,
                                           "category_id": class_id, "bbox": [0, 0, w, h]})
            continue
        label = root / "labels" / path.relative_to(root / "images").with_suffix(".txt")
        if not label.is_file():
            continue  # imported image remains unreviewed, never an implicit negative
        for line in label.read_text(encoding="utf-8-sig").splitlines():
            if not line.strip():
                continue
            fields = line.split()
            cid = int(fields[0])
            values = [float(v) for v in fields[1:]]
            if any(not math.isfinite(v) or not 0 <= v <= 1 for v in values):
                raise ValueError("YOLO 坐标必须在 0–1 范围")
            item = {"id": len(payload["annotations"]) + 1, "image_id": image_number, "category_id": cid}
            if task == "detect":
                if len(values) != 4:
                    raise ValueError("检测标签每行必须为类别加四个坐标")
                cx, cy, bw, bh = values
                item["bbox"] = [(cx - bw/2)*w, (cy - bh/2)*h, bw*w, bh*h]
            else:
                if len(values) < 6 or len(values) % 2:
                    raise ValueError("分割标签至少需要三个点")
                poly = [v * (w if j % 2 == 0 else h) for j, v in enumerate(values)]
                xs, ys = poly[::2], poly[1::2]
                item["bbox"] = [min(xs), min(ys), max(xs)-min(xs), max(ys)-min(ys)]
                item["segmentation"] = [poly]
            payload["annotations"].append(item)
    folder = project.root / "imports" / uid("batch")
    folder.mkdir(parents=True)
    normalized = folder / "normalized_coco.json"
    atomic_write_json(normalized, payload)
    try:
        count = import_coco(project, normalized, root)
    except Exception as exc:
        atomic_write_json(folder / "report.json", {"status": "failed", "error": str(exc)})
        raise
    atomic_write_json(folder / "report.json", {"status": "completed", "instances": count, "task": task})
    return count
