import ast
import os
import sys
import tempfile
import unittest
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from PySide6.QtWidgets import QApplication
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith("PySide6"):
        QApplication = None
    else:
        raise
else:
    import numpy as np

    from AntSleap.core.tif_project import TifProjectManager
    from AntSleap.core.tif_volume_io import write_volume_sidecar
    from AntSleap.ui.tif_workbench import TifWorkbenchWidget


@unittest.skipUnless(QApplication is not None, "PySide6 is required for TIF Agent context tests")
class TifAgentContextBuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _make_volume_widget(self, root):
        manager = TifProjectManager()
        manager.create_project("agent_context", root / "agent_context")
        manager.create_specimen_scaffold("01-0101-21", modality="confocal")
        image = np.arange(5 * 8 * 8, dtype=np.uint8).reshape((5, 8, 8))
        edit = np.zeros((5, 8, 8), dtype=np.uint16)
        image_rel = "specimens/01-0101-21/working/image.ome.zarr"
        edit_rel = "specimens/01-0101-21/labels/working_edit.ome.zarr"
        image_meta = write_volume_sidecar(root / "agent_context" / image_rel, image, role="working_image")
        edit_meta = write_volume_sidecar(root / "agent_context" / edit_rel, edit, role="working_edit")
        manager.register_working_volume("01-0101-21", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
        manager.register_label_volume("01-0101-21", "working_edit", edit_rel, edit_meta["shape_zyx"], edit_meta["dtype"], save=True)
        part = manager.add_part(
            "01-0101-21",
            "head",
            image={"path": image_rel, **image_meta},
            parent_bbox_zyx=[[1, 2], [3, 4], [5, 6]],
            save=False,
        )
        part["user_tags"] = ["review_batch"]
        manager.add_part_reslice(
            "01-0101-21",
            "head",
            {
                "reslice_id": "head_local_axis_001",
                "image_path": image_rel,
                "status": "exported",
                "outputs": {"image_shape_zyx": [5, 8, 8]},
                "reslice_params": {"output_shape_zyx": [5, 8, 8], "output_spacing_zyx": [1.0, 1.0, 1.0]},
            },
            save=False,
        )
        manager.project_data["part_user_tags"] = [
            {"tag_id": "review_batch", "label": "Review batch"}
        ]
        manager.save_project()
        widget = TifWorkbenchWidget(manager, "en")
        widget.render_current_slice()
        return widget

    def _dict_keys_from_return(self, path, required_key):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
                keys = [
                    key.value
                    for key in node.value.keys
                    if isinstance(key, ast.Constant) and isinstance(key.value, str)
                ]
                if required_key in keys:
                    return keys
        return []

    def _compact_allowed_keys(self):
        tree = ast.parse((PROJECT_ROOT / "AntSleap" / "main.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_compact_agent_context":
                for stmt in node.body:
                    if not isinstance(stmt, ast.Assign):
                        continue
                    if not any(isinstance(target, ast.Name) and target.id == "allowed_keys" for target in stmt.targets):
                        continue
                    return [
                        item.value
                        for item in stmt.value.elts
                        if isinstance(item, ast.Constant) and isinstance(item.value, str)
                    ]
        return []

    def _panel_mapping_keys(self):
        tree = ast.parse((PROJECT_ROOT / "AntSleap" / "ui" / "taxamask_agent_panel.py").read_text(encoding="utf-8"))
        keys = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Tuple) or len(node.elts) < 2:
                continue
            first = node.elts[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                keys.add(first.value)
        return keys

    def test_tif_agent_context_keys_are_compacted_and_prompt_mapped(self):
        builder_keys = self._dict_keys_from_return(
            PROJECT_ROOT / "AntSleap" / "ui" / "tif_agent_context.py",
            "tif_next_requirement",
        )
        self.assertGreater(len(builder_keys), 60)

        allowed_keys = set(self._compact_allowed_keys())
        missing_from_compact = [key for key in builder_keys if key not in allowed_keys]
        self.assertEqual(missing_from_compact, [])

        prompt_keys = self._panel_mapping_keys()
        missing_from_prompt = [key for key in builder_keys if key not in prompt_keys]
        self.assertEqual(missing_from_prompt, [])

    def test_public_agent_context_entry_delegates_to_builder_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp))
            try:
                widget.current_volume_scope = "part"
                widget.current_part_id = "head"
                widget.current_reslice_id = "head_local_axis_001"
                widget.current_part = widget.project.get_part("01-0101-21", "head", default={})
                widget._tif_predict_selected_refs = {("01-0101-21", "head", "head_local_axis_001")}
                context = widget.get_agent_context()

                self.assertIs(widget.agent_context_builder.workbench, widget)
                self.assertEqual(context["source_workbench"], "tif_volume")
                self.assertEqual(context["project_type"], "tif_volume")
                self.assertEqual(context["active_specimen_id"], "01-0101-21")
                self.assertEqual(context["active_part_id"], "head")
                self.assertEqual(context["active_reslice_id"], "head_local_axis_001")
                self.assertEqual(context["active_part_group_tags"], "Review batch")
                self.assertEqual(context["active_volume_shape_zyx"], "5/8/8")
                self.assertIn("annotation_training_loop", context["tif_next_requirement"])
                self.assertIn("tif_state_summary", context)
                self.assertIn("preview_resource_summary", context)
                self.assertIn("local_axis_state_summary", context)
                self.assertIn("head_local_axis_001", context["local_axis_state_summary"])
                self.assertIn("predict_target_summary", context)
                self.assertEqual(context["predict_selected_target_count"], "1")
                self.assertIn("01-0101-21/head/head_local_axis_001", context["predict_selected_targets"])
                self.assertIn("volume_clip_plane", context)
                self.assertIn("volume_roi_high_detail", context)
                self.assertIn("training_sample_rule", context)
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()


if __name__ == "__main__":
    unittest.main()
