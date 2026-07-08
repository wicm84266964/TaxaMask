from .tif_service_result import service_blocked, service_ok


class TifTruthPromotionService:
    def __init__(self, project_manager):
        self.project = project_manager

    def split_review_acceptance_refs(self, refs, *, require_opened_for_review=False):
        report = self.project.build_part_review_acceptance_report(
            refs,
            require_opened_for_review=require_opened_for_review,
        )
        return service_ok(
            "review_acceptance_split",
            report=report,
            ready=list(report.get("ready") or []),
            not_opened=list(report.get("not_opened") or []),
            blocked=list(report.get("blocked") or []),
        )

    def promote_reviewed_refs(self, refs, *, require_opened_for_review=False, save=True):
        split = self.split_review_acceptance_refs(refs, require_opened_for_review=require_opened_for_review)
        blocked = list(split.payload.get("blocked") or [])
        ready = list(split.payload.get("ready") or [])
        if blocked:
            return service_blocked("part_review_not_ready", reasons=["part_review_not_ready"], blocked=blocked, ready=ready)
        if not ready:
            return service_blocked("no_review_ready_refs", reasons=["no_review_ready_refs"], ready=ready)
        result = self.project.promote_reviewed_part_results_to_manual_truth(
            ready,
            require_opened_for_review=False,
            save=save,
        )
        return service_ok("reviewed_refs_promoted", result=result, count=int(result.get("count", 0) or 0), ready=ready)
