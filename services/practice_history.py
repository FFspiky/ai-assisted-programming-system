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


def prepare_submission(user_id, data, code, language, problem_id):
    key = operation_key(data) if data.get("operation_id") is not None else None
    digest = fingerprint(
        {
            "code": code,
            "language": language,
            "problem_id": problem_id,
            "parent_submission_id": data.get("parent_submission_id"),
            "proposal_id": data.get("proposal_id"),
            "proposal_revision": data.get("proposal_revision"),
        }
    )
    if key:
        previous = PracticeEvent.query.filter_by(user_id=user_id, operation_id=key).first()
        if previous:
            if previous.kind != "retest" or previous.payload.get("fingerprint") != digest:
                raise PracticeConflict("操作标识已用于另一份代码，请重新提交")
            saved = Submission.query.filter_by(id=previous.submission_id, user_id=user_id).first()
            if not saved:
                raise PracticeConflict("先前提交记录不存在")
            return {"replay": saved}
    proposal, parent = None, None
    if data.get("parent_submission_id") is not None:
        parent_id = data["parent_submission_id"]
        if type(parent_id) is not int:
            raise PracticeConflict("原提交不存在", 404)
        parent = Submission.query.filter_by(id=parent_id, user_id=user_id).first()
        if not parent or parent.problem_id != problem_id or parent.language != language:
            raise PracticeConflict("原提交与本次题目或语言不匹配", 404)
    revision = data.get("proposal_revision")
    if data.get("proposal_id") is not None:
        proposal, base = owned_proposal(user_id, data["proposal_id"])
        if base.problem_id != problem_id or base.language != language:
            raise PracticeConflict("建议与当前题目或语言不匹配", 400)
        if (
            type(revision) is not int
            or proposal.revision != revision
            or proposal.state != "accepted"
        ):
            raise PracticeConflict("建议状态已改变，请刷新后再提交")
        if parent is None:
            parent = base
    return {
        "proposal": proposal,
        "revision": revision,
        "parent": parent,
        "key": key,
        "fingerprint": digest,
    }


def record_submission(context, submission):
    from services.code_proposals import code_diff

    proposal, parent = context["proposal"], context["parent"]
    if proposal:
        changed = CodeProposal.query.filter_by(
            id=proposal.id, revision=context["revision"], state="accepted"
        ).update({"revision": context["revision"] + 1}, synchronize_session=False)
        if changed != 1:
            raise PracticeConflict("判题期间建议状态已改变，本次记录未保存，请刷新后重新提交")
    before = (
        proposal.candidate_code
        if proposal
        else parent.code_submitted if parent else submission.code_submitted
    )
    db.session.flush()
    db.session.add(
        PracticeEvent(
            user_id=submission.user_id,
            problem_id=submission.problem_id,
            language=submission.language,
            submission_id=submission.id,
            proposal_id=proposal.id if proposal else None,
            kind="retest",
            operation_id=context["key"],
            payload={
                "fingerprint": context["fingerprint"],
                "parent_submission_id": parent.id if parent else None,
                "edited_after_accept": bool(proposal and before != submission.code_submitted),
                "diff": code_diff(before, submission.code_submitted),
                "proposal_revision": context["revision"] if proposal else None,
            },
        )
    )
