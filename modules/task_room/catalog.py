"""Original task briefs, explicit contracts and deterministic acceptance oracles.

The catalog contains no API keys, generated assessments or hidden acceptance cases.
AI may explain a rule, but only the user's enumerated choices determine the oracle.
"""

from __future__ import annotations

import copy
import inspect

from .simple_catalog import (
    SIMPLE_CASES,
    SIMPLE_SCENARIOS,
    SIMPLE_SOLVERS,
    SIMPLE_VALIDATORS,
    simple_reference_code,
)


def _object(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label} 必须是 JSON 对象")
    return value


def _keys(value, required, optional, label):
    _object(value, label)
    if not required.issubset(value) or set(value) - required - optional:
        raise ValueError(f"{label} 字段不符合约定")


def _string(value, label, maximum=40, allow_empty=False):
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError(f"{label} 必须是不超过 {maximum} 字的字符串")
    result = value.strip()
    if not result and not allow_empty:
        raise ValueError(f"{label} 不能为空")
    return result


def _integer(value, label, minimum=0, maximum=10000):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{label} 必须是 {minimum} 至 {maximum} 的整数")
    return value


def _items(value, label):
    if not isinstance(value, list) or len(value) > 100:
        raise ValueError(f"{label} 必须是最多 100 项的数组")
    return value


def _validate_signup(data):
    _keys(data, {"registrations"}, set(), "输入")
    result = []
    for index, row in enumerate(_items(data["registrations"], "registrations")):
        _keys(row, {"name", "phone"}, {"group"}, f"registrations[{index}]")
        result.append(
            {
                "name": _string(row["name"], "name", allow_empty=True),
                "phone": _string(row["phone"], "phone", 40, allow_empty=True),
                "group": _string(row.get("group", ""), "group", allow_empty=True) or "未分组",
            }
        )
    return {"registrations": result}


def _signup_result(rules, data):
    roster = []
    positions = {}
    rejected = []
    duplicates = 0
    for index, row in enumerate(data["registrations"]):
        # Only ASCII digits count; str.isdigit() also accepts other Unicode numerals.
        valid_phone = (
            len(row["phone"]) == 11
            and row["phone"].startswith("1")
            and all("0" <= digit <= "9" for digit in row["phone"])
        )
        reason = "empty_name" if not row["name"] else "invalid_phone" if not valid_phone else ""
        if reason:
            if rules["invalid"] == "report":
                rejected.append({"index": index, "reason": reason})
            continue
        identity = row[rules["identity"]]
        if identity in positions:
            duplicates += 1
            if rules["duplicate"] == "last":
                roster[positions[identity]] = dict(row)
        else:
            positions[identity] = len(roster)
            roster.append(dict(row))
    return {"roster": roster, "rejected": rejected, "duplicates": duplicates}


def _validate_event(data):
    _keys(data, {"capacity", "requests"}, set(), "输入")
    capacity = _integer(data["capacity"], "capacity", 0, 100)
    result = []
    for index, row in enumerate(_items(data["requests"], "requests")):
        _keys(row, {"user_id", "action"}, {"priority"}, f"requests[{index}]")
        user_id = _string(row["user_id"], "user_id", 32)
        if row["action"] not in ("join", "cancel"):
            raise ValueError("action 只能是 join 或 cancel")
        priority = _integer(row.get("priority", 0), "priority", 0, 9)
        result.append({"user_id": user_id, "action": row["action"], "priority": priority})
    return {"capacity": capacity, "requests": result}


def _event_result(rules, data):
    active = {}
    duplicates = 0
    cancelled = 0
    for index, row in enumerate(data["requests"]):
        user_id = row["user_id"]
        if row["action"] == "cancel":
            if rules["cancellation"] == "release" and user_id in active:
                del active[user_id]
                cancelled += 1
            continue
        if user_id in active:
            duplicates += 1
            if rules["duplicate"] == "first":
                continue
        active[user_id] = {"user_id": user_id, "priority": row["priority"], "index": index}
    ordered = sorted(
        active.values(),
        key=lambda row: (
            (-row["priority"], row["index"]) if rules["order"] == "priority" else (row["index"],)
        ),
    )
    identifiers = [row["user_id"] for row in ordered]
    return {
        "confirmed": identifiers[: data["capacity"]],
        "waiting": identifiers[data["capacity"] :],
        "duplicates": duplicates,
        "cancelled": cancelled,
    }


def _validate_stock(data):
    _keys(data, {"stock", "orders"}, set(), "输入")
    stock = _object(data["stock"], "stock")
    if len(stock) > 30:
        raise ValueError("stock 最多包含 30 种物资")
    normalized_stock = {}
    for item, quantity in stock.items():
        normalized = _string(item, "stock 物资名", 32)
        if normalized in normalized_stock:
            raise ValueError("stock 物资名去除首尾空白后不能重复")
        normalized_stock[normalized] = _integer(quantity, "stock 库存")
    orders = []
    for index, row in enumerate(_items(data["orders"], "orders")):
        _keys(row, {"order_id", "item", "quantity"}, set(), f"orders[{index}]")
        orders.append(
            {
                "order_id": _string(row["order_id"], "order_id", 32),
                "item": _string(row["item"], "item", 32),
                "quantity": _integer(row["quantity"], "quantity", 1),
                "index": index,
            }
        )
    return {"stock": normalized_stock, "orders": orders}


def _stock_result(rules, data):
    remaining = dict(data["stock"])
    unique = {}
    duplicates = 0
    for row in data["orders"]:
        order_id = row["order_id"]
        if order_id in unique:
            duplicates += 1
            if rules["duplicate"] == "first":
                continue
        unique[order_id] = row
    ordered = sorted(
        unique.values(),
        key=lambda row: (
            (row["quantity"], row["index"])
            if rules["allocation"] == "small_first"
            else (row["index"],)
        ),
    )
    results = []
    for row in ordered:
        item, requested = row["item"], row["quantity"]
        available = remaining.get(item, 0)
        allocated = (
            min(available, requested)
            if rules["insufficient"] == "partial"
            else requested if available >= requested else 0
        )
        if item not in remaining:
            allocated = 0
        if item in remaining:
            remaining[item] -= allocated
        status = "fulfilled" if allocated == requested else "partial" if allocated else "rejected"
        reason = (
            "unknown_item"
            if item not in remaining
            else "out_of_stock" if allocated < requested else ""
        )
        results.append(
            {
                "order_id": row["order_id"],
                "item": item,
                "requested": requested,
                "allocated": allocated,
                "status": status,
                "reason": reason,
            }
        )
    return {"remaining": remaining, "results": results, "duplicates": duplicates}


def _option(value, label, description):
    return {"value": value, "label": label, "description": description}


_SCENARIOS = [
    {
        "id": "signup_roster",
        "title": "把一份混乱报名表，交成可用名单",
        "subtitle": "社团迎新 · 数据清洗与去重",
        "difficulty": "入门",
        "duration": "25–40 分钟",
        "client": {
            "name": "林予",
            "role": "校园摄影社 · 活动负责人",
            "avatar": "林",
            "initial": "报名表有人重复填、名字带空格，还有空手机号。明天要按这份表拉活动群，你能帮我整理成一份名单吗？重复到底保留哪次，我们先商量清楚。",
        },
        "brief": "摄影社通过多个入口收集了报名记录。你要交付一个名单整理函数，先明确‘同一个人’的判定方式、重复记录的取舍与坏数据的去向，再用可复现案例验收。",
        "deliverable": "solve(data)：输出清洗后的名单、无效记录报告与重复次数。",
        "input_schema": '输入 {"registrations": [{"name": 字符串, "phone": 字符串, "group": 可选字符串}]}。最多 100 条；每个字段原始长度最多 40。姓名、手机号和分组去除首尾空白；空分组默认为“未分组”。合法手机号为 1 开头的 11 位 ASCII 数字，内部空格或连字符不删除。空姓名与非法手机号由所选坏数据规则处理。',
        "output_schema": '输出 {"roster": [{"name": 字符串, "phone": 字符串, "group": 字符串}], "rejected": [{"index": 从 0 开始的原始行号, "reason": "empty_name" 或 "invalid_phone"}], "duplicates": 整数}。名单按身份首次出现排序，保留最新内容也不改变该位置。无效行不参与去重；同时无效时优先报告 empty_name。',
        "rule_groups": [
            {
                "key": "identity",
                "label": "如何认定同一人",
                "question": "同名但手机号不同，算同一个报名人吗？",
                "recommended": "phone",
                "options": [
                    _option("phone", "按手机号去重", "同号视为同一人，同名不同号分别保留。"),
                    _option("name", "按姓名去重", "去除首尾空白后同名即合并，手机号不同也合并。"),
                ],
            },
            {
                "key": "duplicate",
                "label": "重复记录保留哪次",
                "question": "同一个人改了分组再次提交，用哪次内容？",
                "recommended": "first",
                "options": [
                    _option("first", "保留首次", "保留首次有效记录，后来重复的内容忽略。"),
                    _option(
                        "last", "保留最新", "以最后一条有效记录覆盖内容，名单位置仍按首次出现。"
                    ),
                ],
            },
            {
                "key": "invalid",
                "label": "无效记录如何交代",
                "question": "缺姓名或手机号的行，需要回报给负责人补录吗？",
                "recommended": "report",
                "options": [
                    _option("report", "跳过并报告", "名单排除无效行，同时按原始行号返回原因。"),
                    _option("skip", "直接跳过", "名单排除无效行，rejected 固定为空数组。"),
                ],
            },
        ],
        "changes": [
            {
                "id": "latest_submission",
                "title": "报名人可以改分组",
                "message": "有人报完又换了活动分组。请改为保留最后一次有效提交，名单次序仍按首次报名。",
                "patch": {"duplicate": "last"},
            },
            {
                "id": "name_identity",
                "title": "名单改为按姓名合并",
                "message": "这次名单用于线下签到，请按去除首尾空白后的姓名合并同一人，手机号不同也合并。其他规则不变。",
                "patch": {"identity": "name"},
            },
            {
                "id": "report_bad_rows",
                "title": "需要无效行补录清单",
                "message": "我需要逐条联系补录。无效记录请返回原始行号和原因，同时保留有效名单。",
                "patch": {"invalid": "report"},
            },
        ],
        "starter_code": 'def solve(data):\n    """输入报名记录；输出合同规定的三个字段。"""\n    registrations = data["registrations"]\n    roster = []\n    rejected = []\n    duplicates = 0\n    # 1. 去除各字段首尾空白，空分组使用“未分组”。\n    # 2. 根据合同检查姓名和手机号，处理无效行。\n    # 3. 按确认的身份与重复规则整理名单，保持首次出现顺序。\n    # registrations 中的原始行号从 0 开始。\n    return {"roster": roster, "rejected": rejected, "duplicates": duplicates}\n',
        "example_input": {
            "registrations": [
                {"name": " 小林 ", "phone": "13800000001", "group": "街拍"},
                {"name": "小林", "phone": "13800000001", "group": "人像"},
                {"name": "小周", "phone": "", "group": "街拍"},
            ]
        },
    },
    {
        "id": "event_waitlist",
        "title": "给满员活动，一份说得清的候补名单",
        "subtitle": "校园工作坊 · 名额与候补规则",
        "difficulty": "进阶",
        "duration": "35–50 分钟",
        "client": {
            "name": "程嘉",
            "role": "校园创客空间 · 运营同学",
            "avatar": "程",
            "initial": "我们的激光切割课只有几个名额，报名人数经常超出。有人重复报名、有人临时取消，也有志愿者优先名额。你能根据报名记录给我最终录取和候补名单吗？",
        },
        "brief": "一次活动从报名到截止会收到加入与取消事件。你要处理完整事件序列，按协商的队列规则在截止时生成最终名单，保证取消、重复和优先级的行为可以解释。",
        "deliverable": "solve(data)：输出最终录取名单、候补名单与事件处理统计。",
        "input_schema": '输入 {"capacity": 0–100 的整数, "requests": [{"user_id": 非空字符串, "action": "join" 或 "cancel", "priority": 可选的 0–9 整数，默认 0}]}。最多 100 条；user_id 原始长度最多 32，去除首尾空白。priority 数字越大越优先。布尔值不是整数。',
        "output_schema": '输出 {"confirmed": [user_id], "waiting": [user_id], "duplicates": 整数, "cancelled": 整数}。先按顺序处理全部事件，再对仍有效的报名排序；前 capacity 人录取，其余候补。duplicates 统计加入时已处于有效名单中的重复加入次数；cancelled 只统计按合同成功移除有效报名的取消次数。取消后再加入视为新报名。',
        "rule_groups": [
            {
                "key": "order",
                "label": "录取与候补的顺序",
                "question": "按报名先后，还是先满足高优先级报名？",
                "recommended": "fifo",
                "options": [
                    _option("fifo", "按报名先后", "按有效加入事件的位置排序，忽略 priority。"),
                    _option(
                        "priority", "优先级优先", "先按 priority 从高到低，同优先级按有效加入顺序。"
                    ),
                ],
            },
            {
                "key": "cancellation",
                "label": "取消是否释放名额",
                "question": "已报名的人取消后，要让候补自动进入吗？",
                "recommended": "ignore",
                "options": [
                    _option(
                        "ignore", "忽略取消事件", "所有 cancel 不改变有效报名，cancelled 为 0。"
                    ),
                    _option(
                        "release",
                        "取消并释放",
                        "移除该用户的有效报名，截止时重新分配名额。不存在的用户取消不计数。",
                    ),
                ],
            },
            {
                "key": "duplicate",
                "label": "重复报名如何处理",
                "question": "重复报名可以更新优先级或报名次序吗？",
                "recommended": "first",
                "options": [
                    _option(
                        "first",
                        "首次报名为准",
                        "有效报名期间的重复 join 只计数，不更新顺序或优先级。",
                    ),
                    _option(
                        "last",
                        "最新报名为准",
                        "重复 join 更新优先级，并把有效加入位置移到这次事件。",
                    ),
                ],
            },
        ],
        "changes": [
            {
                "id": "allow_cancel",
                "title": "开放取消与候补递补",
                "message": "活动允许临时退出了。取消有效报名后请释放名额，候补按既有排序规则递补；取消不存在的报名忽略。",
                "patch": {"cancellation": "release"},
            },
            {
                "id": "volunteer_priority",
                "title": "志愿者优先录取",
                "message": "priority 数字较大的报名请优先录取，同优先级仍按有效报名先后。取消与重复规则沿用当前合同。",
                "patch": {"order": "priority"},
            },
            {
                "id": "update_join",
                "title": "重复提交可更新报名",
                "message": "报名人可以重新提交优先级。重复 join 请采用最新 priority，并把加入顺序改为本次提交的位置。",
                "patch": {"duplicate": "last"},
            },
        ],
        "starter_code": 'def solve(data):\n    """按合同处理事件，然后在截止时分配名额。"""\n    capacity = data["capacity"]\n    requests = data["requests"]\n    active = {}\n    duplicates = 0\n    cancelled = 0\n    # 1. 顺序处理 join/cancel，记录有效加入的位置与 priority。\n    # 2. 应用合同约定的取消和重复规则。\n    # 3. 将有效报名按合同排序，再分成录取与候补名单。\n    ordered_ids = []\n    return {"confirmed": ordered_ids[:capacity], "waiting": ordered_ids[capacity:],\n            "duplicates": duplicates, "cancelled": cancelled}\n',
        "example_input": {
            "capacity": 2,
            "requests": [
                {"user_id": "A", "action": "join", "priority": 0},
                {"user_id": "B", "action": "join", "priority": 3},
                {"user_id": "C", "action": "join", "priority": 1},
                {"user_id": "A", "action": "cancel"},
            ],
        },
    },
    {
        "id": "stock_orders",
        "title": "让有限物资，按约定分到每张申请单",
        "subtitle": "校园市集 · 库存分配与重复订单",
        "difficulty": "进阶",
        "duration": "35–50 分钟",
        "client": {
            "name": "沈禾",
            "role": "校园公益市集 · 物资管理员",
            "avatar": "沈",
            "initial": "市集各摊位来领物资，但库存有限，申请单还会重复提交。库存不够时整单拒绝还是先发一部分？大单和小单谁先？这些规则我想跟你确认后再上线。",
        },
        "brief": "物资管理员提供初始库存和申请单。你要先处理重复订单，再按确认的分配顺序扣减库存，给出每单结果。每一份物资都必须能对上剩余数量。",
        "deliverable": "solve(data)：输出剩余库存、逐单分配结果和重复次数。",
        "input_schema": '输入 {"stock": {物资名: 0–10000 的整数}, "orders": [{"order_id": 非空字符串, "item": 非空字符串, "quantity": 1–10000 的整数}]}。最多 30 种物资、100 张申请；物资名与订单号原始长度最多 32，去除首尾空白；规范化后库存键不能重复。未知物资允许出现在订单中，结果为拒绝。布尔值不是整数。',
        "output_schema": '输出 {"remaining": {物资名: 剩余整数}, "results": [{"order_id": 字符串, "item": 字符串, "requested": 整数, "allocated": 整数, "status": "fulfilled"/"partial"/"rejected", "reason": ""/"out_of_stock"/"unknown_item"}], "duplicates": 整数}。先对 order_id 去重，保留首次或最新出现的整单和该次原始位置，再分配。results 按实际处理顺序。全部满足 reason 为空；有已知物资但未全部满足为 out_of_stock；未知物资为 unknown_item 且不加入 remaining。',
        "rule_groups": [
            {
                "key": "insufficient",
                "label": "库存不足怎么办",
                "question": "库存不够满足一单时，先发一部分还是整单拒绝？",
                "recommended": "reject",
                "options": [
                    _option("reject", "整单拒绝", "不足时 allocated 为 0，库存留给后续订单。"),
                    _option(
                        "partial",
                        "允许部分发放",
                        "按 min(剩余库存, 申请数量) 发放，数量大于 0 但不足时状态为 partial。",
                    ),
                ],
            },
            {
                "key": "allocation",
                "label": "按什么顺序发放",
                "question": "按提交先后，还是优先满足数量小的申请？",
                "recommended": "sequence",
                "options": [
                    _option("sequence", "提交先后", "去重后按保留记录的原始位置处理。"),
                    _option(
                        "small_first",
                        "小单优先",
                        "去重后按 quantity 从小到大，同数量按保留记录的位置处理。",
                    ),
                ],
            },
            {
                "key": "duplicate",
                "label": "同订单号以哪次为准",
                "question": "同一订单号换了数量甚至物资，采用哪一单？",
                "recommended": "first",
                "options": [
                    _option("first", "保留首次整单", "同号订单只保留第一次出现的所有字段与位置。"),
                    _option(
                        "last",
                        "保留最新整单",
                        "同号订单只保留最后一次出现的所有字段与位置，先去重再扣库存。",
                    ),
                ],
            },
        ],
        "changes": [
            {
                "id": "allow_partial",
                "title": "允许先领到一部分",
                "message": "库存紧张时可以先发一部分，请按剩余库存分配，部分满足标记 partial，库存为零仍是 rejected。",
                "patch": {"insufficient": "partial"},
            },
            {
                "id": "small_requests_first",
                "title": "先支持更多小摊位",
                "message": "请在订单去重后优先处理申请量小的单，同申请量按保留记录的原始提交位置排序。",
                "patch": {"allocation": "small_first"},
            },
            {
                "id": "latest_order",
                "title": "申请单允许更正",
                "message": "同订单号以最后一次提交的整单为准，物资和数量都可能变化，原始位置也以最后一次为准。先去重再扣库存。",
                "patch": {"duplicate": "last"},
            },
        ],
        "starter_code": 'def solve(data):\n    """先去重，再按合同分配；禁止出现负库存。"""\n    remaining = dict(data["stock"])\n    orders = data["orders"]\n    duplicates = 0\n    results = []\n    # 1. 规范化字符串，按订单号和合同规则去重。\n    # 2. 按约定顺序处理保留的申请单。\n    # 3. 区分未知物资、零库存、部分满足与全部满足。\n    # 4. 逐单记录 requested/allocated/status/reason，并扣减库存。\n    return {"remaining": remaining, "results": results, "duplicates": duplicates}\n',
        "example_input": {
            "stock": {"帆布袋": 5, "贴纸": 10},
            "orders": [
                {"order_id": "A", "item": "帆布袋", "quantity": 7},
                {"order_id": "B", "item": "帆布袋", "quantity": 2},
                {"order_id": "A", "item": "帆布袋", "quantity": 4},
            ],
        },
    },
]


def _registration(name, phone, group=""):
    return {"name": name, "phone": phone, "group": group}


def _request(user_id, action="join", priority=0):
    return {"user_id": user_id, "action": action, "priority": priority}


def _order(order_id, item, quantity):
    return {"order_id": order_id, "item": item, "quantity": quantity}


_CASES = {
    "signup_roster": [
        ("empty", "没有报名记录", {"registrations": []}),
        (
            "normal",
            "正常名单保持原序",
            {
                "registrations": [
                    _registration("小林", "13800000001", "街拍"),
                    _registration("小周", "13800000002", "人像"),
                ]
            },
        ),
        (
            "trim",
            "首尾空白与默认分组",
            {
                "registrations": [
                    {"name": " 小林 ", "phone": " 13800000001 "},
                    _registration("小周", "13800000002", "  "),
                ]
            },
        ),
        (
            "same_phone",
            "同号改名与换分组",
            {
                "registrations": [
                    _registration("小林", "13800000001", "街拍"),
                    _registration("林予", "13800000001", "人像"),
                ]
            },
        ),
        (
            "same_name",
            "同名但不同手机号",
            {
                "registrations": [
                    _registration("小林", "13800000001", "街拍"),
                    _registration("小林", "13800000002", "人像"),
                ]
            },
        ),
        (
            "invalid",
            "无效行的行号与原因",
            {
                "registrations": [
                    _registration("", "13800000001"),
                    _registration("小周", ""),
                    _registration(" ", "bad"),
                    _registration("小陈", "23800000001"),
                ]
            },
        ),
        (
            "phone_format",
            "内部空格和非 ASCII 数字",
            {
                "registrations": [
                    _registration("小甲", "138 0000001"),
                    _registration("小乙", "１３８０００００００１"),
                    _registration("小丙", "138-0000001"),
                    _registration("小丁", "13800000004"),
                ]
            },
        ),
        (
            "stable_position",
            "最新内容保持首次名单位置",
            {
                "registrations": [
                    _registration("甲", "13800000001", "旧"),
                    _registration("乙", "13800000002", "中"),
                    _registration("甲", "13800000001", "新"),
                    _registration("丙", "13800000003", "末"),
                ]
            },
        ),
        (
            "invalid_not_duplicate",
            "无效记录不消耗去重身份",
            {
                "registrations": [
                    _registration("甲", ""),
                    _registration("甲", "13800000001"),
                    _registration("", "13800000001"),
                    _registration("甲", "13800000001", "更新"),
                ]
            },
        ),
        (
            "repeated",
            "多次重复与独立身份",
            {
                "registrations": [
                    _registration("甲", "13800000001", "一"),
                    _registration("甲", "13800000001", "二"),
                    _registration("甲", "13800000001", "三"),
                    _registration("乙", "13800000002", "四"),
                ]
            },
        ),
    ],
    "event_waitlist": [
        ("empty", "空事件序列", {"capacity": 2, "requests": []}),
        ("zero", "名额为零时全部候补", {"capacity": 0, "requests": [_request("A"), _request("B")]}),
        (
            "overflow",
            "满员与候补顺序",
            {
                "capacity": 2,
                "requests": [_request("A"), _request("B"), _request("C"), _request("D")],
            },
        ),
        (
            "priority",
            "优先级改变录取顺序",
            {
                "capacity": 2,
                "requests": [
                    _request("A", priority=0),
                    _request("B", priority=9),
                    _request("C", priority=3),
                    _request("D", priority=9),
                ],
            },
        ),
        (
            "cancel",
            "有效报名取消后递补",
            {"capacity": 1, "requests": [_request("A"), _request("B"), _request("A", "cancel")]},
        ),
        (
            "unknown_cancel",
            "无效和重复取消不重复计数",
            {
                "capacity": 1,
                "requests": [
                    _request("X", "cancel"),
                    _request("A"),
                    _request("A", "cancel"),
                    _request("A", "cancel"),
                ],
            },
        ),
        (
            "duplicate",
            "重复加入更新位置和优先级",
            {
                "capacity": 1,
                "requests": [
                    _request("A", priority=1),
                    _request("B", priority=2),
                    _request("A", priority=9),
                ],
            },
        ),
        (
            "rejoin",
            "取消后重新报名",
            {
                "capacity": 1,
                "requests": [
                    _request("A"),
                    _request("B"),
                    _request("A", "cancel"),
                    _request("A", priority=5),
                ],
            },
        ),
        (
            "tie",
            "相同优先级的稳定顺序",
            {
                "capacity": 2,
                "requests": [
                    _request("C", priority=4),
                    _request("A", priority=4),
                    _request("B", priority=4),
                ],
            },
        ),
        (
            "trim",
            "规范化身份与默认优先级",
            {
                "capacity": 3,
                "requests": [
                    {"user_id": " A ", "action": "join"},
                    _request("B", priority=1),
                    _request("A", priority=3),
                    _request(" C ", "cancel"),
                ],
            },
        ),
    ],
    "stock_orders": [
        ("empty", "没有申请单", {"stock": {"袋": 5}, "orders": []}),
        ("empty_stock", "空库存中的未知物资", {"stock": {}, "orders": [_order("A", "袋", 1)]}),
        ("exact", "正好用尽库存", {"stock": {"袋": 5}, "orders": [_order("A", "袋", 5)]}),
        (
            "insufficient",
            "大单不足后小单能否领取",
            {"stock": {"袋": 5}, "orders": [_order("A", "袋", 7), _order("B", "袋", 2)]},
        ),
        (
            "ordering",
            "分配顺序影响结果",
            {
                "stock": {"袋": 5},
                "orders": [_order("A", "袋", 4), _order("B", "袋", 2), _order("C", "袋", 1)],
            },
        ),
        (
            "duplicate",
            "更正数量先去重再扣库存",
            {
                "stock": {"袋": 5},
                "orders": [_order("A", "袋", 4), _order("B", "袋", 2), _order("A", "袋", 1)],
            },
        ),
        (
            "replace_item",
            "同单更正物资与处理位置",
            {
                "stock": {"袋": 3, "贴纸": 5},
                "orders": [_order("A", "袋", 3), _order("B", "贴纸", 4), _order("A", "贴纸", 2)],
            },
        ),
        (
            "unknown_zero",
            "未知物资和零库存原因不同",
            {"stock": {"袋": 0}, "orders": [_order("A", "袋", 1), _order("B", "徽章", 1)]},
        ),
        (
            "tie",
            "小单相同数量按提交顺序",
            {
                "stock": {"袋": 3},
                "orders": [_order("C", "袋", 2), _order("A", "袋", 2), _order("B", "袋", 2)],
            },
        ),
        (
            "trim",
            "规范化订单号与物资名",
            {
                "stock": {" 袋 ": 5, "贴纸": 2},
                "orders": [_order(" A ", " 袋 ", 2), _order("A", "贴纸", 1), _order("B", "袋", 4)],
            },
        ),
    ],
}

_VALIDATORS = {
    "signup_roster": _validate_signup,
    "event_waitlist": _validate_event,
    "stock_orders": _validate_stock,
}
_SOLVERS = {
    "signup_roster": _signup_result,
    "event_waitlist": _event_result,
    "stock_orders": _stock_result,
}

# Keep the three multi-rule scenarios intact while sharing one public API with
# the smaller projects. Metadata is public and contains no reference answers.
_APPLIED_METADATA = {
    "signup_roster": {
        "skills": ["strings", "lists", "dicts", "testing", "business"],
        "estimated_minutes": 40,
        "learning_goal": "按约定清洗、验证和去重报名数据，交付可复现的名单。",
        "category": "报名管理",
        "topics": ["campus", "data"],
    },
    "event_waitlist": {
        "skills": ["lists", "dicts", "sorting", "testing", "business"],
        "estimated_minutes": 45,
        "learning_goal": "处理报名事件、取消和候补，把排序与状态规则组合成可靠结果。",
        "category": "活动候补",
        "topics": ["campus"],
    },
    "stock_orders": {
        "skills": ["loops", "dicts", "sorting", "testing", "business"],
        "estimated_minutes": 50,
        "learning_goal": "先去重再分配库存，验证顺序、数量和拒绝原因的一致性。",
        "category": "库存分配",
        "topics": ["campus", "daily", "data"],
    },
}
for _scenario in _SCENARIOS:
    _scenario.update({"level": "applied", **_APPLIED_METADATA[_scenario["id"]]})
_SCENARIOS.extend(SIMPLE_SCENARIOS)
_CASES.update(SIMPLE_CASES)
_VALIDATORS.update(SIMPLE_VALIDATORS)
_SOLVERS.update(SIMPLE_SOLVERS)


def list_catalog():
    """Return independent copies of all public, original scenario briefs."""
    return copy.deepcopy(_SCENARIOS)


def get_scenario(scenario_id):
    for scenario in _SCENARIOS:
        if scenario["id"] == scenario_id:
            return copy.deepcopy(scenario)
    raise ValueError("任务不存在，请重新选择任务")


def validate_rules(scenario_id, rules):
    scenario = get_scenario(scenario_id)
    _object(rules, "规则")
    groups = scenario["rule_groups"]
    if set(rules) != {group["key"] for group in groups}:
        raise ValueError("请明确确认全部规则，且不要添加合同之外的规则")
    normalized = {}
    for group in groups:
        value = rules[group["key"]]
        if not isinstance(value, str) or value not in {
            option["value"] for option in group["options"]
        }:
            raise ValueError(f"{group['label']} 的选项无效")
        normalized[group["key"]] = value
    return normalized


def evaluate_input(scenario_id, rules, data):
    """Evaluate bounded JSON on the host using the confirmed, finite rule model."""
    normalized = validate_rules(scenario_id, rules)
    valid_data = _VALIDATORS[scenario_id](data)
    return _SOLVERS[scenario_id](normalized, valid_data)


def build_contract(scenario_id, rules, version=1):
    normalized = validate_rules(scenario_id, rules)
    _integer(version, "合同版本", 1, 10000)
    scenario = get_scenario(scenario_id)
    labels = []
    for group in scenario["rule_groups"]:
        option = next(
            option for option in group["options"] if option["value"] == normalized[group["key"]]
        )
        labels.append(
            {
                "key": group["key"],
                "label": group["label"],
                "value": option["value"],
                "text": f"{option['label']}：{option['description']}",
            }
        )
    rule_text = "\n".join(
        f"{index}. {row['label']} — {row['text']}" for index, row in enumerate(labels, 1)
    )
    spec = (
        f"{scenario['title']}\n验收合同 v{version}\n\n{scenario['brief']}\n\n"
        f"交付物\n{scenario['deliverable']}\n\n已确认规则\n{rule_text}\n\n"
        f"输入约定\n{scenario['input_schema']}\n\n输出约定\n{scenario['output_schema']}\n\n"
        "实现所选语言的 solve(data)，返回 JSON 兼容的结果，不需要读取标准输入或打印结果。"
        "数组顺序属于合同；对象键顺序不影响验收；布尔值与整数不同。"
        "全部验收案例公开，期望值由已确认规则计算，AI 不参与判分。"
    )
    cases = [
        {
            "id": case_id,
            "name": name,
            "input": copy.deepcopy(data),
            "expected": evaluate_input(scenario_id, normalized, data),
        }
        for case_id, name, data in _CASES[scenario_id]
    ]
    return {
        "scenario_id": scenario_id,
        "version": version,
        "title": scenario["title"],
        "rules": normalized,
        "rule_labels": labels,
        "spec": spec,
        "input_schema": scenario["input_schema"],
        "output_schema": scenario["output_schema"],
        "cases": cases,
        "starter_code": scenario["starter_code"],
        "example_input": copy.deepcopy(scenario["example_input"]),
    }


def reference_code(scenario_id, rules):
    """Trusted verification source only; never returned by catalog/contract APIs."""
    normalized = validate_rules(scenario_id, rules)
    if scenario_id in SIMPLE_SOLVERS:
        return simple_reference_code(scenario_id, normalized)
    functions = [
        _object,
        _keys,
        _string,
        _integer,
        _items,
        _VALIDATORS[scenario_id],
        _SOLVERS[scenario_id],
    ]
    sources = "\n\n".join(inspect.getsource(function).strip() for function in functions)
    validator_name = _VALIDATORS[scenario_id].__name__
    solver_name = _SOLVERS[scenario_id].__name__
    return (
        f"{sources}\n\n\ndef solve(data):\n"
        f"    return {solver_name}({normalized!r}, {validator_name}(data))\n"
    )
