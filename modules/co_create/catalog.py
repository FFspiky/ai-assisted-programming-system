"""Three small finite rule families; only these trusted oracles run on the host."""

import copy
import json

CATALOG = {
    "dedupe": {
        "id": "dedupe",
        "title": "重复名单整理",
        "description": "同一名单有两种整理顺序。补一个例子，让程序知道你的意思。",
        "input_hint": '字符串列表，例如 ["A", "B", "A"]；最多 30 项，每项 40 字。',
        "seed_examples": [{"id": "seed-1", "input": ["A", "A", "B"], "expected": ["A", "B"]}],
        "probe": ["A", "B", "A"],
        "rule_options": [
            {"id": "first", "label": "按首次出现的顺序去重"},
            {"id": "last", "label": "按最后出现的顺序去重"},
        ],
        "review_rule": {
            "id": "first",
            "label": "重复名称只保留一次，并按首次出现的顺序输出。",
        },
    },
    "threshold": {
        "id": "threshold",
        "title": "达标数据筛选",
        "description": "恰好达到门槛算不算达标？用边界例子明确规则。",
        "input_hint": '对象，例如 {"values": [60, 70, 90], "threshold": 70}；整数 -1000 至 1000，最多 30 项。',
        "seed_examples": [
            {
                "id": "seed-1",
                "input": {"values": [50, 80, 90], "threshold": 60},
                "expected": [80, 90],
            }
        ],
        "probe": {"values": [50, 60, 80], "threshold": 60},
        "rule_options": [
            {"id": "inclusive", "label": "达到或超过门槛"},
            {"id": "exclusive", "label": "必须超过门槛"},
        ],
        "review_rule": {
            "id": "inclusive",
            "label": "按原顺序保留大于或等于 threshold 的整数，包括恰好达标的值。",
        },
    },
    "ordering": {
        "id": "ordering",
        "title": "数值排序约定",
        "description": "按数值还是按离零的距离排序？正数例子可能区分不出来。",
        "input_hint": "整数列表，例如 [-3, 1, 2]；整数 -1000 至 1000，最多 30 项。",
        "seed_examples": [{"id": "seed-1", "input": [3, 1, 2], "expected": [1, 2, 3]}],
        "probe": [-3, 1, 2],
        "rule_options": [
            {"id": "numeric", "label": "按数值从小到大"},
            {"id": "absolute", "label": "按绝对值从小到大，相同绝对值保持原顺序"},
        ],
        "review_rule": {
            "id": "numeric",
            "label": "将所有整数按数值从小到大排列，保留重复值。",
        },
    },
}

IMPLEMENTATIONS = {
    ("dedupe", "first"): "def solve(data):\n    return list(dict.fromkeys(data))\n",
    (
        "dedupe",
        "last",
    ): "def solve(data):\n    return list(reversed(list(dict.fromkeys(reversed(data)))))\n",
    (
        "threshold",
        "inclusive",
    ): "def solve(data):\n    return [x for x in data['values'] if x >= data['threshold']]\n",
    (
        "threshold",
        "exclusive",
    ): "def solve(data):\n    return [x for x in data['values'] if x > data['threshold']]\n",
    ("ordering", "numeric"): "def solve(data):\n    return sorted(data)\n",
    ("ordering", "absolute"): "def solve(data):\n    return sorted(data, key=abs)\n",
}


def get_scenario(scenario_id):
    if not isinstance(scenario_id, str) or scenario_id not in CATALOG:
        raise ValueError("请选择有效的小场景。")
    return copy.deepcopy(CATALOG[scenario_id])


def list_catalog():
    return [copy.deepcopy(s) for s in CATALOG.values()]


def validate_input(scenario_id, value):
    # JSON size is bounded separately from character-count and finite-family checks.
    if len(json.dumps(value, ensure_ascii=False, allow_nan=False)) > 4000:
        raise ValueError("单个输入最多 4000 字。")
    if scenario_id == "threshold":
        if not isinstance(value, dict) or set(value) != {"values", "threshold"}:
            raise ValueError("输入须只包含 values 与 threshold。")
        items = value["values"]
        if type(value["threshold"]) is not int or not -1000 <= value["threshold"] <= 1000:
            raise ValueError("threshold 须为 -1000 至 1000 的整数。")
    else:
        items = value
    if not isinstance(items, list) or len(items) > 30:
        raise ValueError("输入列表最多 30 项。")
    if scenario_id == "dedupe":
        if any(not isinstance(x, str) or not 1 <= len(x) <= 40 for x in items):
            raise ValueError("名单每项须为 1 至 40 字的字符串。")
    elif any(type(x) is not int or not -1000 <= x <= 1000 for x in items):
        raise ValueError("列表各项须为 -1000 至 1000 的整数。")
    return copy.deepcopy(value)


def validate_output(scenario_id, value):
    return validate_input("dedupe" if scenario_id == "dedupe" else "ordering", value)


def evaluate(scenario_id, rule_id, value):
    value = validate_input(scenario_id, value)
    valid = {r["id"] for r in CATALOG[scenario_id]["rule_options"]}
    if rule_id not in valid:
        raise ValueError("未知验收规则。")
    if scenario_id == "dedupe":
        if rule_id == "first":
            return list(dict.fromkeys(value))
        return list(reversed(list(dict.fromkeys(reversed(value)))))
    if scenario_id == "threshold":
        return (
            [x for x in value["values"] if x >= value["threshold"]]
            if rule_id == "inclusive"
            else [x for x in value["values"] if x > value["threshold"]]
        )
    return sorted(value) if rule_id == "numeric" else sorted(value, key=abs)
