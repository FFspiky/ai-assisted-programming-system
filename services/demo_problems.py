"""Original small teaching examples; only seeds new IDs, never overwrites user edits."""

DEMOS = [
    {
        "id": "DEMO-01",
        "title": "整数求和",
        "description": "<p>输入整数 n（1 ≤ n ≤ 100），输出从 1 到 n（包含 n）的整数之和。</p><h3>例子</h3><pre>输入：3\n输出：6</pre>",
        "code": "n = int(input())\ntotal = 0\nfor i in range(1, n):\n    total += i\nprint(total)\n",
        "input": "3\n",
        "cases": [("3\n", "6", True), ("1\n", "1", True), ("100\n", "5050", False)],
    },
    {
        "id": "DEMO-02",
        "title": "字符串末位字符",
        "description": "<p>输入一行非空字符串，输出最后一个字符。字符串长度为 1 到 100。</p><h3>例子</h3><pre>输入：code\n输出：e</pre>",
        "code": "text = input()\nprint(text[len(text)])\n",
        "input": "code\n",
        "cases": [("code\n", "e", True), ("a\n", "a", True), ("hello\n", "o", False)],
    },
    {
        "id": "DEMO-03",
        "title": "两数相加",
        "description": "<p>输入两行整数 a 和 b（0 ≤ a,b ≤ 100），输出它们的和。</p><h3>例子</h3><pre>输入：2\n3\n输出：5</pre>",
        "code": "a = input()\nb = input()\nprint(a + b)\n",
        "input": "2\n3\n",
        "cases": [("2\n3\n", "5", True), ("0\n1\n", "1", True), ("12\n8\n", "20", False)],
    },
]


def seed_demo_problems():
    from models import Problem, TestCase, db

    added = []
    for demo in DEMOS:
        if db.session.get(Problem, demo["id"]):
            continue
        db.session.add(
            Problem(
                id=demo["id"],
                title=demo["title"],
                description=demo["description"],
                judge_mode="text",
                category={"DEMO-01": "control", "DEMO-02": "strings", "DEMO-03": "basics"}[
                    demo["id"]
                ],
                tags={
                    "DEMO-01": ["循环", "边界条件"],
                    "DEMO-02": ["字符串", "索引"],
                    "DEMO-03": ["输入输出", "类型转换"],
                }[demo["id"]],
                source="智练 CodeLab 自编演示题",
            )
        )
        for stdin, expected, public in demo["cases"]:
            db.session.add(
                TestCase(
                    problem_id=demo["id"],
                    input_data=stdin,
                    expected_output=expected,
                    is_public=public,
                )
            )
        added.append(demo["id"])
    db.session.commit()
    return added
