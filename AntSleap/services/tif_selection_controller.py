from dataclasses import dataclass

from .tif_service_result import service_ok


@dataclass(frozen=True)
class TifSelectionState:
    specimen_id: str = ""
    volume_scope: str = "full"
    part_id: str = ""
    reslice_id: str = ""
    label_role: str = ""
    display_mode: str = "slice"

    @property
    def is_part_scope(self):
        return self.volume_scope == "part"

    def context_key(self):
        return (
            str(self.specimen_id or ""),
            str(self.volume_scope or ""),
            str(self.part_id or ""),
            str(self.reslice_id or ""),
            str(self.label_role or ""),
            str(self.display_mode or ""),
        )

    def to_dict(self):
        return {
            "specimen_id": self.specimen_id,
            "volume_scope": self.volume_scope,
            "part_id": self.part_id,
            "reslice_id": self.reslice_id,
            "label_role": self.label_role,
            "display_mode": self.display_mode,
        }


class TifSelectionController:
    def __init__(self, state=None):
        self.state = state or TifSelectionState()

    def update(self, **changes):
        payload = self.state.to_dict()
        payload.update({key: str(value or "") for key, value in changes.items() if key in payload})
        if not payload.get("volume_scope"):
            payload["volume_scope"] = "full"
        if not payload.get("display_mode"):
            payload["display_mode"] = "slice"
        self.state = TifSelectionState(**payload)
        return service_ok("selection_updated", state=self.state.to_dict(), context_key=self.state.context_key())

    def select_specimen(self, specimen_id, *, volume_scope="full"):
        return self.update(specimen_id=specimen_id, volume_scope=volume_scope, part_id="", reslice_id="")

    def select_part(self, specimen_id, part_id, *, reslice_id=""):
        return self.update(specimen_id=specimen_id, volume_scope="part", part_id=part_id, reslice_id=reslice_id)

    def label_roles_for_scope(self, scope=None):
        clean_scope = str(scope or self.state.volume_scope or "full")
        if clean_scope == "part":
            return ("manual_truth", "editable_ai_result", "raw_ai_prediction_backup")
        return ("working_edit", "manual_truth", "raw_ai_prediction_backup")

    def preferred_label_role(self, current_role="", scope=None):
        roles = self.label_roles_for_scope(scope)
        if current_role in roles:
            if str(scope or self.state.volume_scope or "") == "part" and current_role == "manual_truth":
                return "editable_ai_result"
            return current_role
        return "editable_ai_result" if str(scope or self.state.volume_scope or "") == "part" else "working_edit"
