from dataclasses import dataclass

from .tif_service_result import service_blocked, service_ok


@dataclass(frozen=True)
class TifPreviewRequest:
    mode: str
    cache_key: tuple
    message: str = ""
    roi_bbox: list = None
    owner: tuple = None
    budget_bytes: int = 0

    def to_dict(self):
        return {
            "mode": self.mode,
            "cache_key": self.cache_key,
            "message": self.message,
            "roi_bbox": self.roi_bbox,
            "owner": self.owner,
            "budget_bytes": self.budget_bytes,
        }


class TifVolumePreviewService:
    def _roi_key(self, roi_bbox=None):
        if roi_bbox is None:
            return None
        return tuple(tuple(int(value) for value in pair) for pair in roi_bbox)

    def build_cache_key(self, *, volume_path="", label_path="", mode="still", roi_bbox=None, mask_mode="image_only", scope="full", specimen_id="", part_id="", reslice_id=""):
        roi_tuple = tuple(tuple(int(v) for v in pair) for pair in (roi_bbox or []))
        return (
            str(scope or ""),
            str(specimen_id or ""),
            str(part_id or ""),
            str(reslice_id or ""),
            str(volume_path or ""),
            str(label_path or ""),
            str(mode or "still"),
            str(mask_mode or "image_only"),
            roi_tuple,
        )

    def build_workbench_preview_request(
        self,
        *,
        owner,
        shape,
        source_dtype,
        max_dim,
        preserve_source,
        algorithm,
        roi_bbox=None,
        texture_budget_bytes=0,
        mode="still",
        message="",
    ):
        clean_owner = tuple(owner or ("", "full", "", ""))
        clean_shape = tuple(int(value) for value in (shape or ()))
        clean_dtype = str(source_dtype or "")
        clean_max_dim = int(max_dim or 0)
        clean_algorithm = str(algorithm or "")
        roi_key = self._roi_key(roi_bbox)
        clean_budget = int(texture_budget_bytes or 0)
        cache_key = (
            clean_owner,
            clean_shape,
            clean_dtype,
            clean_max_dim,
            bool(preserve_source),
            clean_algorithm,
            roi_key,
            clean_budget,
        )
        return service_ok(
            "volume_preview_request_ready",
            request={
                "cache_key": cache_key,
                "owner": clean_owner,
                "shape": clean_shape,
                "source_dtype": clean_dtype,
                "max_dim": clean_max_dim,
                "preserve_source": bool(preserve_source),
                "algorithm": clean_algorithm,
                "roi_bbox": roi_bbox,
                "roi_key": roi_key,
                "texture_budget_bytes": clean_budget,
                "mode": "drag" if mode == "drag" else "still",
                "message": str(message or ""),
            },
        )

    def build_mask_preview_request(
        self,
        *,
        owner,
        shape,
        source_dtype,
        max_dim,
        mask_identity,
        algorithm,
        roi_bbox=None,
        mode="still",
        message="",
    ):
        clean_owner = tuple(owner or ("", "full", "", ""))
        clean_shape = tuple(int(value) for value in (shape or ()))
        clean_dtype = str(source_dtype or "")
        clean_max_dim = int(max_dim or 0)
        clean_algorithm = str(algorithm or "")
        roi_key = self._roi_key(roi_bbox)
        cache_key = (
            clean_owner,
            clean_shape,
            clean_dtype,
            clean_max_dim,
            int(mask_identity or 0),
            clean_algorithm,
            roi_key,
        )
        return service_ok(
            "volume_mask_preview_request_ready",
            request={
                "cache_key": cache_key,
                "owner": clean_owner,
                "shape": clean_shape,
                "source_dtype": clean_dtype,
                "max_dim": clean_max_dim,
                "algorithm": clean_algorithm,
                "roi_bbox": roi_bbox,
                "roi_key": roi_key,
                "mode": "drag" if mode == "drag" else "still",
                "message": str(message or ""),
            },
        )

    def build_preview_request(self, *, volume_path="", label_path="", mode="still", roi_bbox=None, mask_mode="image_only", scope="full", specimen_id="", part_id="", reslice_id="", budget_bytes=0):
        if not volume_path:
            return service_blocked("volume_path_missing", reasons=["volume_path_missing"])
        cache_key = self.build_cache_key(
            volume_path=volume_path,
            label_path=label_path,
            mode=mode,
            roi_bbox=roi_bbox,
            mask_mode=mask_mode,
            scope=scope,
            specimen_id=specimen_id,
            part_id=part_id,
            reslice_id=reslice_id,
        )
        request = TifPreviewRequest(
            mode=str(mode or "still"),
            cache_key=cache_key,
            roi_bbox=[list(pair) for pair in (roi_bbox or [])] if roi_bbox else None,
            owner=(str(specimen_id or ""), str(part_id or ""), str(reslice_id or "")),
            budget_bytes=int(budget_bytes or 0),
        )
        return service_ok("volume_preview_request_ready", request=request.to_dict())
