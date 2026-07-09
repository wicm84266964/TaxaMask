from dataclasses import dataclass, field


@dataclass(frozen=True)
class ServiceResult:
    ok: bool
    message: str = ""
    action: str = ""
    payload: dict = field(default_factory=dict)
    reasons: list = field(default_factory=list)

    def __bool__(self):
        return bool(self.ok)

    def to_dict(self):
        return {
            "ok": bool(self.ok),
            "message": str(self.message or ""),
            "action": str(self.action or ""),
            "payload": dict(self.payload or {}),
            "reasons": list(self.reasons or []),
        }


def service_ok(message="", action="", **payload):
    return ServiceResult(True, message=str(message or ""), action=str(action or ""), payload=dict(payload or {}))


def service_blocked(message="", action="", reasons=None, **payload):
    return ServiceResult(
        False,
        message=str(message or ""),
        action=str(action or ""),
        payload=dict(payload or {}),
        reasons=list(reasons or []),
    )
