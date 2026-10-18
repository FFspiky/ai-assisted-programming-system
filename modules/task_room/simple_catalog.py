"""Six small, original projects with finite rules and public acceptance cases.

This module is independent of catalog.py so its trusted reference functions can
also be assembled into standalone solve(data) source for the isolated runner.
"""

from __future__ import annotations

import inspect


def _simple_keys(value, required, label):
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError(f"{label} 字段不符合约定")


def _simple_integer(value, label, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{label} 必须是 {minimum} 至 {maximum} 的整数")
    return value


def _simple_string(value, label, maximum=40, allow_empty=False):
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError(f"{label} 必须是不超过 {maximum} 字的字符串")
    result = value.strip()
    if not result and not allow_empty:
        raise ValueError(f"{label} 不能为空")
    return result


def _simple_items(value, label):
    if not isinstance(value, list) or len(value) > 100:
        raise ValueError(f"{label} 必须是最多 100 项的数组")
    return value


def _validate_score_summary(data):
    _simple_keys(data, {"scores"}, "输入")
    return {
        "scores": [
            _simple_integer(score, "score", 0, 100)
            for score in _simple_items(data["scores"], "scores")
        ]
    }


def _score_summary_result(rules, data):
    scores = data["scores"]
    threshold = int(rules["threshold"])
    passed = sum(
        1
        for score in scores
        if (score >= threshold if rules["boundary"] == "inclusive" else score > threshold)
    )
    return {
        "count": len(scores),
        "total": sum(scores),
        "highest": max(scores, default=0),
        "passed": passed,
    }


def _validate_text_counter(data):
    _simple_keys(data, {"text"}, "输入")
    return {"text": _simple_string(data["text"], "text", 2000, allow_empty=True)}


def _text_counter_result(rules, data):
    words = data["text"].split()
    if rules["case"] == "fold":
        words = [word.lower() for word in words]
    counts = {}
    for word in words:
        counts[word] = counts.get(word, 0) + 1
    ordered = sorted(counts) if rules["order"] == "alphabetical" else list(counts)
    return {
        "count": len(words),
        "longest": max((len(word) for word in words), default=0),
        "words": [{"word": word, "count": counts[word]} for word in ordered],
    }


def _validate_shopping_total(data):
    _simple_keys(data, {"items", "delivery_cents"}, "输入")
    delivery = _simple_integer(data["delivery_cents"], "delivery_cents", 0, 100000)
    items = []
    for row in _simple_items(data["items"], "items"):
        _simple_keys(row, {"name", "price_cents", "quantity"}, "item")
        items.append(
            {
                "name": _simple_string(row["name"], "name"),
                "price_cents": _simple_integer(row["price_cents"], "price_cents", 0, 1000000),
                "quantity": _simple_integer(row["quantity"], "quantity", 0, 100),
            }
        )
    return {"items": items, "delivery_cents": delivery}


def _shopping_total_result(rules, data):
    quantity = sum(row["quantity"] for row in data["items"])
    subtotal = sum(row["price_cents"] * row["quantity"] for row in data["items"])
    net = subtotal * 90 // 100 if rules["discount"] == "ten_percent" else subtotal
    delivery = data["delivery_cents"] if rules["delivery"] == "always" or quantity else 0
    return {
        "quantity": quantity,
        "subtotal_cents": subtotal,
        "discount_cents": subtotal - net,
        "delivery_cents": delivery,
        "total_cents": net + delivery,
    }


def _validate_todo_sort(data):
    _simple_keys(data, {"tasks"}, "输入")
    tasks = []
    for row in _simple_items(data["tasks"], "tasks"):
        _simple_keys(row, {"title", "priority", "status"}, "task")
        if row["status"] not in ("pending", "done"):
            raise ValueError("status 只能是 pending 或 done")
        tasks.append(
            {
                "title": _simple_string(row["title"], "title"),
                "priority": _simple_integer(row["priority"], "priority", 1, 3),
                "status": row["status"],
            }
        )
    return {"tasks": tasks}


def _todo_sort_result(rules, data):
    tasks = [
        dict(row)
        for row in data["tasks"]
        if rules["visibility"] == "all" or row["status"] == "pending"
    ]
    if rules["order"] == "priority":
        tasks.sort(key=lambda row: -row["priority"])
    return {"tasks": tasks, "count": len(tasks)}


def _validate_study_checkin(data):
    _simple_keys(data, {"records"}, "输入")
    records = []
    for row in _simple_items(data["records"], "records"):
        _simple_keys(row, {"day", "minutes"}, "record")
        records.append(
            {
                "day": _simple_integer(row["day"], "day", 1, 31),
                "minutes": _simple_integer(row["minutes"], "minutes", 0, 1440),
            }
        )
    return {"records": records}


def _study_checkin_result(rules, data):
    daily = {}
    for row in data["records"]:
        day, minutes = row["day"], row["minutes"]
        daily[day] = (
            daily.get(day, 0) + minutes
            if rules["daily"] == "sum"
            else max(daily.get(day, 0), minutes)
        )
    goal = int(rules["goal"])
    days = [
        {"day": day, "minutes": daily[day], "met_goal": daily[day] >= goal} for day in sorted(daily)
    ]
    return {
        "days": days,
        "total_minutes": sum(daily.values()),
        "qualified_days": sum(1 for day in days if day["met_goal"]),
    }


def _validate_expense_summary(data):
    _simple_keys(data, {"expenses"}, "输入")
    expenses = []
    for row in _simple_items(data["expenses"], "expenses"):
        _simple_keys(row, {"category", "amount_cents"}, "expense")
        expenses.append(
            {
                "category": _simple_string(row["category"], "category"),
                "amount_cents": _simple_integer(row["amount_cents"], "amount_cents", 0, 1000000),
            }
        )
    return {"expenses": expenses}


def _expense_summary_result(rules, data):
    grouped = {}
    for row in data["expenses"]:
        amount = row["amount_cents"]
        if amount == 0 and rules["zeros"] == "skip":
            continue
        category = row["category"]
        if category not in grouped:
            grouped[category] = {"category": category, "total_cents": 0, "count": 0}
        grouped[category]["total_cents"] += amount
        grouped[category]["count"] += 1
    categories = list(grouped.values())
    if rules["order"] == "amount":
        categories.sort(key=lambda row: -row["total_cents"])
    return {
        "categories": categories,
        "total_cents": sum(row["total_cents"] for row in categories),
        "count": sum(row["count"] for row in categories),
    }


def _group(key, label, question, recommended, *options):
    return {
        "key": key,
        "label": label,
        "question": question,
        "recommended": recommended,
        "options": [
            {"value": value, "label": title, "description": description}
            for value, title, description in options
        ],
    }


def _change(change_id, title, message, **patch):
    return {"id": change_id, "title": title, "message": message, "patch": patch}


SIMPLE_SCENARIOS = [
    {
        "id": "score_summary",
        "title": "给一组成绩做个小统计",
        "subtitle": "学习委员 · 第一个循环项目",
        "difficulty": "零基础",
        "duration": "10–15 分钟",
        "level": "starter",
        "skills": ["basics", "loops", "lists", "testing"],
        "estimated_minutes": 15,
        "learning_goal": "用列表、循环和条件判断，统计数量、总分、最高分及达标人数。",
        "category": "成绩统计",
        "topics": ["campus", "data"],
        "client": {
            "name": "许晨",
            "role": "学习委员",
            "avatar": "许",
            "initial": "这次小测的分数出来了，我只需要人数、总分、最高分和达标人数。达标线取 60 还是 80？刚好压线算不算？咱们先定这两件事。",
        },
        "brief": "把整数成绩列表变成一份四项统计。没有学生时四项都返回 0；先确认分数线和压线规则。",
        "deliverable": "solve(data)：返回 count、total、highest 和 passed 四个整数。",
        "input_schema": '输入 {"scores": [0–100 的整数]}，最多 100 个分数；空列表合法。布尔值、浮点数及额外字段无效。',
        "output_schema": '输出 {"count": 人数, "total": 总分, "highest": 最高分, "passed": 达标人数}。空列表时均为 0。达标分数线和是否包含等号由规则决定；不计算平均数。',
        "rule_groups": [
            _group(
                "threshold",
                "达标分数线",
                "达到多少分才算达标？",
                "60",
                ("60", "60 分", "以 60 为达标线。"),
                ("80", "80 分", "以 80 为达标线。"),
            ),
            _group(
                "boundary",
                "刚好压线怎么办",
                "等于达标线算达标吗？",
                "inclusive",
                ("inclusive", "压线算达标", "分数大于或等于达标线。"),
                ("exclusive", "必须超过分数线", "分数严格大于达标线。"),
            ),
        ],
        "changes": [
            _change(
                "raise_threshold",
                "把目标提高到 80 分",
                "这次统计改为 80 分达标，压线规则保持合同约定。",
                threshold="80",
            ),
            _change(
                "strict_boundary",
                "需要真正超过分数线",
                "刚好压线不计入达标人数，请使用严格大于。",
                boundary="exclusive",
            ),
        ],
        "starter_code": 'def solve(data):\n    """按合同选定的分数线和压线规则统计。"""\n    scores = data["scores"]\n    # 累加总分，记录最高分，再用条件判断统计达标人数。\n    # 空列表的四个字段都应为 0。\n    return {"count": len(scores), "total": 0, "highest": 0, "passed": 0}\n',
        "example_input": {"scores": [58, 60, 80, 95]},
    },
    {
        "id": "text_counter",
        "title": "统计一小段文字里的单词",
        "subtitle": "英语角 · 字符串与计数",
        "difficulty": "零基础",
        "duration": "15–20 分钟",
        "level": "starter",
        "skills": ["basics", "strings", "loops", "dicts", "testing"],
        "estimated_minutes": 20,
        "learning_goal": "使用 split、字符串转换和字典计数，保留约定的结果顺序。",
        "category": "文字处理",
        "topics": ["campus", "data"],
        "client": {
            "name": "周可",
            "role": "英语角记录员",
            "avatar": "周",
            "initial": "我想知道英文小短文一共有几个词、最长的词多长、每个词用了几次。Hello 和 hello 要算一起吗？词频表按出现顺序还是字母顺序？",
        },
        "brief": "用空白切分短文，统计词数、最长词长度和逐词次数。不需要分词库，也不需要删除标点。",
        "deliverable": "solve(data)：返回 count、longest 和 words 词频列表。",
        "input_schema": '输入 {"text": 字符串}，原始长度最多 2000；空串及全空白合法。以 Python str.split() 的空白规则切词，连续空白不产生空词。标点保留，所以 hi 与 hi, 是不同词。',
        "output_schema": '输出 {"count": 词的总数, "longest": 规范化后最长词的字符数, "words": [{"word": 词, "count": 次数}]}。空文本返回 0、0、[]。大小写合并使用 str.lower()，长度在转换后统计。字母序采用 Python 字符串升序，出现序按规范化词首次出现。',
        "rule_groups": [
            _group(
                "case",
                "是否合并大小写",
                "Hello 和 hello 算同一个词吗？",
                "fold",
                ("fold", "转小写后合并", "每个词先执行 lower() 再计数。"),
                ("keep", "区分大小写", "词的原始大小写保留。"),
            ),
            _group(
                "order",
                "词频表顺序",
                "词频列表按什么顺序展示？",
                "appearance",
                ("appearance", "首次出现顺序", "按规范化后的词第一次出现的位置。"),
                ("alphabetical", "字母序", "按词字符串升序排列。"),
            ),
        ],
        "changes": [
            _change(
                "keep_case",
                "区分原文大小写",
                "老师要检查大写使用情况，请保留词的大小写，其他规则保持不变。",
                case="keep",
            ),
            _change(
                "alphabetical_words",
                "整理成字母表",
                "词频列表请改成按字符串升序排列。",
                order="alphabetical",
            ),
        ],
        "starter_code": 'def solve(data):\n    """先切词，按合同处理大小写，再计数和排序。"""\n    tokens = data["text"].split()\n    # 用字典记录每个词出现的次数。\n    # longest 在大小写处理后计算，空文本为 0。\n    return {"count": len(tokens), "longest": 0, "words": []}\n',
        "example_input": {"text": "Hello world hello Python"},
    },
    {
        "id": "shopping_total",
        "title": "算清一次小购物的金额",
        "subtitle": "宿舍采购 · 整数与简单运算",
        "difficulty": "零基础",
        "duration": "15–20 分钟",
        "level": "starter",
        "skills": ["basics", "loops", "lists", "business", "testing"],
        "estimated_minutes": 20,
        "learning_goal": "用单价乘数量并累加，以整数分计算折扣和配送费。",
        "category": "购物结算",
        "topics": ["daily"],
        "client": {
            "name": "陈米",
            "role": "宿舍采购员",
            "avatar": "陈",
            "initial": "帮宿舍买东西，每项有单价和数量，我想算总件数和最后付款金额。今天有九折活动，要不要启用？空购物单的配送费又怎么算？",
        },
        "brief": "对购物条目做简单乘法和累加，再处理整单折扣与配送费。全部金额以整数分表示，避免小数误差。",
        "deliverable": "solve(data)：返回件数、小计、折扣金额、实收配送费和总金额。",
        "input_schema": '输入 {"items": [{"name": 非空字符串, "price_cents": 0–1000000 的整数, "quantity": 0–100 的整数}], "delivery_cents": 0–100000 的整数}。最多 100 条，名称原始长度最多 40 并去除首尾空白。同名商品不合并，每行独立计费；数量为 0 合法。',
        "output_schema": '输出 {"quantity": 总件数, "subtotal_cents": 单价乘数量的总和, "discount_cents": 小计减折后金额, "delivery_cents": 实收配送费, "total_cents": 折后金额加配送费}。九折的折后金额为 subtotal_cents * 90 // 100，先算整单再向下取整到分；配送费不打折。空单和全零数量均属于总件数为 0。',
        "rule_groups": [
            _group(
                "delivery",
                "空单配送费",
                "总件数为 0 时收配送费吗？",
                "nonempty",
                ("nonempty", "有商品才收", "总件数大于 0 才收输入的配送费。"),
                ("always", "始终收取", "总件数为 0 也收输入的配送费。"),
            ),
            _group(
                "discount",
                "是否启用优惠",
                "商品小计要打九折吗？",
                "none",
                ("none", "原价", "商品小计不打折。"),
                ("ten_percent", "整单九折", "整单小计乘 90 再整除 100，配送费不打折。"),
            ),
        ],
        "changes": [
            _change(
                "activate_discount",
                "启用九折活动",
                "今天的商品小计统一九折，折后金额向下取整到分，配送费照旧。",
                discount="ten_percent",
            ),
            _change(
                "charge_empty_delivery",
                "保留空单服务费",
                "即使总件数为 0，也收取输入给出的配送费。",
                delivery="always",
            ),
        ],
        "starter_code": 'def solve(data):\n    """金额用整数分；先算小计，再按合同折扣及配送费。"""\n    quantity = 0\n    subtotal = 0\n    # 遍历 items，累加 quantity 与 price_cents * quantity。\n    # 折扣作用于整单小计，最后再加实收配送费。\n    return {"quantity": quantity, "subtotal_cents": subtotal, "discount_cents": 0, "delivery_cents": 0, "total_cents": 0}\n',
        "example_input": {
            "items": [
                {"name": "牛奶", "price_cents": 350, "quantity": 2},
                {"name": "面包", "price_cents": 599, "quantity": 1},
            ],
            "delivery_cents": 200,
        },
    },
    {
        "id": "todo_sort",
        "title": "把今天的待办排个顺序",
        "subtitle": "个人计划 · 筛选与稳定排序",
        "difficulty": "基础",
        "duration": "15–25 分钟",
        "level": "basic",
        "skills": ["loops", "lists", "sorting", "testing"],
        "estimated_minutes": 25,
        "learning_goal": "筛选列表记录，用稳定排序保留相同优先级的原始顺序。",
        "category": "待办整理",
        "topics": ["daily", "campus"],
        "client": {
            "name": "叶宁",
            "role": "学生志愿者",
            "avatar": "叶",
            "initial": "我的待办太乱了，每项有优先级和完成状态。先只看没完成的可以吗？安排顺序按原来的记录，还是优先做最紧急的？同级别别打乱。",
        },
        "brief": "从待办列表选出需要展示的任务，再按约定顺序排列。没有重复合并或状态变化，只需要一次筛选和可选排序。",
        "deliverable": "solve(data)：返回 tasks 列表和 count 数量。",
        "input_schema": '输入 {"tasks": [{"title": 非空字符串, "priority": 1–3 的整数, "status": "pending" 或 "done"}]}。最多 100 条；标题原始长度最多 40 并去除首尾空白。3 为最高优先级；相同标题仍是独立任务。',
        "output_schema": '输出 {"tasks": [{"title": 标题, "priority": 优先级, "status": 状态}], "count": 展示任务数}。筛选后按合同保留输入顺序，或按 priority 降序；相同优先级必须保持输入顺序。空结果为 [] 和 0。',
        "rule_groups": [
            _group(
                "visibility",
                "展示哪些任务",
                "已经完成的任务还要显示吗？",
                "pending",
                ("pending", "只显示待办", "只保留 status 为 pending 的记录。"),
                ("all", "显示全部", "保留 pending 和 done 的全部记录。"),
            ),
            _group(
                "order",
                "任务顺序",
                "先做高优先级的任务吗？",
                "input",
                ("input", "保持记录顺序", "筛选后保留输入顺序。"),
                ("priority", "高优先级在前", "priority 降序，同级保留输入顺序。"),
            ),
        ],
        "changes": [
            _change(
                "show_done",
                "回顾已经完成的工作",
                "列表改为展示全部任务，完成状态也要保留。",
                visibility="all",
            ),
            _change(
                "urgent_first",
                "紧急的事情先处理",
                "任务改按优先级从高到低，同级保持原始顺序。",
                order="priority",
            ),
        ],
        "starter_code": 'def solve(data):\n    """规范化标题，按合同筛选并稳定排序。"""\n    tasks = data["tasks"]\n    # 新建结果列表，保留需要展示的任务；不要按标题去重。\n    # 如需排序，3 在 2 前，2 在 1 前，同级保持原始顺序。\n    selected = []\n    return {"tasks": selected, "count": len(selected)}\n',
        "example_input": {
            "tasks": [
                {"title": "整理笔记", "priority": 1, "status": "pending"},
                {"title": "交作业", "priority": 3, "status": "pending"},
                {"title": "买文具", "priority": 2, "status": "done"},
            ]
        },
    },
    {
        "id": "study_checkin",
        "title": "汇总这个月的学习打卡",
        "subtitle": "学习搭子 · 按天汇总",
        "difficulty": "基础",
        "duration": "20–25 分钟",
        "level": "basic",
        "skills": ["loops", "dicts", "sorting", "testing"],
        "estimated_minutes": 25,
        "learning_goal": "用字典按天累计或取最大值，再按日期排序并判断目标。",
        "category": "学习打卡",
        "topics": ["campus", "daily", "data"],
        "client": {
            "name": "陆安",
            "role": "学习小组成员",
            "avatar": "陆",
            "initial": "同一天我可能学了好几次，想看每天的学习时长和达标天数。同一天是把时长加起来，还是只取最长一次？每天目标定 15 还是 30 分钟？",
        },
        "brief": "输入一个月内的学习记录，按天合并后输出日期顺序的小报表。无需处理真实日历或连续天数。",
        "deliverable": "solve(data)：返回每日汇总、总分钟数和达标天数。",
        "input_schema": '输入 {"records": [{"day": 1–31 的整数, "minutes": 0–1440 的整数}]}。最多 100 条；day 表示同一个月内的日号，无需年月。重复日期合法，零分钟记录也保留日期。',
        "output_schema": '输出 {"days": [{"day": 日号, "minutes": 该天合并分钟数, "met_goal": 布尔值}], "total_minutes": 各天合并分钟数总和, "qualified_days": 达标天数}。days 按 day 升序，每天只出现一次；合并后分钟数大于或等于目标即达标。空记录返回 []、0、0。合并后一天允许超过 1440。',
        "rule_groups": [
            _group(
                "daily",
                "同一天怎样合并",
                "同一天的多次学习要累加吗？",
                "sum",
                ("sum", "累加全部记录", "同一天每次学习的分钟数相加。"),
                ("max", "保留最长一次", "同一天只取最大的 minutes。"),
            ),
            _group(
                "goal",
                "每天学习目标",
                "达到多少分钟算一天达标？",
                "15",
                ("15", "15 分钟", "合并分钟数大于或等于 15。"),
                ("30", "30 分钟", "合并分钟数大于或等于 30。"),
            ),
        ],
        "changes": [
            _change(
                "longest_session",
                "每天只算最长一次",
                "同一天的重复打卡请保留最长一次，不再累加。",
                daily="max",
            ),
            _change(
                "half_hour_goal",
                "目标提高到半小时",
                "每天合并后的时长至少 30 分钟才算达标。",
                goal="30",
            ),
        ],
        "starter_code": 'def solve(data):\n    """按日号合并，排序后判断学习目标。"""\n    records = data["records"]\n    # 用字典以 day 为键，根据合同累加或取最大 minutes。\n    # 按 day 升序生成 days，每天标记 met_goal。\n    return {"days": [], "total_minutes": 0, "qualified_days": 0}\n',
        "example_input": {
            "records": [
                {"day": 3, "minutes": 10},
                {"day": 1, "minutes": 30},
                {"day": 3, "minutes": 8},
            ]
        },
    },
    {
        "id": "expense_summary",
        "title": "把零散花销汇总成分类账",
        "subtitle": "生活记账 · 字典分组",
        "difficulty": "基础",
        "duration": "20–30 分钟",
        "level": "basic",
        "skills": ["loops", "dicts", "sorting", "business", "testing"],
        "estimated_minutes": 30,
        "learning_goal": "按分类分组累计整数金额及笔数，处理零金额记录和稳定排序。",
        "category": "生活记账",
        "topics": ["daily", "data"],
        "client": {
            "name": "温梨",
            "role": "记账新手",
            "avatar": "温",
            "initial": "花销已经按餐饮、交通这些分类记好了，帮我汇总每类多少钱、几笔就行。零元订单算不算一笔？分类按第一次出现，还是花得最多的在前面？",
        },
        "brief": "把开销按类别累计金额和笔数。只做一种分组，不需要预算、退款、日期或账户。所有金额都用整数分。",
        "deliverable": "solve(data)：返回分类汇总、总金额和参与统计的总笔数。",
        "input_schema": '输入 {"expenses": [{"category": 非空字符串, "amount_cents": 0–1000000 的整数}]}。最多 100 条；分类原始长度最多 40，先去除首尾空白，之后同名类别合并。金额为 0 合法，不接受负数、浮点数或布尔值。',
        "output_schema": '输出 {"categories": [{"category": 类别, "total_cents": 类别金额总和, "count": 类别笔数}], "total_cents": 总金额, "count": 统计笔数}。零元过滤在分组前执行；跳过零元后没有记录的类别不出现。出现序按过滤后类别首次出现；金额序按类别总金额降序，金额相同保留过滤后的首次出现顺序。空结果返回 []、0、0。',
        "rule_groups": [
            _group(
                "order",
                "分类展示顺序",
                "分类账先显示哪个类别？",
                "appearance",
                ("appearance", "首次出现顺序", "按参与统计的类别首次出现顺序。"),
                ("amount", "花销最多在前", "总金额降序，同金额保留首次出现顺序。"),
            ),
            _group(
                "zeros",
                "零元订单计数",
                "零元订单也算一笔吗？",
                "keep",
                ("keep", "保留零元记录", "零元也占一笔，零元类别可单独出现。"),
                ("skip", "跳过零元记录", "先过滤 amount_cents 为 0 的记录，再分组。"),
            ),
        ],
        "changes": [
            _change(
                "largest_category_first",
                "先看花钱最多的类别",
                "分类按汇总金额降序，同金额保持首次出现顺序。",
                order="amount",
            ),
            _change(
                "ignore_free_orders",
                "零元订单不计入账本",
                "零元记录先跳过，不计笔数，也不单独留下类别。",
                zeros="skip",
            ),
        ],
        "starter_code": 'def solve(data):\n    """先按合同处理零元记录，再按类别累加整数分。"""\n    expenses = data["expenses"]\n    # 规范化 category，用字典累计 total_cents 和 count。\n    # 按合同生成出现序或金额降序的 categories。\n    return {"categories": [], "total_cents": 0, "count": 0}\n',
        "example_input": {
            "expenses": [
                {"category": "餐饮", "amount_cents": 1800},
                {"category": "交通", "amount_cents": 400},
                {"category": "餐饮", "amount_cents": 1200},
            ]
        },
    },
]


SIMPLE_CASES = {
    "score_summary": [
        ("empty", "空列表", {"scores": []}),
        ("boundary", "刚好等于两种分数线", {"scores": [59, 60, 61, 79, 80, 81]}),
        ("one", "只有一个分数", {"scores": [100]}),
        ("zeros", "全部零分", {"scores": [0, 0, 0]}),
        ("mixed", "无序分数与极值", {"scores": [80, 0, 95, 60, 100, 20]}),
        ("repeat", "重复分数仍按人数统计", {"scores": [60, 60, 80, 80]}),
    ],
    "text_counter": [
        ("empty", "全空白文本", {"text": " \t\n "}),
        ("whitespace", "连续空白分隔", {"text": " a\t b\n a  "}),
        ("case", "大小写与标点", {"text": "Hi hi HI hi, Hi"}),
        ("order", "首次出现与字母序", {"text": "zebra apple zebra banana"}),
        ("unicode", "Unicode 小写后的长度", {"text": "İ i 中文 中文"}),
        ("repeat", "重复单词与最长词", {"text": "a programming a b"}),
    ],
    "shopping_total": [
        ("empty", "空单配送费", {"items": [], "delivery_cents": 250}),
        (
            "normal",
            "单价乘数量",
            {"items": [{"name": "奶", "price_cents": 350, "quantity": 2}], "delivery_cents": 200},
        ),
        (
            "zero",
            "全零数量等同空单",
            {"items": [{"name": "面包", "price_cents": 599, "quantity": 0}], "delivery_cents": 100},
        ),
        (
            "rounding",
            "整单九折向下取整",
            {"items": [{"name": "糖", "price_cents": 101, "quantity": 1}], "delivery_cents": 3},
        ),
        (
            "multiple",
            "同名商品独立计费与免费商品",
            {
                "items": [
                    {"name": " 牛奶 ", "price_cents": 101, "quantity": 2},
                    {"name": "牛奶", "price_cents": 99, "quantity": 1},
                    {"name": "赠品", "price_cents": 0, "quantity": 3},
                ],
                "delivery_cents": 0,
            },
        ),
        (
            "maximum",
            "允许的大单金额",
            {
                "items": [{"name": "设备", "price_cents": 1000000, "quantity": 100}],
                "delivery_cents": 100000,
            },
        ),
    ],
    "todo_sort": [
        ("empty", "没有任务", {"tasks": []}),
        (
            "mixed",
            "完成状态与高优先级",
            {
                "tasks": [
                    {"title": "甲", "priority": 1, "status": "pending"},
                    {"title": "乙", "priority": 3, "status": "done"},
                    {"title": "丙", "priority": 2, "status": "pending"},
                ]
            },
        ),
        (
            "tie",
            "同优先级稳定排序",
            {
                "tasks": [
                    {"title": "丙", "priority": 3, "status": "pending"},
                    {"title": "甲", "priority": 3, "status": "pending"},
                    {"title": "乙", "priority": 1, "status": "pending"},
                ]
            },
        ),
        ("done", "全部已经完成", {"tasks": [{"title": "休息", "priority": 2, "status": "done"}]}),
        (
            "trim",
            "标题去除首尾空白",
            {"tasks": [{"title": " 交作业 ", "priority": 3, "status": "pending"}]},
        ),
        (
            "same_title",
            "同名任务不合并",
            {
                "tasks": [
                    {"title": "复习", "priority": 1, "status": "pending"},
                    {"title": "复习", "priority": 3, "status": "pending"},
                ]
            },
        ),
    ],
    "study_checkin": [
        ("empty", "没有打卡", {"records": []}),
        (
            "duplicate",
            "重复日期累加或取最大",
            {"records": [{"day": 3, "minutes": 10}, {"day": 3, "minutes": 8}]},
        ),
        (
            "boundary",
            "刚好达到目标",
            {"records": [{"day": 1, "minutes": 15}, {"day": 2, "minutes": 30}]},
        ),
        (
            "order",
            "日期升序与零分钟",
            {
                "records": [
                    {"day": 9, "minutes": 0},
                    {"day": 1, "minutes": 20},
                    {"day": 5, "minutes": 40},
                ]
            },
        ),
        (
            "zero",
            "零分钟日期仍保留",
            {"records": [{"day": 2, "minutes": 0}, {"day": 2, "minutes": 0}]},
        ),
        (
            "maximum",
            "月末与最大单次分钟数",
            {"records": [{"day": 31, "minutes": 1440}, {"day": 31, "minutes": 1440}]},
        ),
    ],
    "expense_summary": [
        ("empty", "没有花销", {"expenses": []}),
        (
            "group",
            "重复分类累加并排序",
            {
                "expenses": [
                    {"category": "交通", "amount_cents": 200},
                    {"category": "餐饮", "amount_cents": 800},
                    {"category": "交通", "amount_cents": 100},
                ]
            },
        ),
        (
            "tie",
            "相同总额保持首次出现",
            {
                "expenses": [
                    {"category": "乙", "amount_cents": 300},
                    {"category": "甲", "amount_cents": 300},
                ]
            },
        ),
        (
            "zeros",
            "零元类别与过滤后的首次顺序",
            {
                "expenses": [
                    {"category": "赠品", "amount_cents": 0},
                    {"category": "甲", "amount_cents": 0},
                    {"category": "乙", "amount_cents": 100},
                    {"category": "甲", "amount_cents": 100},
                ]
            },
        ),
        (
            "trim",
            "规范化分类名后合并",
            {
                "expenses": [
                    {"category": " 餐饮 ", "amount_cents": 101},
                    {"category": "餐饮", "amount_cents": 99},
                ]
            },
        ),
        (
            "maximum",
            "大额整数分与重复笔数",
            {
                "expenses": [
                    {"category": "设备", "amount_cents": 1000000},
                    {"category": "设备", "amount_cents": 1000000},
                ]
            },
        ),
    ],
}

SIMPLE_VALIDATORS = {
    "score_summary": _validate_score_summary,
    "text_counter": _validate_text_counter,
    "shopping_total": _validate_shopping_total,
    "todo_sort": _validate_todo_sort,
    "study_checkin": _validate_study_checkin,
    "expense_summary": _validate_expense_summary,
}
SIMPLE_SOLVERS = {
    "score_summary": _score_summary_result,
    "text_counter": _text_counter_result,
    "shopping_total": _shopping_total_result,
    "todo_sort": _todo_sort_result,
    "study_checkin": _study_checkin_result,
    "expense_summary": _expense_summary_result,
}


def simple_reference_code(scenario_id, rules):
    """Return trusted source with no imports or dependency on the host catalog."""
    validator, solver = SIMPLE_VALIDATORS[scenario_id], SIMPLE_SOLVERS[scenario_id]
    functions = [_simple_keys, _simple_integer, _simple_string, _simple_items, validator, solver]
    sources = "\n\n".join(inspect.getsource(function).strip() for function in functions)
    return (
        f"{sources}\n\n\ndef solve(data):\n"
        f"    return {solver.__name__}({rules!r}, {validator.__name__}(data))\n"
    )
