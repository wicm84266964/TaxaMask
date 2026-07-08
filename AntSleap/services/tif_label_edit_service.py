from dataclasses import dataclass, field

import numpy as np

from AntSleap.core.tif_label_guard import can_write_label_role, require_editable_label_role

from .tif_service_result import service_blocked, service_ok


@dataclass(frozen=True)
class TifLabelSaveRequest:
    edit_path: str
    slices: dict
    slice_revisions: dict = field(default_factory=dict)
    scope: str = "top_level"
    specimen_id: str = ""
    part_id: str = ""
    reslice_id: str = ""
    role: str = "working_edit"
    reason: str = "manual"

    def to_dict(self):
        return {
            "edit_path": self.edit_path,
            "slices": dict(self.slices or {}),
            "slice_revisions": dict(self.slice_revisions or {}),
            "scope": self.scope,
            "specimen_id": self.specimen_id,
            "part_id": self.part_id,
            "reslice_id": self.reslice_id,
            "role": self.role,
            "reason": self.reason,
        }


class TifLabelEditService:
    def editable_role_for_scope(self, scope):
        return "editable_ai_result" if str(scope or "") == "part" else "working_edit"

    def can_edit_role(self, role, *, scope="top_level"):
        guard = require_editable_label_role(role, scope="part" if scope == "part" else "top_level")
        if guard:
            return service_ok("label_role_editable", role=role, scope=scope)
        return service_blocked(guard.reason, reasons=[guard.reason], role=role, scope=scope)

    def can_save_role(self, role, *, scope="top_level", reason="manual", context=None):
        operation = "auto_save" if str(reason or "") == "auto_save" else "manual_save"
        guard = can_write_label_role(
            role,
            operation=operation,
            audit_metadata=dict(context or {}),
            overwrite_existing=True,
        )
        if guard:
            return service_ok("label_save_allowed", role=role, scope=scope, operation=operation)
        return service_blocked(guard.reason, reasons=[guard.reason], role=role, scope=scope, operation=operation)

    def build_save_request(
        self,
        *,
        edit_volume,
        dirty_slices,
        edit_slice_revisions=None,
        edit_path="",
        scope="top_level",
        specimen_id="",
        part_id="",
        reslice_id="",
        role="",
        reason="manual",
    ):
        if edit_volume is None:
            return service_blocked("edit_volume_missing", reasons=["edit_volume_missing"])
        if not dirty_slices:
            return service_blocked("no_dirty_slices", reasons=["no_dirty_slices"])
        if not edit_path:
            return service_blocked("edit_path_missing", reasons=["edit_path_missing"])
        clean_scope = "part" if str(scope or "") == "part" else "top_level"
        clean_role = str(role or self.editable_role_for_scope(clean_scope))
        context = {
            "scope": clean_scope,
            "specimen_id": str(specimen_id or ""),
            "part_id": str(part_id or ""),
            "reslice_id": str(reslice_id or ""),
        }
        save_guard = self.can_save_role(clean_role, scope=clean_scope, reason=reason, context=context)
        if not save_guard:
            return save_guard
        slice_indices = sorted(int(z) for z in dirty_slices)
        slices = {}
        revisions = {}
        for z_index in slice_indices:
            if 0 <= z_index < int(edit_volume.shape[0]):
                slices[z_index] = np.asarray(edit_volume[z_index]).copy()
                revisions[z_index] = int((edit_slice_revisions or {}).get(z_index, 0))
        if not slices:
            return service_blocked("dirty_slices_out_of_bounds", reasons=["dirty_slices_out_of_bounds"])
        request = TifLabelSaveRequest(
            edit_path=str(edit_path or ""),
            slices=slices,
            slice_revisions=revisions,
            scope=clean_scope,
            specimen_id=str(specimen_id or ""),
            part_id=str(part_id or ""),
            reslice_id=str(reslice_id or ""),
            role=clean_role,
            reason=str(reason or "manual"),
        )
        return service_ok("label_save_request_ready", request=request.to_dict())
