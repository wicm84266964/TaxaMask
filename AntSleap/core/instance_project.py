"""Transactional instance annotations; deliberately independent of part labels."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from .safe_io import AdvisoryFileLock, atomic_write_json
from .sqlite_storage import connect_sqlite_database, connect_sqlite_database_readonly

PROJECT_KIND = "species_instances_2d"
MANIFEST_VERSION = "taxamask-instance-project-v1"


def uid(prefix):
    return f"{prefix}_{uuid.uuid4().hex}"


def digest(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def encode_mask(mask):
    a = (np.asarray(mask) != 0).astype(np.uint8)
    if a.ndim != 2 or not a.any():
        raise ValueError("掩膜必须为非空二维区域")
    flat = a.ravel(order="F")
    cuts = np.flatnonzero(flat[1:] != flat[:-1]) + 1
    counts = np.diff(np.r_[0, cuts, flat.size]).tolist()
    if flat[0]:
        counts.insert(0, 0)
    return {"size": list(a.shape), "counts": counts}


def decode_mask(rle):
    h, w = map(int, rle["size"])
    counts = rle["counts"]
    if h <= 0 or w <= 0 or h * w > 250_000_000:
        raise ValueError("掩膜尺寸无效")
    if not isinstance(counts, list):
        from pycocotools import mask as coco_mask
        result = coco_mask.decode(rle)
        if result.shape != (h, w):
            raise ValueError("掩膜尺寸不匹配")
        return result.astype(np.uint8)
    if any(type(n) is not int or n < 0 for n in counts) or sum(counts) != h * w:
        raise ValueError("RLE 长度无效")
    return np.repeat(np.arange(len(counts)) % 2, counts).astype(np.uint8).reshape((h, w), order="F")


def polygon_mask(points, width, height):
    if len(points) < 3 or any(len(p) != 2 or not all(math.isfinite(float(v)) for v in p) for p in points):
        raise ValueError("轮廓至少需要三个有效顶点")
    if any(not (0 <= x <= width and 0 <= y <= height) for x, y in points):
        raise ValueError("轮廓超出图片")
    im = Image.new("L", (width, height))
    ImageDraw.Draw(im).polygon([tuple(p) for p in points], fill=1)
    return encode_mask(np.asarray(im))


def mask_box(rle):
    yy, xx = np.where(decode_mask(rle))
    if not len(xx):
        raise ValueError("掩膜为空")
    return [float(xx.min()), float(yy.min()), float(xx.max() + 1), float(yy.max() + 1)]


class InstanceProject:
    """Single writer, SQLite transactions, immutable revision events and undo."""

    def __init__(self, path, *, readonly=False):
        self.readonly = readonly
        self.path = Path(path).resolve()
        manifest = json.loads(self.path.read_text(encoding="utf-8"))
        if manifest.get("schema_version") != MANIFEST_VERSION or manifest.get("project_type") != PROJECT_KIND:
            raise ValueError("不是支持的物种与个体项目")
        self.root = self.path.parent
        db = (self.root / manifest["database"]).resolve()
        if db.parent != self.root or not db.is_file():
            raise ValueError("实例数据库缺失或路径无效")
        self.lock = AdvisoryFileLock(self.root / ".instance-writer.lock", trusted_root=self.root, timeout=0.1)
        if not readonly and not self.lock.acquire():
            raise ValueError("此项目已被其他窗口打开，请关闭原窗口后重试")
        self.connection = None
        try:
            self.connection = connect_sqlite_database_readonly(db) if readonly else connect_sqlite_database(db)
            self.connection.row_factory = sqlite3.Row
            if self.connection.execute("PRAGMA user_version").fetchone()[0] != 1:
                raise ValueError("不支持的实例数据库版本")
            meta = dict(self.connection.execute("SELECT key,value FROM meta"))
            if meta.get("project_id") != manifest["project_id"]:
                raise ValueError("项目入口与数据库身份不匹配")
            if self.connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("数据库完整性检查失败")
            self.project_id = meta["project_id"]
            self.name = meta["name"]
            self._undo, self._redo = [], []
            self._last_backup = 0.0
            # A previous process may have stopped before reporting its child outcome.
            if not readonly:
                with self.connection:
                    self.connection.execute("CREATE TABLE IF NOT EXISTS agent_requests(id TEXT PRIMARY KEY,result TEXT NOT NULL)")
                    for run in self.records("runs"):
                        if run.get("status") == "running":
                            run["status"] = "interrupted"
                            self._write("runs", run["id"], run)
        except Exception:
            self.close()
            raise

    @classmethod
    def create(cls, folder, name="物种与个体项目"):
        root = Path(folder).resolve()
        root.mkdir(parents=True, exist_ok=True)
        if any(root.iterdir()):
            raise ValueError("请选择一个空文件夹创建项目，避免覆盖现有材料")
        db = root / "annotations.sqlite"
        connection = connect_sqlite_database(db)
        project_id = uid("instance_project")
        try:
            with connection:
                connection.executescript('''
                    PRAGMA user_version=1;
                    CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                    CREATE TABLE categories(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
                    CREATE TABLE images(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
                    CREATE TABLE instances(id TEXT PRIMARY KEY,image_id TEXT NOT NULL REFERENCES images(id),
                        category_id TEXT REFERENCES categories(id),payload TEXT NOT NULL);
                    CREATE INDEX instance_image ON instances(image_id);
                    CREATE TABLE events(seq INTEGER PRIMARY KEY AUTOINCREMENT,time TEXT NOT NULL,
                        operation TEXT NOT NULL,before_json TEXT NOT NULL,after_json TEXT NOT NULL);
                    CREATE TABLE runs(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
                    CREATE TABLE agent_requests(id TEXT PRIMARY KEY,result TEXT NOT NULL);
                ''')
                connection.executemany("INSERT INTO meta VALUES (?,?)", [("project_id", project_id), ("name", name), ("revision", "0")])
        finally:
            connection.close()
        path = root / "project.instance.json"
        atomic_write_json(path, {"schema_version": MANIFEST_VERSION, "project_type": PROJECT_KIND,
                                 "project_id": project_id, "database": db.name})
        return cls(path)

    def close(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None
        self.lock.release()

    @property
    def revision(self):
        return int(self.connection.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0])

    def records(self, table, image_id=None):
        if table not in {"categories", "images", "instances", "runs"}:
            raise ValueError("无效记录类型")
        sql, params = f"SELECT payload FROM {table}", ()
        if image_id is not None:
            if table != "instances":
                raise ValueError("仅实例支持图像筛选")
            sql, params = sql + " WHERE image_id=?", (image_id,)
        return [json.loads(row[0]) for row in self.connection.execute(sql, params)]

    def get(self, table, key):
        if table not in {"categories", "images", "instances", "runs"}:
            raise ValueError("无效记录类型")
        row = self.connection.execute(f"SELECT payload FROM {table} WHERE id=?", (key,)).fetchone()
        if row is None:
            raise KeyError(key)
        return json.loads(row[0])

    def _write(self, table, key, value):
        if value is None:
            self.connection.execute(f"DELETE FROM {table} WHERE id=?", (key,))
        elif table == "instances":
            self.connection.execute("INSERT OR REPLACE INTO instances VALUES (?,?,?,?)",
                                    (key, value["image_id"], value.get("category_id"), json.dumps(value, ensure_ascii=False)))
        else:
            self.connection.execute(f"INSERT INTO {table} VALUES (?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload", (key, json.dumps(value, ensure_ascii=False)))

    def change(self, operation, changes, *, history=True, agent_result=None):
        if self.readonly:
            raise ValueError("只读项目不能修改标注")
        before, after = [], []
        if time.monotonic() - self._last_backup > 300:
            self.backup()
            self._last_backup = time.monotonic()
        with self.connection:
            for table, key, value in changes:
                if table not in {"categories", "images", "instances"}:
                    raise ValueError("非法编辑对象")
                try:
                    old = self.get(table, key)
                except KeyError:
                    old = None
                before.append((table, key, old))
                self._write(table, key, value)
                after.append((table, key, value))
            self.connection.execute("UPDATE meta SET value=CAST(value AS INTEGER)+1 WHERE key='revision'")
            self.connection.execute("INSERT INTO events(time,operation,before_json,after_json) VALUES (?,?,?,?)",
                                    (datetime.now(timezone.utc).isoformat(), operation, json.dumps(before), json.dumps(after)))
            if agent_result is not None:
                self.connection.execute("INSERT INTO agent_requests VALUES (?,?)", (agent_result[0], json.dumps(agent_result[1])))
        if history:
            self._undo.append((before, copy.deepcopy(after)))
            self._undo = self._undo[-100:]
            self._redo.clear()

    def undo(self):
        if self._undo:
            before, after = self._undo[-1]
            self.change("undo", list(reversed(before)), history=False)
            self._undo.pop()
            self._redo.append((before, after))

    def redo(self):
        if self._redo:
            before, after = self._redo[-1]
            self.change("redo", after, history=False)
            self._redo.pop()
            self._undo.append((before, after))

    def category(self, name, key=None):
        name = name.strip()
        if not name:
            raise ValueError("类别名不能为空")
        if any(c["name"].casefold() == name.casefold() and c["id"] != key for c in self.records("categories")):
            raise ValueError("类别名称已存在，请选择已有类别")
        record = self.get("categories", key) if key else {"id": uid("category"), "rank": "species", "identification_status": "provisional"}
        record["name"] = name
        self.change("category", [("categories", record["id"], record)])
        return record["id"]

    def merge_categories(self, source_id, target_id):
        if source_id == target_id:
            raise ValueError("不能合并到自身")
        source = self.get("categories", source_id)
        target = self.get("categories", target_id)
        target["aliases"] = sorted(set(target.get("aliases", []) + [source["name"]] + source.get("aliases", [])))
        changes = [("categories", target_id, target)]
        affected = set()
        for record in self.records("instances"):
            if record.get("category_id") == source_id:
                record.update(category_id=target_id, review="draft", revision=record["revision"] + 1)
                changes.append(("instances", record["id"], record))
                affected.add(record["image_id"])
        changes.extend(self._dirty_image(i) for i in affected)
        changes.append(("categories", source_id, None))
        self.change("merge_categories", changes)

    def remove_category(self, category_id):
        if any(r.get("category_id") == category_id for r in self.records("instances")):
            raise ValueError("类别仍被个体引用，请先改类或合并")
        self.get("categories", category_id)
        self.change("remove_category", [("categories", category_id, None)])

    def import_images(self, paths, *, source_group="", provenance=None):
        created, errors = [], []
        known = {r["source_hash"] for r in self.records("images")}
        media = self.root / "media"
        media.mkdir(exist_ok=True)
        changes = []
        for path in paths:
            output = None
            try:
                path = Path(path).resolve()
                source_hash = digest(path)
                if source_hash in known:
                    continue
                with Image.open(path) as source:
                    if getattr(source, "n_frames", 1) != 1:
                        raise ValueError("多帧/体数据请使用 TIF 工作台")
                    oriented = ImageOps.exif_transpose(source).convert("RGB")
                    key = uid("image")
                    output = media / f"{key}.png"
                    oriented.save(output)
                    width, height = oriented.size
                record = {"id": key, "name": path.name, "path": output.relative_to(self.root).as_posix(),
                          "source_path": str(path), "source_hash": source_hash, "hash": digest(output),
                          "width": width, "height": height, "source_group": source_group,
                          "provenance": provenance or {}, "review": "unreviewed", "revision": 0}
                changes.append(("images", key, record))
                created.append(key)
                known.add(source_hash)
            except Exception as exc:
                if output is not None:
                    output.unlink(missing_ok=True)
                errors.append({"path": str(path), "error": str(exc)})
        if changes:
            try:
                self.change("import_images", changes)
            except Exception:
                for _, _, record in changes:
                    (self.root / record["path"]).unlink(missing_ok=True)
                raise
        return created, errors

    def image_path(self, record):
        path = (self.root / record["path"]).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("图像路径越过项目目录")
        return path

    def _dirty_image(self, image_id):
        image = self.get("images", image_id)
        image["review"] = "in_progress"
        image["revision"] += 1
        return ("images", image_id, image)

    def put_instance(self, image_id, category_id, box=None, *, mask=None, key=None, source="manual", specimen_id="", expected_revision=None, changes=None, score=None):
        image = self.get("images", image_id)
        if category_id:
            self.get("categories", category_id)
        old = self.get("instances", key) if key else None
        if old and (old["image_id"] != image_id or expected_revision is not None and old["revision"] != expected_revision):
            raise ValueError("实例已变更，请重新选择")
        if mask is not None:
            if mask["size"] != [image["height"], image["width"]]:
                raise ValueError("掩膜与图片尺寸不同")
            box = mask_box(mask)
        if box is None or len(box) != 4 or not all(math.isfinite(float(x)) for x in box):
            raise ValueError("无效标注框")
        x1, y1, x2, y2 = map(float, box)
        if not (0 <= x1 < x2 <= image["width"] and 0 <= y1 < y2 <= image["height"]):
            raise ValueError("标注框为空或超出图片边界")
        record = {"id": key or uid("instance"), "image_id": image_id, "category_id": category_id,
                  "box": [x1, y1, x2, y2], "mask": copy.deepcopy(mask), "source": source,
                  "geometry_source": source, "class_source": source if source in {"model", "external_model", "agent", "import"} else "manual",
                  "review": "draft", "revision": (old["revision"] + 1) if old else 1,
                  "specimen_id": specimen_id or (old or {}).get("specimen_id", "")}
        if score is not None:
            if not math.isfinite(score) or not 0 <= score <= 1:
                raise ValueError("无效置信度")
            record["score"] = score
        edit = [("instances", record["id"], record), self._dirty_image(image_id)]
        if changes is not None:
            changes.extend(edit)
        else:
            self.change("instance_edit", edit)
        return record["id"]

    def batch(self, keys, operation, category_id=None):
        if operation not in {"confirm", "delete", "reclassify"}:
            raise ValueError("未知操作")
        if operation == "reclassify":
            self.get("categories", category_id)
        changes, images = [], set()
        for key in dict.fromkeys(keys):
            record = self.get("instances", key)
            images.add(record["image_id"])
            if operation == "confirm":
                if not record.get("category_id"):
                    raise ValueError("未鉴定对象不能确认成物种训练标签")
                record["review"] = "confirmed"
                record["reviewed_revision"] = record["revision"]
                record["confirmed_at"] = datetime.now(timezone.utc).isoformat()
                record["accepted_via"] = "human_review"
            elif operation == "reclassify":
                record.update(category_id=category_id, class_source="manual", review="draft", revision=record["revision"] + 1)
            changes.append(("instances", key, None if operation == "delete" else record))
        if changes:
            changes.extend(self._dirty_image(i) for i in sorted(images))
            self.change(operation, changes)

    def review_image(self, image_id, status):
        if status not in {"complete", "confirmed_empty", "excluded"}:
            raise ValueError("无效整图状态")
        items = self.records("instances", image_id)
        if status == "confirmed_empty" and items:
            raise ValueError("图片仍有实例，不能确认无目标")
        if status == "complete" and (not items or any(not self.trusted(r) for r in items)):
            raise ValueError("请先确认所有个体；无目标图片请使用确认无目标")
        image = self.get("images", image_id)
        image["review"] = status
        self.change("image_review", [("images", image_id, image)])

    @staticmethod
    def trusted(record):
        return bool(record.get("category_id") and record.get("review") == "confirmed"
                    and record.get("reviewed_revision") == record.get("revision"))

    def snapshot(self):
        with self.connection:
            # BEGIN explicitly: a SELECT alone does not start a Python sqlite transaction.
            self.connection.execute("BEGIN")
            return {"project_id": self.project_id, "revision": self.revision,
                    **{t: self.records(t) for t in ("categories", "images", "instances")}}

    def backup(self):
        directory = self.root / "backups"
        directory.mkdir(exist_ok=True)
        target = directory / f"annotations-{uid('backup')}.sqlite"
        out = sqlite3.connect(target)
        try:
            self.connection.backup(out)
        finally:
            out.close()
        return target

    def restore_backup(self, path):
        """Validate first, preserve the current database, then restore transactionally."""
        backup = Path(path).resolve()
        if not backup.is_file():
            raise ValueError("备份文件不存在")
        source = sqlite3.connect(backup.as_uri() + "?mode=ro", uri=True)
        try:
            if source.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("备份数据库损坏")
            meta = dict(source.execute("SELECT key,value FROM meta"))
            if meta.get("project_id") != self.project_id or source.execute("PRAGMA user_version").fetchone()[0] != 1:
                raise ValueError("备份不是当前项目或版本不兼容")
            old_revision = self.revision
            self.backup()
            source.backup(self.connection)
            # Do not silently promote restored annotations back to training truth.
            changes = []
            for record in self.records("instances"):
                record.update(review="draft", revision=record["revision"] + 1)
                changes.append(("instances", record["id"], record))
            changes.extend(self._dirty_image(image["id"]) for image in self.records("images"))
            with self.connection:
                self.connection.execute("UPDATE meta SET value=? WHERE key='revision'", (str(max(old_revision, self.revision) + 1),))
            self.change("restore_requires_review", changes, history=False)
            self._undo.clear()
            self._redo.clear()
        finally:
            source.close()

    def record_run(self, record):
        with self.connection:
            self._write("runs", record["id"], record)

    def settings(self):
        row = self.connection.execute("SELECT value FROM meta WHERE key='settings'").fetchone()
        return json.loads(row[0]) if row else {}

    def set_settings(self, settings):
        with self.connection:
            self.connection.execute("INSERT INTO meta VALUES ('settings',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (json.dumps(settings, ensure_ascii=False),))
