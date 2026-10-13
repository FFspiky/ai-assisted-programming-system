"""Owned, optimistic and replay-safe practice actions."""

import hashlib
import json

from config import MAX_CODE_CHARS
from models import CodeProposal, PracticeEvent, Submission, db
from services.code_proposals import proposal_payload


class PracticeConflict(Exception):
    def __init__(self, message, status=409):
        super().__init__(message)
        self.status = status


def fingerprint(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def operation_key(data):
    value = data.get("operation_id")
    if not isinstance(value, str) or not 8 <= len(value) <= 64:
        raise PracticeConflict("操作标识无效，请刷新后重试", 400)
    return value


def owned_proposal(user_id, proposal_id):
    if type(proposal_id) is not int:
        raise PracticeConflict("建议不存在", 404)
    proposal = CodeProposal.query.filter_by(id=proposal_id, user_id=user_id).first()
    if not proposal:
        raise PracticeConflict("建议不存在", 404)
    base = Submission.query.filter_by(id=proposal.submission_id, user_id=user_id).first()
    if not base:
        raise PracticeConflict("原提交不存在", 404)
    return proposal, base


def action(user_id, proposal_id, data):
    proposal, base = owned_proposal(user_id, proposal_id)
    key = operation_key(data)
    digest = fingerprint({"proposal_id": proposal_id, **data})
    previous = PracticeEvent.query.filter_by(user_id=user_id, operation_id=key).first()
    if previous:
        if (
            previous.payload.get("fingerprint") != digest
            or previous.payload.get("revision") != proposal.revision
        ):
            raise PracticeConflict("操作记录已变化，请刷新后查看最新状态")
        return {
            "proposal": proposal_payload(proposal),
            "editor_code": previous.payload["after_code"],
            "replayed": True,
        }
    kind, revision, code = data.get("action"), data.get("revision"), data.get("code")
    if (
        kind not in {"accept", "reject", "undo"}
        or type(revision) is not int
        or not isinstance(code, str)
        or len(code) > MAX_CODE_CHARS
    ):
        raise PracticeConflict("操作参数不正确", 400)
    if data.get("language") != base.language:
        raise PracticeConflict("语言已改变，请回到该建议对应的语言")
    allowed = {
        "accept": {"pending", "rejected", "undone"},
        "reject": {"pending", "undone"},
        "undo": {"accepted"},
    }
    if proposal.revision != revision or proposal.state not in allowed[kind]:
        raise PracticeConflict("建议状态已改变，请刷新后重试")
    expected = proposal.candidate_code if kind == "undo" else proposal.base_code
    if kind != "reject" and code != expected:
        raise PracticeConflict("代码已继续编辑，不能覆盖当前内容。请先查看差异并手动调整。")
    after = (
        proposal.candidate_code
        if kind == "accept"
        else proposal.base_code if kind == "undo" else code
    )
    state = {"accept": "accepted", "reject": "rejected", "undo": "undone"}[kind]
    changed = CodeProposal.query.filter_by(id=proposal.id, revision=revision).update(
        {"state": state, "revision": revision + 1}, synchronize_session=False
    )
    if changed != 1:
        raise PracticeConflict("另一处已更新建议，请刷新后重试")
    db.session.add(
        PracticeEvent(
            user_id=user_id,
            problem_id=base.problem_id,
            language=base.language,
            submission_id=base.id,
            proposal_id=proposal.id,
            kind=kind,
            operation_id=key,
            payload={
                "fingerprint": digest,
                "revision": revision + 1,
                "before_code": code,
                "after_code": after,
            },
        )
    )
    db.session.commit()
    db.session.refresh(proposal)
    return {"proposal": proposal_payload(proposal), "editor_code": after, "replayed": False}
