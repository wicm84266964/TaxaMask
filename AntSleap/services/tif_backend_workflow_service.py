from .tif_service_result import service_blocked, service_ok


class TifBackendWorkflowService:
    def __init__(self, project_manager):
        self.project = project_manager

    def train_ready_part_refs(self, specimen_ids=None):
        refs = []
        wanted = {str(item) for item in specimen_ids} if specimen_ids else None
        for specimen in self.project.project_data.get("specimens", []) or []:
            specimen_id = str((specimen or {}).get("specimen_id") or "")
            if wanted is not None and specimen_id not in wanted:
                continue
            for part in (specimen or {}).get("parts", []) or []:
                if not isinstance(part, dict):
                    continue
                readiness = self.project.evaluate_part_train_ready(
                    specimen_id,
                    part.get("part_id", ""),
                    validate_label_ids=False,
                )
                if not readiness.get("train_ready"):
                    continue
                refs.append(
                    {
                        "specimen_id": readiness.get("specimen_id", ""),
                        "part_id": readiness.get("part_id", ""),
                        "reslice_id": readiness.get("reslice_id", ""),
                    }
                )
        return refs

    def train_ready_part_reports(self, specimen_ids=None):
        reports = []
        wanted = {str(item) for item in specimen_ids} if specimen_ids else None
        for specimen in self.project.project_data.get("specimens", []) or []:
            specimen_id = str((specimen or {}).get("specimen_id") or "")
            if wanted is not None and specimen_id not in wanted:
                continue
            for part in (specimen or {}).get("parts", []) or []:
                if not isinstance(part, dict):
                    continue
                readiness = self.project.evaluate_part_train_ready(
                    specimen_id,
                    part.get("part_id", ""),
                    validate_label_ids=False,
                )
                reports.append(readiness)
        return reports

    def selected_specimen_ids_for_action(self, action, *, current_specimen_id=""):
        clean_action = str(action or "")
        if clean_action in {"prepare_dataset", "train"}:
            ready = [item.get("specimen_id") for item in self.project.list_train_ready_specimens()]
            if not ready:
                return service_blocked("no_train_ready_top_level_volumes", reasons=["no_train_ready_top_level_volumes"])
            return service_ok("selected_top_level_train_samples", specimen_ids=ready)
        ids = [str(current_specimen_id or "")] if current_specimen_id else []
        if not ids:
            ids = [item.get("specimen_id") for item in self.project.project_data.get("specimens", []) if isinstance(item, dict)]
        ids = [item for item in ids if item]
        if not ids:
            return service_blocked("no_top_level_volume_available", reasons=["no_top_level_volume_available"])
        return service_ok("selected_top_level_predict_samples", specimen_ids=ids)

    def selected_backend_samples_for_action(
        self,
        action,
        *,
        current_volume_scope="full",
        current_specimen_id="",
        current_part_id="",
        current_reslice_id="",
        selected_predict_refs=None,
    ):
        clean_action = str(action or "")
        if clean_action in {"prepare_dataset", "train"}:
            if current_volume_scope == "part" and current_specimen_id and current_part_id:
                readiness = self.project.evaluate_part_train_ready(
                    current_specimen_id,
                    current_part_id,
                    current_reslice_id,
                    validate_label_ids=False,
                )
                if not readiness.get("train_ready"):
                    return service_blocked(
                        "current_part_not_train_ready",
                        reasons=list(readiness.get("reasons") or []),
                        readiness=readiness,
                    )
            part_refs = self.train_ready_part_refs()
            if part_refs:
                return service_ok("selected_part_train_samples", input_scope="part_reslice", part_refs=part_refs, specimen_ids=[])
            if current_volume_scope == "part":
                return service_blocked("current_part_not_train_ready", reasons=["part_not_train_ready"])
            top = self.selected_specimen_ids_for_action(clean_action)
            if top:
                return service_ok(
                    "selected_top_level_train_samples",
                    input_scope="top_level_volume",
                    part_refs=[],
                    specimen_ids=top.payload.get("specimen_ids", []),
                    fallback_reason="no_train_ready_parts",
                )
            return service_blocked(top.message or "no_train_ready_samples", reasons=top.reasons)

        refs = []
        for ref in selected_predict_refs or []:
            specimen_id = str((ref or {}).get("specimen_id") or "")
            part_id = str((ref or {}).get("part_id") or "")
            reslice_id = str((ref or {}).get("reslice_id") or "")
            if not specimen_id or not part_id:
                continue
            readiness = self.project.evaluate_part_predict_ready(specimen_id, part_id, reslice_id)
            if not readiness.get("predict_ready"):
                return service_blocked("selected_prediction_target_incomplete", reasons=list(readiness.get("reasons") or []), readiness=readiness)
            refs.append({"specimen_id": specimen_id, "part_id": part_id, "reslice_id": readiness.get("reslice_id", reslice_id)})
        if refs:
            return service_ok("selected_part_predict_samples", input_scope="part_reslice", part_refs=refs, specimen_ids=[])
        if current_volume_scope != "part":
            top = self.selected_specimen_ids_for_action(clean_action, current_specimen_id=current_specimen_id)
            if top:
                return service_ok(
                    "selected_top_level_predict_samples",
                    input_scope="top_level_volume",
                    part_refs=[],
                    specimen_ids=top.payload.get("specimen_ids", []),
                )
            return service_blocked(top.message or "no_predict_samples", reasons=top.reasons)
        return service_blocked("select_prediction_target", reasons=["select_prediction_target"])

    def predict_will_overwrite_editable_result(self, *, part_refs=None, specimen_ids=None, input_scope="part_reslice"):
        if str(input_scope or "") == "top_level_volume":
            for specimen_id in specimen_ids or []:
                specimen = self.project.get_specimen(str(specimen_id), default=None)
                record = (((specimen or {}).get("labels") or {}).get("working_edit") or {})
                if str(record.get("path") or "").strip():
                    return service_ok("predict_will_overwrite_editable_result", overwrite=True)
            return service_ok("predict_will_not_overwrite_editable_result", overwrite=False)
        for ref in part_refs or []:
            record = self.project.part_label_record(
                str((ref or {}).get("specimen_id") or ""),
                str((ref or {}).get("part_id") or ""),
                "editable_ai_result",
                reslice_id=str((ref or {}).get("reslice_id") or ""),
            )
            if str(record.get("path") or "").strip():
                return service_ok("predict_will_overwrite_editable_result", overwrite=True)
        return service_ok("predict_will_not_overwrite_editable_result", overwrite=False)
