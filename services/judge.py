from config import JUDGE_FLOAT_TOLERANCE

ANSWER_SEPARATOR = "---OR---"


def _normalize_lines(text):
    return "\n".join(line.rstrip() for line in str(text or "").strip().splitlines())


def _as_float_tokens(text):
    tokens = str(text or "").strip().split()
    if not tokens:
        return None
    try:
        return [float(token) for token in tokens]
    except ValueError:
        return None


def outputs_match(actual_output, expected_output):
    actual_normalized = _normalize_lines(actual_output)
    expected_options = split_expected_outputs(expected_output)
    return any(_single_output_matches(actual_normalized, expected) for expected in expected_options)


def split_expected_outputs(expected_output):
    text = str(expected_output or "")
    options = []
    current_lines = []

    for line in text.splitlines():
        if line.strip() == ANSWER_SEPARATOR:
            option = "\n".join(current_lines).strip()
            if option:
                options.append(option)
            current_lines = []
            continue
        current_lines.append(line)

    option = "\n".join(current_lines).strip()
    if option:
        options.append(option)

    return options or [""]


def _single_output_matches(actual_normalized, expected_output):
    expected_normalized = _normalize_lines(expected_output)
    if actual_normalized == expected_normalized:
        return True

    actual_numbers = _as_float_tokens(actual_normalized)
    expected_numbers = _as_float_tokens(expected_normalized)
    if actual_numbers is None or expected_numbers is None:
        return False
    if len(actual_numbers) != len(expected_numbers):
        return False

    return all(
        abs(actual - expected) <= JUDGE_FLOAT_TOLERANCE
        for actual, expected in zip(actual_numbers, expected_numbers)
    )
