import re
from decimal import Decimal, DecimalException

from config import JUDGE_FLOAT_TOLERANCE

ANSWER_SEPARATOR = "---OR---"


def _normalize_lines(text):
    return "\n".join(line.rstrip() for line in str(text or "").strip().splitlines())


def split_expected_outputs(expected_output):
    options, current = [], []
    for line in str(expected_output or "").splitlines():
        if line.strip() == ANSWER_SEPARATOR:
            options.append("\n".join(current).strip())
            current = []
        else:
            current.append(line)
    options.append("\n".join(current).strip())
    return options


def outputs_match(actual_output, expected_output, mode="text"):
    actual = _normalize_lines(actual_output)
    return any(
        _single_output_matches(actual, option, mode)
        for option in split_expected_outputs(expected_output)
    )


def _single_output_matches(actual, expected_output, mode):
    expected = _normalize_lines(expected_output)
    if mode == "text":
        return actual == expected
    left, right = actual.split(), expected.split()
    if not left or len(left) != len(right):
        return False
    if mode == "integer":
        if not all(re.fullmatch(r"[+-]?\d+", token) for token in left + right):
            return False
        return all(Decimal(a) == Decimal(b) for a, b in zip(left, right, strict=True))
    if mode != "float":
        return False
    try:
        pairs = [(Decimal(a), Decimal(b)) for a, b in zip(left, right, strict=True)]
        tolerance = Decimal(str(JUDGE_FLOAT_TOLERANCE))
        return all(a.is_finite() and b.is_finite() and abs(a - b) <= tolerance for a, b in pairs)
    except DecimalException:
        return False
