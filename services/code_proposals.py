"""Exact, snapshot-bound edits. Never infer replacement ranges from diagnosis lines."""

import difflib

from config import MAX_CODE_CHARS
from models import CodeProposal, db
from services.ai_client import AIClientError


def apply_edits(base, edits):
    lines = base.split("\n")
    count = len(lines) - int(base.endswith("\n"))
    if not isinstance(edits, list) or not 1 <= len(edits) <= 3:
        raise AIClientError("局部修改缺少精确替换范围，请重新请求")
    previous_end, added = 0, 0
    clean = []
    for edit in edits:
        if not isinstance(edit, dict):
            raise AIClientError("修改格式不正确")
        start, end = edit.get("start_line"), edit.get("end_line")
        before, after = edit.get("before"), edit.get("after")
        if (
            type(start) is not int
            or type(end) is not int
            or not previous_end < start <= end <= count
            or not isinstance(before, str)
            or not isinstance(after, str)
        ):
            raise AIClientError("修改范围无效或重叠，请重新请求")
        if before != "\n".join(lines[start - 1 : end]) or before == after:
            raise AIClientError("修改前的代码与提交快照不一致，请重新请求")
        added += len(after.splitlines())
        if added > 8 or end - start + 1 > 8:
            raise AIClientError("局部修改过长，请选择完整参考")
        previous_end = end
        clean.append({"start_line": start, "end_line": end, "before": before, "after": after})
    for edit in reversed(clean):
        lines[edit["start_line"] - 1 : edit["end_line"]] = (
            edit["after"].split("\n") if edit["after"] else []
        )
    candidate = "\n".join(lines)
    if not candidate.strip() or len(candidate) > MAX_CODE_CHARS or candidate == base:
        raise AIClientError("候选代码为空、过长或没有变化，请重新请求")
    return candidate, clean


def ensure_proposal(record):
    if record.source != "panel" or record.requested_level not in {3, 4}:
        return None
    result = record.result or {}
    if result.get("status") != "supported" or not result.get("code"):
        return None
    existing = CodeProposal.query.filter_by(help_id=record.id).first()
    if existing:
        return existing
    base = record.request_snapshot["code"]
    if record.requested_level == 3:
        # Old responses remain readable but cannot be applied by guessing their range.
        if not result.get("edits"):
            return None
        candidate, edits = apply_edits(base, result["edits"])
    else:
        candidate, edits = result["code"], []
        if not candidate.strip() or len(candidate) > MAX_CODE_CHARS or candidate == base:
            return None
    proposal = CodeProposal(
        help_id=record.id,
        user_id=record.user_id,
        submission_id=record.submission_id,
        base_code=base,
        candidate_code=candidate,
        edits=edits,
    )
    db.session.add(proposal)
    return proposal


def code_diff(before, after):
    return list(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile="修改前",
            tofile="修改后",
            lineterm="",
            n=2,
        )
    )


def proposal_payload(proposal):
    return {
        "id": proposal.id,
        "help_id": proposal.help_id,
        "submission_id": proposal.submission_id,
        "base_code": proposal.base_code,
        "candidate_code": proposal.candidate_code,
        "diff": code_diff(proposal.base_code, proposal.candidate_code),
        "state": proposal.state,
        "revision": proposal.revision,
        "created_at": proposal.created_at.isoformat() + "Z",
    }
