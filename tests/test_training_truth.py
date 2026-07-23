import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from AntSleap.core.project import ProjectManager
from AntSleap.core.blink_dataset import BlinkTrajectoryDataset
from AntSleap.core.blink_heatmap_dataset import BlinkHeatmapDataset
from AntSleap.core.training_preflight import build_training_preflight
from AntSleap.core.training_truth import (
    TRAINING_ACCEPT_SELECTED_AI,
    TRAINING_REVIEW_CONFIRMED,
    TRAINING_REVIEW_DRAFT,
    TRAINING_SOURCE_BLINK_EXPERT,
    get_part_training_truth,
    remove_part_training_truth,
    resolve_part_training_trust,
    set_part_training_truth,
)
from tests.test_2d_sqlite_project_save import _sqlite_manager


class TrainingTruthTests(unittest.TestCase):
    def _polygon(self):
        return [[5.0, 5.0], [30.0, 5.0], [15.0, 25.0]]

    def test_legacy_manual_is_confirmed_but_auto_marker_is_draft(self):
        manual = {"parts": {"Head": self._polygon()}}
        draft = {
            "parts": {"Head": self._polygon()},
            "descriptions": {"Head": "Auto-Annotated"},
        }

        self.assertTrue(resolve_part_training_trust(manual, "Head")["eligible"])
        decision = resolve_part_training_trust(draft, "Head")
        self.assertFalse(decision["eligible"])
        self.assertEqual(decision["state"], "draft")

    def test_explicit_draft_and_confirmed_marker_conflict_are_excluded(self):
        entry = {"parts": {"Head": self._polygon()}, "descriptions": {}}
        set_part_training_truth(
            entry,
            "Head",
            source=TRAINING_SOURCE_BLINK_EXPERT,
            review_status=TRAINING_REVIEW_DRAFT,
        )
        self.assertEqual(resolve_part_training_trust(entry, "Head")["state"], "draft")

        set_part_training_truth(
            entry,
            "Head",
            source="model_prediction",
            review_status=TRAINING_REVIEW_CONFIRMED,
            accepted_via=TRAINING_ACCEPT_SELECTED_AI,
        )
        entry["descriptions"]["Head"] = "Auto-Annotated"
        decision = resolve_part_training_trust(entry, "Head")
        self.assertFalse(decision["eligible"])
        self.assertEqual(decision["state"], "conflict")

    def test_update_label_defaults_to_manual_and_accept_selected_preserves_source(self):
        manager = ProjectManager()
        image_path = manager._image_data_key("manual.png")
        manager.project_data["images"] = [image_path]
        manager.project_data["labels"] = {image_path: manager._default_label_entry()}

        manager.update_label(image_path, "Head", self._polygon(), save=False)
        manual_truth = get_part_training_truth(
            manager.project_data["labels"][image_path], "Head"
        )
        self.assertEqual(manual_truth["source"], "manual")
        self.assertEqual(manual_truth["review_status"], "confirmed")

        manager.update_label(
            image_path,
            "Eye",
            self._polygon(),
            "Auto-Annotated",
            auto_box=[4, 4, 31, 26],
            save=False,
        )
        manager.update_auto_box(
            image_path,
            "Eye",
            [4, 4, 31, 26],
            source_meta={"source": "vlm_first_mile", "review_status": "draft"},
            save=False,
        )
        self.assertEqual(manager.verify_image_labels(image_path, save=False), 1)
        accepted = get_part_training_truth(
            manager.project_data["labels"][image_path], "Eye"
        )
        self.assertEqual(accepted["source"], "vlm_first_mile")
        self.assertEqual(accepted["review_status"], "confirmed")
        self.assertEqual(accepted["accepted_via"], "accept_selected_ai")

    def test_auto_signal_stays_draft_when_marker_is_removed_without_acceptance(self):
        manager = ProjectManager()
        image_path = manager._image_data_key("auto.png")
        manager.project_data["images"] = [image_path]
        manager.project_data["labels"] = {image_path: manager._default_label_entry()}
        manager.update_label(
            image_path,
            "Head",
            self._polygon(),
            "Auto-Annotated",
            auto_box=[4, 4, 31, 26],
            save=False,
        )
        entry = manager.project_data["labels"][image_path]
        entry["descriptions"].pop("Head")
        decision = resolve_part_training_trust(entry, "Head")
        self.assertFalse(decision["eligible"])
        self.assertEqual(decision["state"], "draft")

    def test_strict_metadata_rejects_unknown_confirmed_source_and_preserves_other_metadata(self):
        entry = {
            "label_part_metadata": {
                "Head": {"other_audit": {"operator": "reviewer"}}
            }
        }
        with self.assertRaisesRegex(ValueError, "training_truth_record_invalid"):
            set_part_training_truth(
                entry,
                "Head",
                source="unknown_plugin",
                review_status=TRAINING_REVIEW_CONFIRMED,
                accepted_via=TRAINING_ACCEPT_SELECTED_AI,
            )
        set_part_training_truth(
            entry,
            "Head",
            source=TRAINING_SOURCE_BLINK_EXPERT,
            review_status=TRAINING_REVIEW_DRAFT,
        )
        self.assertTrue(remove_part_training_truth(entry, "Head"))
        self.assertEqual(
            entry["label_part_metadata"]["Head"]["other_audit"],
            {"operator": "reviewer"},
        )

    def test_blink_draft_without_marker_can_be_accepted_and_removed(self):
        manager = ProjectManager()
        image_path = manager._image_data_key("blink.png")
        manager.project_data["images"] = [image_path]
        manager.project_data["labels"] = {image_path: manager._default_label_entry()}
        manager.update_label(
            image_path,
            "Eye",
            self._polygon(),
            save=False,
            training_source=TRAINING_SOURCE_BLINK_EXPERT,
            training_review_status=TRAINING_REVIEW_DRAFT,
            training_accepted_via="",
        )
        self.assertEqual(
            manager.summarize_image_ai_drafts(image_path)["reviewable_polygon_parts"],
            ["Eye"],
        )
        self.assertEqual(manager.verify_image_labels(image_path, save=False), 1)
        accepted = get_part_training_truth(manager.project_data["labels"][image_path], "Eye")
        self.assertEqual(accepted["source"], TRAINING_SOURCE_BLINK_EXPERT)
        self.assertEqual(accepted["accepted_via"], TRAINING_ACCEPT_SELECTED_AI)

        manager.update_label(
            image_path,
            "Mandible",
            self._polygon(),
            save=False,
            training_source=TRAINING_SOURCE_BLINK_EXPERT,
            training_review_status=TRAINING_REVIEW_DRAFT,
            training_accepted_via="",
        )
        self.assertEqual(manager.remove_auto_labels_for_images([image_path], save=False), 1)
        self.assertNotIn("Mandible", manager.project_data["labels"][image_path]["parts"])

    def test_preflight_excludes_explicit_draft_and_reports_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            image_path = str(Path(tmp) / "ant.png")
            Image.new("RGB", (64, 64)).save(image_path)
            draft = {"parts": {"Head": self._polygon()}, "descriptions": {}}
            set_part_training_truth(
                draft,
                "Head",
                source=TRAINING_SOURCE_BLINK_EXPERT,
                review_status=TRAINING_REVIEW_DRAFT,
            )
            preflight = build_training_preflight(
                [image_path], {image_path: draft}, ["Head"], ["Head"]
            )

            self.assertEqual(preflight["locator_samples"], [])
            self.assertEqual(preflight["parts_samples"], [])
            self.assertEqual(
                preflight["excluded_untrusted_parts"][0]["reason"],
                "training_truth_not_confirmed",
            )
            self.assertIn(
                "Excluded 1 unconfirmed part annotation(s) from training.",
                preflight["warnings"],
            )


class BlinkTrainingTruthGateTests(unittest.TestCase):
    def _project_path(self, root, *, truth=None, auto_marker=False):
        Image.new("RGB", (64, 64), color=(180, 180, 180)).save(root / "ant.png")
        label = {
            "parts": {"Eye": [[20, 20], [35, 20], [28, 34]]},
            "descriptions": {"Eye": "Auto-Annotated"} if auto_marker else {},
            "trajectories": {
                "Eye": {
                    "frames": [
                        {"box": [15, 15, 40, 40]},
                        {"box": [20, 20, 35, 35]},
                    ],
                    "parent_context": {
                        "parent_part": "Head",
                        "parent_box": [5, 5, 55, 55],
                        "source": "manual",
                    },
                }
            },
        }
        if truth:
            set_part_training_truth(label, "Eye", **truth)
        project_path = root / "project.json"
        project_path.write_text(
            json.dumps({"labels": {"ant.png": label}}), encoding="utf-8"
        )
        return project_path

    def _lengths(self, project_path):
        return (
            len(
                BlinkTrajectoryDataset(
                    str(project_path), "Eye", parent_part="Head", target_size=(64, 64)
                )
            ),
            len(
                BlinkHeatmapDataset(
                    str(project_path), "Eye", parent_part="Head", input_size=64
                )
            ),
        )

    def test_both_backends_share_the_same_training_truth_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = self._project_path(
                root,
                truth={
                    "source": TRAINING_SOURCE_BLINK_EXPERT,
                    "review_status": TRAINING_REVIEW_DRAFT,
                    "accepted_via": "",
                },
            )
            self.assertEqual(self._lengths(draft), (0, 0))

            confirmed = self._project_path(
                root,
                truth={
                    "source": TRAINING_SOURCE_BLINK_EXPERT,
                    "review_status": TRAINING_REVIEW_CONFIRMED,
                    "accepted_via": TRAINING_ACCEPT_SELECTED_AI,
                },
            )
            self.assertEqual(self._lengths(confirmed), (10, 10))

            conflict = self._project_path(
                root,
                truth={
                    "source": TRAINING_SOURCE_BLINK_EXPERT,
                    "review_status": TRAINING_REVIEW_CONFIRMED,
                    "accepted_via": TRAINING_ACCEPT_SELECTED_AI,
                },
                auto_marker=True,
            )
            self.assertEqual(self._lengths(conflict), (0, 0))
            self.assertEqual(self._lengths(self._project_path(root)), (10, 10))


class TrainingTruthSQLiteTests(unittest.TestCase):
    def test_malformed_truth_round_trip_stays_conflicting(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager, manifest_path, _db_path = _sqlite_manager(Path(tmp))
            image_path = manager.project_data["images"][0]
            manager.update_label(
                image_path, "Eye", [[2, 2], [8, 2], [8, 9], [2, 9]], save=True
            )
            entry = manager.project_data["labels"][image_path]
            entry.setdefault("label_part_metadata", {}).setdefault("Eye", {})[
                "training_truth_v1"
            ] = {
                "source": "unknown_plugin",
                "review_status": "confirmed",
                "accepted_via": "manual_edit",
            }
            manager._mark_sqlite_label_dirty(image_path)
            manager.save_project()

            reloaded = ProjectManager()
            reloaded.load_project(manifest_path)
            decision = resolve_part_training_trust(
                reloaded.project_data["labels"][image_path], "Eye"
            )
            self.assertFalse(decision["eligible"])
            self.assertEqual(decision["state"], "conflict")

    def test_invalid_label_part_metadata_json_blocks_project_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager, manifest_path, db_path = _sqlite_manager(Path(tmp))
            image_path = manager.project_data["images"][0]
            manager.update_label(
                image_path, "Eye", [[2, 2], [8, 2], [8, 9], [2, 9]], save=True
            )
            connection = sqlite3.connect(db_path)
            try:
                with connection:
                    connection.execute(
                        "UPDATE label_parts SET metadata_json = ? WHERE part_name = ?",
                        ("{", "Eye"),
                    )
            finally:
                connection.close()

            with self.assertRaisesRegex(ValueError, "label_part_metadata_invalid:Eye"):
                ProjectManager().load_project(manifest_path)


if __name__ == "__main__":
    unittest.main()
