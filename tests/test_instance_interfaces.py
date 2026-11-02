import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from AntSleap.core.instance_project import InstanceProject, digest
from AntSleap.core.instance_agent import REQUEST_SCHEMA, submit_request, process_inbox, apply_request, inspect_project
from AntSleap.core.instance_external_backend import (CONTRACT_SCHEMA, PREDICTION_SCHEMA, MODEL_SCHEMA,
    category_hash, sanitize_instance_backend, validate_prediction, external_predict, external_train)


class InstanceInterfaceTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / ".tmp_validation"
        root.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = InstanceProject.create(self.root / "project")
        self.addCleanup(self.project.close)
        self.category = self.project.category("Example species")
        source = self.root / "source.png"
        Image.new("RGB", (40, 30), "green").save(source)
        self.image_id = self.project.import_images([source])[0][0]
        self.image = self.project.get("images", self.image_id)
        self.categories = self.project.records("categories")

    def request(self):
        return {"schema_version": REQUEST_SCHEMA, "request_id": "agent_1", "project_id": self.project.project_id,
                "expected_revision": self.project.revision, "action": "propose_instances",
                "instances": [{"image_id": self.image_id, "category_id": self.category, "bbox_xyxy": [1, 2, 10, 20]}]}

    def test_project_writer_and_model_job_locks(self):
        from AntSleap.core.instance_model_jobs import run_model_job
        with self.assertRaises(ValueError):
            InstanceProject(self.project.path)
        def nested():
            with self.assertRaises(RuntimeError):
                run_model_job(self.project.root, lambda: None)
            return "finished"
        self.assertEqual(run_model_job(self.project.root, nested), "finished")
        self.assertEqual(run_model_job(self.project.root, lambda: "released"), "released")

    def test_agent_reads_while_gui_owns_writer_and_queues_drafts(self):
        reader = InstanceProject(self.project.path, readonly=True)
        try:
            payload = inspect_project(reader)
            self.assertEqual(payload["revision"], self.project.revision)
            result = submit_request(reader, self.request())
            self.assertEqual(result["status"], "queued")
            self.assertEqual(self.project.records("instances"), [])
            with self.assertRaises(ValueError):
                reader.category("forbidden")
        finally:
            reader.close()
        results = process_inbox(self.project)
        self.assertEqual(results[0]["status"], "applied_as_drafts")
        self.assertFalse(self.project.trusted(self.project.records("instances")[0]))
        self.assertEqual(process_inbox(self.project), [])

    def test_agent_rejects_confirmation_stale_request_and_partial_batch(self):
        request = self.request()
        request["instances"][0]["review"] = "confirmed"
        with self.assertRaises(ValueError):
            apply_request(self.project, request)
        request = self.request()
        request["instances"].append({"image_id": self.image_id, "category_id": self.category, "bbox_xyxy": [0, 0, 999, 3]})
        with self.assertRaises(ValueError):
            apply_request(self.project, request)
        self.assertEqual(self.project.records("instances"), [])
        request = self.request()
        self.project.category("Another")
        with self.assertRaises(ValueError):
            apply_request(self.project, request)

    def test_agent_idempotence_after_apply(self):
        request = self.request()
        first = apply_request(self.project, request)
        second = apply_request(self.project, request)
        self.assertEqual(first, second)
        self.assertEqual(submit_request(self.project, request), first)
        self.assertEqual(self.project.records("instances")[0]["class_source"], "agent")
        request["instances"][0]["bbox_xyxy"] = [2, 3, 11, 21]
        with self.assertRaises(ValueError):
            submit_request(self.project, request)
        self.assertEqual(len(self.project.records("instances")), 1)

    def test_external_cancellation_timeout_and_settings_persistence(self):
        from AntSleap.core.instance_external_backend import run_command
        script = self.root / "wait adapter.py"
        script.write_text("import time; time.sleep(30)", encoding="utf-8")
        settings = sanitize_instance_backend({"python_executable": sys.executable, "timeout_seconds": 1,
            "predict_command": '\"{python}\" \"' + str(script) + '\" \"{contract}\"'})
        self.project.set_settings({"backend": "external", "external_backend": settings})
        reader = InstanceProject(self.project.path, readonly=True)
        try:
            self.assertEqual(reader.settings()["external_backend"], settings)
        finally:
            reader.close()
        with self.assertRaises(InterruptedError):
            run_command(settings, "predict_command", self.root / "contract.json", self.root, cancel_check=lambda: True)
        with self.assertRaises(TimeoutError):
            run_command(settings, "predict_command", self.root / "contract.json", self.root)

    def test_malformed_agent_inbox_is_rejected(self):
        pending = self.project.root / "agent_requests" / "pending"
        pending.mkdir(parents=True)
        (pending / "bad.json").write_text("[]", encoding="utf-8")
        self.assertEqual(process_inbox(self.project)[0]["status"], "rejected")
        self.assertEqual(self.project.records("instances"), [])

    def test_agent_cli_submission_and_material_review_gate(self):
        import subprocess
        import sqlite3
        from AntSleap.core.instance_material_import import reviewed_candidates, import_reviewed_materials
        request_file = self.root / "request.json"
        request_file.write_text(json.dumps(self.request()), encoding="utf-8")
        cli = Path(__file__).resolve().parents[1] / "tools" / "agentic" / "instance_workbench.py"
        process = subprocess.run([sys.executable, str(cli), "propose_instances", "--project", str(self.project.path),
                                  "--request", str(request_file)], capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr + process.stdout)
        self.assertEqual(json.loads(process.stdout)["status"], "queued")
        self.assertEqual(process_inbox(self.project)[0]["status"], "applied_as_drafts")
        database = self.root / "materials.sqlite"
        source = self.root / "reviewed.png"
        Image.new("RGB", (20, 20), "red").save(source)
        with sqlite3.connect(database) as conn:
            conn.executescript("""
                CREATE TABLE pdf_files(id INTEGER PRIMARY KEY,file_name TEXT,file_path TEXT);
                CREATE TABLE figure_records(id INTEGER PRIMARY KEY,pdf_file_id INTEGER,page_number INTEGER,
                    figure_index INTEGER,image_file_path TEXT,image_file_name TEXT,final_confidence REAL,
                    species_confidence REAL,accepted INTEGER,species_candidate TEXT,review_status TEXT,
                    category TEXT,multimodal_review_mode TEXT,multimodal_model_used TEXT);
                CREATE TABLE figure_human_reviews(source_table TEXT,record_id INTEGER,human_status TEXT);
                INSERT INTO pdf_files VALUES(1,'paper.pdf','paper.pdf');
                INSERT INTO figure_human_reviews VALUES('figure_records',1,'import_ready');
                INSERT INTO figure_human_reviews VALUES('figure_records',2,'pending');
            """)
            for n in (1, 2):
                conn.execute("INSERT INTO figure_records VALUES(?,1,1,?,?,?,.9,.9,1,'Suggested species','accepted','','','')",
                             (n, n, str(source), source.name))
        candidates = reviewed_candidates(database)
        self.assertEqual(len(candidates), 1)
        _, report = import_reviewed_materials(self.project, database, candidates)
        self.assertEqual(len(report["imported"]), 1)
        imported = self.project.get("images", report["imported"][0])
        self.assertTrue(imported["source_group"].startswith("pdf_"))
        self.assertFalse(any(r["image_id"] == imported["id"] for r in self.project.records("instances")))
        with sqlite3.connect(database) as conn:
            conn.execute("UPDATE figure_human_reviews SET human_status='pending'")
        _, report = import_reviewed_materials(self.project, database, candidates)
        self.assertEqual(len(report["skipped"]), 1)

    def test_duplicate_coco_ids_do_not_mutate_project(self):
        from AntSleap.core.instance_dataset import import_coco
        annotation = self.root / "bad-coco.json"
        for table in ("categories", "images", "annotations"):
            payload = {"categories": [], "images": [], "annotations": []}
            payload[table] = [{"id": 1}, {"id": 1}]
            annotation.write_text(json.dumps(payload), encoding="utf-8")
            before = self.project.revision
            with self.assertRaises(ValueError):
                import_coco(self.project, annotation, self.root)
            self.assertEqual(self.project.revision, before)

    def test_external_configuration_and_contract_validation(self):
        with self.assertRaises(ValueError):
            sanitize_instance_backend({"train_command": "python train.py"})
        with self.assertRaises(ValueError):
            sanitize_instance_backend({"train_command": "python train.py {contract} && echo bad"})
        payload = {"schema_version": PREDICTION_SCHEMA, "project_id": self.project.project_id, "revision": self.project.revision,
                   "image_uid": self.image_id, "image_hash": self.image["hash"], "category_map_hash": category_hash(self.categories), "task": "detect",
                   "instances": [{"proposal_id": "p1", "category_id": self.category, "bbox_xyxy": [1, 2, 10, 20], "score": .9},
                                 {"proposal_id": "p2", "category_id": self.category, "bbox_xyxy": [20, 2, 30, 20], "score": .8}]}
        kwargs = dict(project_id=self.project.project_id, revision=self.project.revision, image=self.image, categories=self.categories, task="detect")
        self.assertEqual(len(validate_prediction(payload, **kwargs)), 2)
        import copy
        for field in ("project_id", "revision", "image_hash", "category_map_hash", "task"):
            invalid = copy.deepcopy(payload)
            invalid[field] = "stale"
            with self.assertRaises(ValueError):
                validate_prediction(invalid, **kwargs)
        invalid = copy.deepcopy(payload)
        invalid["instances"] = [None]
        with self.assertRaises(ValueError):
            validate_prediction(invalid, **kwargs)
        payload["instances"][1]["proposal_id"] = "p1"
        with self.assertRaises(ValueError):
            validate_prediction(payload, **kwargs)

    def test_real_external_predict_process(self):
        script = self.root / "external adapter.py"
        script.write_text('''import json,sys
from pathlib import Path
c=json.loads(Path(sys.argv[1]).read_text())
p={k:c[k] for k in ['project_id','revision','image_uid','image_hash','category_map_hash','task']}
p['schema_version']='taxamask-instance-prediction-v1'
p['instances']=[{'proposal_id':'p'+str(n),'category_id':c['categories'][0]['id'],'bbox_xyxy':[1+n*15,2,10+n*15,20],'score':.9} for n in range(2)]
Path(c['prediction_json']).write_text(json.dumps(p))
''', encoding="utf-8")
        weights = self.root / "external.bin"
        weights.write_bytes(b"contract-test-not-real-model")
        manifest = self.root / "manifest.json"
        manifest.write_text(json.dumps({"schema_version": MODEL_SCHEMA, "task": "detect", "category_map_hash": category_hash(self.categories),
                                       "weights": weights.name, "weights_hash": digest(weights)}), encoding="utf-8")
        settings = {"python_executable": sys.executable, "model_manifest": str(manifest),
                    "predict_command": '"{python}" "' + str(script) + '" "{contract_json}"'}
        proposals = external_predict(settings, run_root=self.root / "runs", project_id=self.project.project_id, revision=self.project.revision,
                                     image=self.image, image_path=self.project.image_path(self.image), categories=self.categories, task="detect")
        self.assertEqual(len(proposals), 2)
        self.assertEqual(len(self.project.records("instances")), 0)

    def test_external_coco_training_uses_shared_ledger(self):
        from AntSleap.core.instance_dataset import export_dataset
        from AntSleap.core.instance_training_record import prepare_record
        key = self.project.put_instance(self.image_id, self.category, [1, 2, 10, 20])
        self.project.batch([key], "confirm")
        self.project.review_image(self.image_id, "complete")
        for n in range(12):
            path = self.root / f"train_{n}.png"
            Image.new("RGB", (40, 30), (n*12, 20, 30)).save(path)
            image_id = self.project.import_images([path])[0][0]
            key = self.project.put_instance(image_id, self.category, [1, 2, 10, 20])
            self.project.batch([key], "confirm")
            self.project.review_image(image_id, "complete")
        folder, _ = export_dataset(self.project, self.root / "exports", format="coco")
        initial = self.root / "initial.bin"
        initial.write_bytes(b"contract-initial")
        script = self.root / "train_adapter.py"
        script.write_text('''import json,sys,hashlib
from pathlib import Path
c=json.loads(Path(sys.argv[1]).read_text())
w=Path(c['run_dir'])/'external.bin'
w.write_bytes(b'contract-test-output')
m={'schema_version':'taxamask-instance-external-model-v1','task':c['task'],'category_map_hash':c['category_map_hash'],'weights':w.name,'weights_hash':hashlib.sha256(w.read_bytes()).hexdigest(),'effective_config':c['effective_config']}
Path(c['model_manifest']).write_text(json.dumps(m))
''', encoding="utf-8")
        config = {"task": "detect", "dataset": str(folder), "run_dir": str(self.root / "training"), "weights": str(initial), "epochs": 1, "batch": 2, "imgsz": 64,
                  "external_backend": {"python_executable": sys.executable, "dataset_format": "coco", "train_command": '"{python}" "' + str(script) + '" "{contract_json}"'}}
        recorder, run, initial_copy = prepare_record(config)
        try:
            config["weights"] = str(initial_copy)
            config["effective_config"] = run.record["effective_config"]
            manifest = external_train(config)
            run.add_artifact(artifact_id="weights", role="output_weights", path=manifest["weights"], path_base="managed_model_root", base_dir=config["run_dir"])
            run.succeed()
            self.assertEqual(run.status, "succeeded")
        finally:
            run.close()
        # Exercise the same child-process entrypoint used by GUI and agent training.
        import subprocess
        config["run_dir"] = str(self.project.root / "runs" / "external_cli_test")
        config["weights"] = str(initial)
        config_file = self.root / "train-config.json"
        config_file.write_text(json.dumps(config), encoding="utf-8")
        completed = subprocess.run([sys.executable, "-m", "AntSleap.core.instance_training", str(config_file)],
                                   cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertTrue((Path(config["run_dir"]) / "model_manifest.json").is_file())


if __name__ == "__main__":
    unittest.main()
