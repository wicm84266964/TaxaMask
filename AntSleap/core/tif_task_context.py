from dataclasses import dataclass


@dataclass(frozen=True)
class TifTaskContext:
    specimen_id: str = ""
    volume_scope: str = ""
    part_id: str = ""
    reslice_id: str = ""
    label_role: str = ""
    display_mode: str = ""
    request_key: str = ""

    def key(self):
        return (
            str(self.specimen_id or ""),
            str(self.volume_scope or ""),
            str(self.part_id or ""),
            str(self.reslice_id or ""),
            str(self.label_role or ""),
            str(self.display_mode or ""),
            str(self.request_key or ""),
        )

    def to_dict(self):
        return {
            "specimen_id": str(self.specimen_id or ""),
            "volume_scope": str(self.volume_scope or ""),
            "part_id": str(self.part_id or ""),
            "reslice_id": str(self.reslice_id or ""),
            "label_role": str(self.label_role or ""),
            "display_mode": str(self.display_mode or ""),
            "request_key": str(self.request_key or ""),
        }

    @classmethod
    def from_mapping(cls, payload=None):
        payload = payload if isinstance(payload, dict) else {}
        return cls(
            specimen_id=str(payload.get("specimen_id") or ""),
            volume_scope=str(payload.get("volume_scope") or payload.get("scope") or ""),
            part_id=str(payload.get("part_id") or ""),
            reslice_id=str(payload.get("reslice_id") or ""),
            label_role=str(payload.get("label_role") or payload.get("role") or ""),
            display_mode=str(payload.get("display_mode") or ""),
            request_key=str(payload.get("request_key") or payload.get("cache_key") or payload.get("task_key") or ""),
        )

    def matches(self, other, *, ignore_empty=True, fields=None):
        other = other if isinstance(other, TifTaskContext) else TifTaskContext.from_mapping(other)
        keys = fields or ("specimen_id", "volume_scope", "part_id", "reslice_id", "label_role", "display_mode", "request_key")
        for key in keys:
            left = str(getattr(self, key, "") or "")
            right = str(getattr(other, key, "") or "")
            if ignore_empty and (not left or not right):
                continue
            if left != right:
                return False
        return True


def tif_context_from_view(
    *,
    specimen_id="",
    volume_scope="",
    part_id="",
    reslice_id="",
    label_role="",
    display_mode="",
    request_key="",
):
    return TifTaskContext(
        specimen_id=str(specimen_id or ""),
        volume_scope=str(volume_scope or ""),
        part_id=str(part_id or ""),
        reslice_id=str(reslice_id or ""),
        label_role=str(label_role or ""),
        display_mode=str(display_mode or ""),
        request_key=str(request_key or ""),
    )
