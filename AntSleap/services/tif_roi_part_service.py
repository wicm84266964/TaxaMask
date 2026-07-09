import numpy as np

from .tif_service_result import service_blocked, service_ok


class TifRoiPartService:
    def bbox_shape(self, bbox_zyx):
        try:
            return [max(0, int(pair[1]) - int(pair[0])) for pair in (bbox_zyx or [])]
        except Exception:
            return []

    def request_voxel_count(self, request):
        shape = self.bbox_shape((request or {}).get("bbox_zyx") or [])
        if len(shape) != 3:
            return 0
        return int(np.prod(shape, dtype=np.int64))

    def should_run_in_background(self, request, *, threshold):
        return self.request_voxel_count(request) >= int(threshold)

    def build_confirm_part_roi_request(
        self,
        *,
        specimen_id,
        part_id,
        display_name,
        bbox_zyx,
        source_shape_zyx,
        roi_id="",
        roi_metadata=None,
        roi_keyframes=None,
        mask_contours=None,
        mask_bbox_zyx=None,
        accepted_preview_mask=None,
    ):
        bbox = [list(pair) for pair in (bbox_zyx or [])]
        if len(bbox) != 3:
            return service_blocked("roi_bbox_required", reasons=["roi_bbox_required"])
        request = {
            "specimen_id": str(specimen_id or ""),
            "part_id": str(part_id or ""),
            "display_name": str(display_name or part_id or ""),
            "bbox_zyx": bbox,
            "source_shape_zyx": [int(value) for value in (source_shape_zyx or [])],
            "roi_id": str(roi_id or ""),
            "roi_metadata": dict(roi_metadata or {}),
            "roi_keyframes": list(roi_keyframes or []),
            "mask_contours": dict(mask_contours or {}),
            "mask_bbox_zyx": [list(pair) for pair in (mask_bbox_zyx or [])],
            "accepted_preview_mask": accepted_preview_mask,
        }
        return service_ok("confirm_part_roi_request_ready", request=request, voxel_count=self.request_voxel_count(request))
