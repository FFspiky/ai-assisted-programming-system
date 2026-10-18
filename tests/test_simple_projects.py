"""Independent expectations for the six beginner task-room projects."""

import copy
import itertools
import unittest

from modules.task_room.catalog import (
    build_contract,
    evaluate_input,
    get_scenario,
    list_catalog,
    reference_code,
    validate_rules,
)

SIMPLE_IDS = {
    "score_summary",
    "text_counter",
    "shopping_total",
    "todo_sort",
    "study_checkin",
    "expense_summary",
}


def recommended(scenario_id):
    return {
        group["key"]: group["recommended"] for group in get_scenario(scenario_id)["rule_groups"]
    }


def variants(scenario_id):
    groups = get_scenario(scenario_id)["rule_groups"]
    for choices in itertools.product(*(group["options"] for group in groups)):
        yield {
            group["key"]: option["value"] for group, option in zip(groups, choices, strict=False)
        }


class SimpleProjectsTest(unittest.TestCase):
    def assert_result(self, scenario_id, rules, data, expected):
        before = copy.deepcopy(data)
        self.assertEqual(evaluate_input(scenario_id, rules, data), expected)
        namespace = {}
        exec(compile(reference_code(scenario_id, rules), "trusted_reference.py", "exec"), namespace)
        self.assertEqual(namespace["solve"](data), expected)
        self.assertEqual(data, before)

    def test_all_metadata_supports_deterministic_learning_recommendations(self):
        allowed_skills = {
            "basics",
            "loops",
            "strings",
            "lists",
            "dicts",
            "sorting",
            "testing",
            "business",
        }
        allowed_topics = {"daily", "campus", "data"}
        catalog = list_catalog()
        self.assertEqual(len(catalog), 9)
        for scenario in catalog:
            with self.subTest(scenario=scenario["id"]):
                self.assertIn(scenario["level"], {"starter", "basic", "applied"})
                self.assertTrue(scenario["skills"])
                self.assertEqual(len(scenario["skills"]), len(set(scenario["skills"])))
                self.assertTrue(set(scenario["skills"]) <= allowed_skills)
                self.assertTrue(set(scenario["topics"]) <= allowed_topics)
                self.assertTrue(scenario["topics"])
                self.assertIs(type(scenario["estimated_minutes"]), int)
                self.assertGreater(scenario["estimated_minutes"], 0)
                self.assertTrue(scenario["learning_goal"])
                self.assertTrue(scenario["category"])
                self.assertEqual(len(scenario["client"]["avatar"]), 1)
                if scenario["id"] in SIMPLE_IDS:
                    self.assertIn(scenario["level"], {"starter", "basic"})
                    self.assertEqual(len(scenario["rule_groups"]), 2)
                    self.assertEqual(len(scenario["changes"]), 2)
                    self.assertLessEqual(scenario["estimated_minutes"], 30)
                else:
                    self.assertEqual(scenario["level"], "applied")
        catalog[-1]["skills"].clear()
        catalog[-1]["topics"].append("mutated")
        self.assertTrue(get_scenario("expense_summary")["skills"])
        self.assertNotIn("mutated", get_scenario("expense_summary")["topics"])

    def test_score_threshold_boundaries_empty_and_repeated_scores(self):
        data = {"scores": [0, 59, 60, 60, 61, 80, 81, 100]}
        expected_passed = {
            ("60", "inclusive"): 6,
            ("60", "exclusive"): 4,
            ("80", "inclusive"): 3,
            ("80", "exclusive"): 2,
        }
        for rules in variants("score_summary"):
            with self.subTest(rules=rules):
                self.assert_result(
                    "score_summary",
                    rules,
                    data,
                    {
                        "count": 8,
                        "total": 501,
                        "highest": 100,
                        "passed": expected_passed[(rules["threshold"], rules["boundary"])],
                    },
                )
                self.assert_result(
                    "score_summary",
                    rules,
                    {"scores": []},
                    {"count": 0, "total": 0, "highest": 0, "passed": 0},
                )

    def test_text_whitespace_case_punctuation_and_order(self):
        data = {"text": " Z\ta z  A\nhi, hi "}
        word_orders = {
            ("fold", "appearance"): [("z", 2), ("a", 2), ("hi,", 1), ("hi", 1)],
            ("fold", "alphabetical"): [("a", 2), ("hi", 1), ("hi,", 1), ("z", 2)],
            ("keep", "appearance"): [("Z", 1), ("a", 1), ("z", 1), ("A", 1), ("hi,", 1), ("hi", 1)],
            ("keep", "alphabetical"): [
                ("A", 1),
                ("Z", 1),
                ("a", 1),
                ("hi", 1),
                ("hi,", 1),
                ("z", 1),
            ],
        }
        for rules in variants("text_counter"):
            with self.subTest(rules=rules):
                expected_words = [
                    {"word": word, "count": count}
                    for word, count in word_orders[(rules["case"], rules["order"])]
                ]
                self.assert_result(
                    "text_counter", rules, data, {"count": 6, "longest": 3, "words": expected_words}
                )
                self.assert_result(
                    "text_counter",
                    rules,
                    {"text": " \t\n"},
                    {"count": 0, "longest": 0, "words": []},
                )
        self.assert_result(
            "text_counter",
            recommended("text_counter"),
            {"text": "İ"},
            {"count": 1, "longest": 2, "words": [{"word": "i\u0307", "count": 1}]},
        )

    def test_shopping_discount_uses_whole_integer_subtotal_before_delivery(self):
        data = {
            "items": [
                {"name": " 同名 ", "price_cents": 101, "quantity": 2},
                {"name": "同名", "price_cents": 99, "quantity": 1},
                {"name": "赠品", "price_cents": 0, "quantity": 1},
            ],
            "delivery_cents": 7,
        }
        for rules in variants("shopping_total"):
            with self.subTest(rules=rules):
                discounted = rules["discount"] == "ten_percent"
                self.assert_result(
                    "shopping_total",
                    rules,
                    data,
                    {
                        "quantity": 4,
                        "subtotal_cents": 301,
                        "discount_cents": 31 if discounted else 0,
                        "delivery_cents": 7,
                        "total_cents": 277 if discounted else 308,
                    },
                )
                fee = 7 if rules["delivery"] == "always" else 0
                for empty in [[], [{"name": "零件", "price_cents": 999, "quantity": 0}]]:
                    self.assert_result(
                        "shopping_total",
                        rules,
                        {"items": empty, "delivery_cents": 7},
                        {
                            "quantity": 0,
                            "subtotal_cents": 0,
                            "discount_cents": 0,
                            "delivery_cents": fee,
                            "total_cents": fee,
                        },
                    )

    def test_todo_filter_stable_priority_and_independent_same_titles(self):
        rows = [
            {"title": " 同名 ", "priority": 1, "status": "pending"},
            {"title": "完成", "priority": 3, "status": "done"},
            {"title": "同名", "priority": 3, "status": "pending"},
            {"title": "先后", "priority": 3, "status": "pending"},
        ]
        clean = [{**row, "title": row["title"].strip()} for row in rows]
        expected_indexes = {
            ("pending", "input"): [0, 2, 3],
            ("pending", "priority"): [2, 3, 0],
            ("all", "input"): [0, 1, 2, 3],
            ("all", "priority"): [1, 2, 3, 0],
        }
        for rules in variants("todo_sort"):
            with self.subTest(rules=rules):
                indices = expected_indexes[(rules["visibility"], rules["order"])]
                self.assert_result(
                    "todo_sort",
                    rules,
                    {"tasks": rows},
                    {"tasks": [clean[index] for index in indices], "count": len(indices)},
                )
                self.assert_result("todo_sort", rules, {"tasks": []}, {"tasks": [], "count": 0})

    def test_study_same_day_merge_before_goal_and_sorted_dates(self):
        data = {
            "records": [
                {"day": 31, "minutes": 15},
                {"day": 2, "minutes": 10},
                {"day": 2, "minutes": 8},
                {"day": 1, "minutes": 30},
                {"day": 3, "minutes": 0},
            ]
        }
        # Each tuple is (day 2 minutes, total, 15-minute qualified, 30-minute qualified).
        expected = {"sum": (18, 63, 3, 1), "max": (10, 55, 2, 1)}
        for rules in variants("study_checkin"):
            with self.subTest(rules=rules):
                second, total, low, high = expected[rules["daily"]]
                goal30 = rules["goal"] == "30"
                self.assert_result(
                    "study_checkin",
                    rules,
                    data,
                    {
                        "days": [
                            {"day": 1, "minutes": 30, "met_goal": True},
                            {
                                "day": 2,
                                "minutes": second,
                                "met_goal": not goal30 and rules["daily"] == "sum",
                            },
                            {"day": 3, "minutes": 0, "met_goal": False},
                            {"day": 31, "minutes": 15, "met_goal": not goal30},
                        ],
                        "total_minutes": total,
                        "qualified_days": high if goal30 else low,
                    },
                )
                self.assert_result(
                    "study_checkin",
                    rules,
                    {"records": []},
                    {"days": [], "total_minutes": 0, "qualified_days": 0},
                )

    def test_expense_zero_filter_precedes_grouping_and_stable_amount_sort(self):
        data = {
            "expenses": [
                {"category": "零", "amount_cents": 0},
                {"category": " 甲 ", "amount_cents": 0},
                {"category": "乙", "amount_cents": 100},
                {"category": "甲", "amount_cents": 100},
                {"category": "丙", "amount_cents": 200},
                {"category": "乙", "amount_cents": 0},
            ]
        }
        expected = {
            ("appearance", "keep"): [("零", 0, 1), ("甲", 100, 2), ("乙", 100, 2), ("丙", 200, 1)],
            ("amount", "keep"): [("丙", 200, 1), ("甲", 100, 2), ("乙", 100, 2), ("零", 0, 1)],
            ("appearance", "skip"): [("乙", 100, 1), ("甲", 100, 1), ("丙", 200, 1)],
            ("amount", "skip"): [("丙", 200, 1), ("乙", 100, 1), ("甲", 100, 1)],
        }
        for rules in variants("expense_summary"):
            with self.subTest(rules=rules):
                categories = [
                    {"category": category, "total_cents": amount, "count": count}
                    for category, amount, count in expected[(rules["order"], rules["zeros"])]
                ]
                self.assert_result(
                    "expense_summary",
                    rules,
                    data,
                    {
                        "categories": categories,
                        "total_cents": 400,
                        "count": 6 if rules["zeros"] == "keep" else 3,
                    },
                )
                self.assert_result(
                    "expense_summary",
                    rules,
                    {"expenses": []},
                    {"categories": [], "total_cents": 0, "count": 0},
                )

    def test_all_144_public_case_rule_combinations_are_standalone_and_detached(self):
        checked = 0
        for scenario_id in sorted(SIMPLE_IDS):
            for rules in variants(scenario_id):
                contract = build_contract(scenario_id, rules)
                self.assertEqual(len(contract["cases"]), 6)
                namespace = {}
                source = reference_code(scenario_id, rules)
                self.assertNotIn("from modules", source)
                exec(compile(source, "trusted_reference.py", "exec"), namespace)
                for case in contract["cases"]:
                    with self.subTest(scenario_id=scenario_id, rules=rules, case=case["id"]):
                        before = copy.deepcopy(case["input"])
                        self.assertEqual(namespace["solve"](case["input"]), case["expected"])
                        self.assertEqual(
                            evaluate_input(scenario_id, rules, case["input"]), case["expected"]
                        )
                        self.assertEqual(case["input"], before)
                        checked += 1
        self.assertEqual(checked, 144)

    def test_exact_rules_and_unknown_fields_are_rejected_for_every_simple_project(self):
        for scenario_id in sorted(SIMPLE_IDS):
            rules = recommended(scenario_id)
            valid = get_scenario(scenario_id)["example_input"]
            invalid = [None, [], {}, {**valid, "unknown": 1}]
            array_key = next((key for key, value in valid.items() if isinstance(value, list)), None)
            if array_key:
                invalid.extend(
                    [
                        {**valid, array_key: {}},
                        {**valid, array_key: [None]},
                        {**valid, array_key: valid[array_key][:1] * 101},
                    ]
                )
                if isinstance(valid[array_key][0], dict):
                    invalid.append({**valid, array_key: [{**valid[array_key][0], "unknown": 1}]})
            for data in invalid:
                with (
                    self.subTest(scenario_id=scenario_id, data=data),
                    self.assertRaises(ValueError),
                ):
                    evaluate_input(scenario_id, rules, data)
            for bad in [
                {},
                {**rules, "unknown": "x"},
                {**rules, next(iter(rules)): True},
                {**rules, next(iter(rules)): []},
            ]:
                with (
                    self.subTest(scenario_id=scenario_id, rules=bad),
                    self.assertRaises(ValueError),
                ):
                    validate_rules(scenario_id, bad)

    def test_numeric_and_string_bounds_reject_booleans_floats_and_oversize(self):
        shapes = {
            "score_summary": [(lambda value: {"scores": [value]}, 0, 100)],
            "shopping_total": [
                (lambda value: {"items": [], "delivery_cents": value}, 0, 100000),
                (
                    lambda value: {
                        "items": [{"name": "A", "price_cents": value, "quantity": 1}],
                        "delivery_cents": 0,
                    },
                    0,
                    1000000,
                ),
                (
                    lambda value: {
                        "items": [{"name": "A", "price_cents": 1, "quantity": value}],
                        "delivery_cents": 0,
                    },
                    0,
                    100,
                ),
            ],
            "todo_sort": [
                (
                    lambda value: {
                        "tasks": [{"title": "A", "priority": value, "status": "pending"}]
                    },
                    1,
                    3,
                )
            ],
            "study_checkin": [
                (lambda value: {"records": [{"day": value, "minutes": 0}]}, 1, 31),
                (lambda value: {"records": [{"day": 1, "minutes": value}]}, 0, 1440),
            ],
            "expense_summary": [
                (lambda value: {"expenses": [{"category": "A", "amount_cents": value}]}, 0, 1000000)
            ],
        }
        for scenario_id, fields in shapes.items():
            for shape, minimum, maximum in fields:
                for value in [True, False, 1.0, "1", minimum - 1, maximum + 1]:
                    with (
                        self.subTest(scenario_id=scenario_id, value=value),
                        self.assertRaises(ValueError),
                    ):
                        evaluate_input(scenario_id, recommended(scenario_id), shape(value))
                for value in [minimum, maximum]:
                    evaluate_input(scenario_id, recommended(scenario_id), shape(value))
        string_shapes = {
            "text_counter": (lambda value: {"text": value}, 2000, True),
            "shopping_total": (
                lambda value: {
                    "items": [{"name": value, "price_cents": 0, "quantity": 0}],
                    "delivery_cents": 0,
                },
                40,
                False,
            ),
            "todo_sort": (
                lambda value: {"tasks": [{"title": value, "priority": 1, "status": "pending"}]},
                40,
                False,
            ),
            "expense_summary": (
                lambda value: {"expenses": [{"category": value, "amount_cents": 0}]},
                40,
                False,
            ),
        }
        for scenario_id, (shape, maximum, allow_empty) in string_shapes.items():
            bad_values = [True, 123, None, "x" * (maximum + 1)]
            if not allow_empty:
                bad_values.extend(["", " \t"])
            for value in bad_values:
                with (
                    self.subTest(scenario_id=scenario_id, value=value),
                    self.assertRaises(ValueError),
                ):
                    evaluate_input(scenario_id, recommended(scenario_id), shape(value))
            evaluate_input(scenario_id, recommended(scenario_id), shape("x" * maximum))
        for status in [True, [], "unknown", "Pending", None]:
            with self.subTest(status=status), self.assertRaises(ValueError):
                evaluate_input(
                    "todo_sort",
                    recommended("todo_sort"),
                    {"tasks": [{"title": "A", "priority": 1, "status": status}]},
                )

    def test_maximum_row_counts_and_big_integer_totals_are_supported(self):
        shopping = evaluate_input(
            "shopping_total",
            {"delivery": "always", "discount": "ten_percent"},
            {
                "items": [{"name": "A", "price_cents": 1000000, "quantity": 100}] * 100,
                "delivery_cents": 100000,
            },
        )
        self.assertEqual(
            shopping,
            {
                "quantity": 10000,
                "subtotal_cents": 10000000000,
                "discount_cents": 1000000000,
                "delivery_cents": 100000,
                "total_cents": 9000100000,
            },
        )
        study = evaluate_input(
            "study_checkin",
            recommended("study_checkin"),
            {"records": [{"day": 31, "minutes": 1440}] * 100},
        )
        self.assertEqual(
            study,
            {
                "days": [{"day": 31, "minutes": 144000, "met_goal": True}],
                "total_minutes": 144000,
                "qualified_days": 1,
            },
        )
        expense = evaluate_input(
            "expense_summary",
            recommended("expense_summary"),
            {"expenses": [{"category": "A", "amount_cents": 1000000}] * 100},
        )
        self.assertEqual(
            expense,
            {
                "categories": [{"category": "A", "total_cents": 100000000, "count": 100}],
                "total_cents": 100000000,
                "count": 100,
            },
        )


if __name__ == "__main__":
    unittest.main()
