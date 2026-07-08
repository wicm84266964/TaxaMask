from dataclasses import dataclass, field


@dataclass(frozen=True)
class TifEditState:
    dirty_slice_count: int = 0
    auto_save_running: bool = False
    manual_save_running: bool = False
    role: str = ""
    scope: str = ""

    def to_dict(self):
        return {
            "dirty_slice_count": int(self.dirty_slice_count or 0),
            "auto_save_running": bool(self.auto_save_running),
            "manual_save_running": bool(self.manual_save_running),
            "role": str(self.role or ""),
            "scope": str(self.scope or ""),
        }


@dataclass(frozen=True)
class TifPreviewState:
    display_mode: str = ""
    render_mode: str = ""
    preview_pending: bool = False
    preview_token: int = 0
    request_key: str = ""

    def to_dict(self):
        return {
            "display_mode": str(self.display_mode or ""),
            "render_mode": str(self.render_mode or ""),
            "preview_pending": bool(self.preview_pending),
            "preview_token": int(self.preview_token or 0),
            "request_key": str(self.request_key or ""),
        }


@dataclass(frozen=True)
class TifBackendState:
    running: bool = False
    action: str = ""
    run_dir: str = ""
    result_json: str = ""
    progress_value: int = 0

    def to_dict(self):
        return {
            "running": bool(self.running),
            "action": str(self.action or ""),
            "run_dir": str(self.run_dir or ""),
            "result_json": str(self.result_json or ""),
            "progress_value": int(self.progress_value or 0),
        }


@dataclass(frozen=True)
class TifRoiState:
    active_roi_id: str = ""
    roi_keyframe_count: int = 0
    mask_keyframe_count: int = 0
    confirm_running: bool = False
    mask_preview_running: bool = False

    def to_dict(self):
        return {
            "active_roi_id": str(self.active_roi_id or ""),
            "roi_keyframe_count": int(self.roi_keyframe_count or 0),
            "mask_keyframe_count": int(self.mask_keyframe_count or 0),
            "confirm_running": bool(self.confirm_running),
            "mask_preview_running": bool(self.mask_preview_running),
        }


@dataclass(frozen=True)
class TifLocalAxisState:
    draft_active: bool = False
    export_running: bool = False
    pick_target: str = ""
    specimen_id: str = ""
    part_id: str = ""
    reslice_id: str = ""
    roll_reference_keys: tuple = field(default_factory=tuple)

    def to_dict(self):
        return {
            "draft_active": bool(self.draft_active),
            "export_running": bool(self.export_running),
            "pick_target": str(self.pick_target or ""),
            "specimen_id": str(self.specimen_id or ""),
            "part_id": str(self.part_id or ""),
            "reslice_id": str(self.reslice_id or ""),
            "roll_reference_keys": list(self.roll_reference_keys or ()),
        }
