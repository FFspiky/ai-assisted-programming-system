"""Verify original task rules independently of Flask, Docker and paid AI APIs."""

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


def recommended(scenario_id):
    return {
        group["key"]: group["recommended"] for group in get_scenario(scenario_id)["rule_groups"]
    }


def all_rules(scenario):
    groups = scenario["rule_groups"]
    for choices in itertools.product(*(group["options"] for group in groups)):
        yield {
            group["key"]: option["value"] for group, option in zip(groups, choices, strict=False)
        }


class TaskRoomCatalogTest(unittest.TestCase):
    def test_catalog_is_complete_original_public_data_and_defensive_copy(self):
        catalog = list_catalog()
        self.assertEqual(len(catalog), 9)
        self.assertEqual(len({scenario["id"] for scenario in catalog}), 9)
        required = {
            "id",
            "title",
            "subtitle",
            "difficulty",
            "duration",
            "client",
            "brief",
            "deliverable",
            "input_schema",
            "output_schema",
            "rule_groups",
            "changes",
            "starter_code",
            "example_input",
            "level",
            "skills",
            "estimated_minutes",
            "learning_goal",
            "category",
            "topics",
        }
        for scenario in catalog:
            self.assertEqual(set(scenario), required)
            self.assertGreaterEqual(len(scenario["changes"]), 2)
            self.assertGreaterEqual(len(scenario["rule_groups"]), 2)
            self.assertEqual(set(scenario["client"]), {"name", "role", "initial", "avatar"})
            self.assertNotIn("reference_code", scenario)
            compile(scenario["starter_code"], "starter.py", "exec")
            for group in scenario["rule_groups"]:
                self.assertIn(
                    group["recommended"], {option["value"] for option in group["options"]}
                )
            for change in scenario["changes"]:
                validate_rules(scenario["id"], {**recommended(scenario["id"]), **change["patch"]})
        catalog[0]["client"]["name"] = "mutated"
        catalog[0]["rule_groups"].clear()
        self.assertNotEqual(get_scenario("signup_roster")["client"]["name"], "mutated")
        self.assertTrue(get_scenario("signup_roster")["rule_groups"])

    def test_complete_rules_are_required_without_silent_defaults(self):
        base = recommended("signup_roster")
        self.assertEqual(validate_rules("signup_roster", base), base)
        bad_rules = [
            None,
            [],
            {},
            {"identity": "phone"},
            {**base, "extra": "x"},
            {**base, "duplicate": "LAST"},
            {**base, "duplicate": True},
            {**base, "duplicate": []},
        ]
        for rules in bad_rules:
            with self.subTest(rules=rules), self.assertRaises(ValueError):
                validate_rules("signup_roster", rules)
        for scenario_id in [None, "missing", "", []]:
            with self.subTest(scenario_id=scenario_id), self.assertRaises(ValueError):
                get_scenario(scenario_id)

    def test_signup_independent_expected_phone_name_first_last_and_reporting(self):
        data = {
            "registrations": [
                {"name": " 甲 ", "phone": " 13800000001 ", "group": "首"},
                {"name": "乙", "phone": "13800000002"},
                {"name": "甲", "phone": "13800000003", "group": "更正"},
                {"name": "改名", "phone": "13800000001", "group": "末"},
                {"name": " ", "phone": ""},
                {"name": "丙", "phone": "１３８０００００００４"},
            ]
        }
        rules = recommended("signup_roster")
        result = evaluate_input("signup_roster", rules, data)
        self.assertEqual(
            result,
            {
                "roster": [
                    {"name": "甲", "phone": "13800000001", "group": "首"},
                    {"name": "乙", "phone": "13800000002", "group": "未分组"},
                    {"name": "甲", "phone": "13800000003", "group": "更正"},
                ],
                "rejected": [
                    {"index": 4, "reason": "empty_name"},
                    {"index": 5, "reason": "invalid_phone"},
                ],
                "duplicates": 1,
            },
        )
        latest = evaluate_input(
            "signup_roster", {**rules, "duplicate": "last", "invalid": "skip"}, data
        )
        self.assertEqual(
            latest["roster"][0], {"name": "改名", "phone": "13800000001", "group": "末"}
        )
        self.assertEqual(latest["rejected"], [])
        by_name = evaluate_input(
            "signup_roster", {**rules, "identity": "name", "duplicate": "last"}, data
        )
        self.assertEqual([row["name"] for row in by_name["roster"]], ["甲", "乙", "改名"])
        self.assertEqual(by_name["roster"][0]["phone"], "13800000003")
        self.assertEqual(by_name["duplicates"], 1)

    def test_signup_invalid_rows_do_not_participate_in_deduplication(self):
        rules = {**recommended("signup_roster"), "identity": "name", "duplicate": "first"}
        result = evaluate_input(
            "signup_roster",
            rules,
            {
                "registrations": [
                    {"name": "甲", "phone": "bad"},
                    {"name": "甲", "phone": "13800000001"},
                ]
            },
        )
        self.assertEqual(result["duplicates"], 0)
        self.assertEqual(result["roster"][0]["phone"], "13800000001")
        self.assertEqual(result["rejected"], [{"index": 0, "reason": "invalid_phone"}])

    def test_event_fifo_priority_cancellation_and_rejoin_have_distinct_results(self):
        data = {
            "capacity": 1,
            "requests": [
                {"user_id": " A ", "action": "join", "priority": 1},
                {"user_id": "B", "action": "join", "priority": 2},
                {"user_id": "A", "action": "join", "priority": 9},
                {"user_id": "A", "action": "cancel"},
                {"user_id": "A", "action": "cancel"},
                {"user_id": "X", "action": "cancel"},
                {"user_id": "A", "action": "join", "priority": 5},
            ],
        }
        rules = recommended("event_waitlist")
        self.assertEqual(
            evaluate_input("event_waitlist", rules, data),
            {"confirmed": ["A"], "waiting": ["B"], "duplicates": 2, "cancelled": 0},
        )
        release = {**rules, "cancellation": "release"}
        self.assertEqual(
            evaluate_input("event_waitlist", release, data),
            {"confirmed": ["B"], "waiting": ["A"], "duplicates": 1, "cancelled": 1},
        )
        self.assertEqual(
            evaluate_input("event_waitlist", {**release, "order": "priority"}, data),
            {"confirmed": ["A"], "waiting": ["B"], "duplicates": 1, "cancelled": 1},
        )
        latest = evaluate_input("event_waitlist", {**rules, "duplicate": "last"}, data)
        self.assertEqual(latest["confirmed"], ["B"])
        self.assertEqual(latest["duplicates"], 2)

    def test_event_priority_ties_and_zero_capacity(self):
        data = {
            "capacity": 0,
            "requests": [
                {"user_id": "C", "action": "join", "priority": 4},
                {"user_id": "A", "action": "join", "priority": 4},
                {"user_id": "B", "action": "join", "priority": 4},
            ],
        }
        result = evaluate_input(
            "event_waitlist", {**recommended("event_waitlist"), "order": "priority"}, data
        )
        self.assertEqual(result["confirmed"], [])
        self.assertEqual(result["waiting"], ["C", "A", "B"])

    def test_stock_independent_reject_partial_and_small_first_results(self):
        data = {
            "stock": {"袋": 5},
            "orders": [
                {"order_id": "A", "item": "袋", "quantity": 7},
                {"order_id": "B", "item": "袋", "quantity": 2},
            ],
        }
        rules = recommended("stock_orders")
        reject = evaluate_input("stock_orders", rules, data)
        self.assertEqual(reject["remaining"], {"袋": 3})
        self.assertEqual(
            reject["results"],
            [
                {
                    "order_id": "A",
                    "item": "袋",
                    "requested": 7,
                    "allocated": 0,
                    "status": "rejected",
                    "reason": "out_of_stock",
                },
                {
                    "order_id": "B",
                    "item": "袋",
                    "requested": 2,
                    "allocated": 2,
                    "status": "fulfilled",
                    "reason": "",
                },
            ],
        )
        partial = evaluate_input("stock_orders", {**rules, "insufficient": "partial"}, data)
        self.assertEqual(partial["remaining"], {"袋": 0})
        self.assertEqual([row["allocated"] for row in partial["results"]], [5, 0])
        self.assertEqual([row["status"] for row in partial["results"]], ["partial", "rejected"])
        small_first = evaluate_input(
            "stock_orders", {**rules, "insufficient": "partial", "allocation": "small_first"}, data
        )
        self.assertEqual([row["order_id"] for row in small_first["results"]], ["B", "A"])
        self.assertEqual([row["allocated"] for row in small_first["results"]], [2, 3])

    def test_stock_deduplicates_whole_order_before_allocation_and_moves_last_position(self):
        data = {
            "stock": {"袋": 3, "贴纸": 5},
            "orders": [
                {"order_id": "A", "item": "袋", "quantity": 3},
                {"order_id": "B", "item": "贴纸", "quantity": 4},
                {"order_id": "A", "item": "贴纸", "quantity": 2},
            ],
        }
        rules = {**recommended("stock_orders"), "duplicate": "last"}
        result = evaluate_input("stock_orders", rules, data)
        self.assertEqual(result["remaining"], {"袋": 3, "贴纸": 1})
        self.assertEqual([row["order_id"] for row in result["results"]], ["B", "A"])
        self.assertEqual(result["duplicates"], 1)
        self.assertEqual(result["results"][1]["allocated"], 0)

    def test_stock_unknown_item_zero_stock_and_exact_fulfillment(self):
        result = evaluate_input(
            "stock_orders",
            {**recommended("stock_orders"), "insufficient": "partial"},
            {
                "stock": {"袋": 0, "贴纸": 2},
                "orders": [
                    {"order_id": "A", "item": "未知", "quantity": 1},
                    {"order_id": "B", "item": "袋", "quantity": 1},
                    {"order_id": "C", "item": "贴纸", "quantity": 2},
                ],
            },
        )
        self.assertEqual(
            [row["reason"] for row in result["results"]], ["unknown_item", "out_of_stock", ""]
        )
        self.assertEqual(result["remaining"], {"袋": 0, "贴纸": 0})

    def test_all_rule_combinations_have_public_runnable_cases_without_mutation(self):
        count = 0
        for scenario in list_catalog():
            for rules in all_rules(scenario):
                with self.subTest(scenario=scenario["id"], rules=rules):
                    contract = build_contract(scenario["id"], rules, 2)
                    expected_count = 10 if scenario["level"] == "applied" else 6
                    self.assertEqual(len(contract["cases"]), expected_count)
                    self.assertEqual(
                        len({case["id"] for case in contract["cases"]}), expected_count
                    )
                    self.assertIn("全部验收案例公开", contract["spec"])
                    self.assertNotIn("reference_code", contract)
                    namespace = {}
                    # Only trusted, original reference source is executed in this unit test.
                    exec(
                        compile(reference_code(scenario["id"], rules), "reference.py", "exec"),
                        namespace,
                    )
                    for case in contract["cases"]:
                        original = copy.deepcopy(case["input"])
                        evaluated = evaluate_input(scenario["id"], rules, case["input"])
                        reference = namespace["solve"](case["input"])
                        self.assertEqual(evaluated, case["expected"])
                        self.assertEqual(reference, case["expected"])
                        self.assertEqual(case["input"], original)
                        if scenario["id"] == "stock_orders":
                            self.assertTrue(
                                all(value >= 0 for value in reference["remaining"].values())
                            )
                            for item, initial in case["input"]["stock"].items():
                                allocated = sum(
                                    row["allocated"]
                                    for row in reference["results"]
                                    if row["item"] == item.strip()
                                )
                                self.assertEqual(
                                    initial, reference["remaining"][item.strip()] + allocated
                                )
                        count += 1
        self.assertEqual(count, 384)

    def test_every_controlled_change_changes_at_least_one_public_case_when_needed(self):
        for scenario in list_catalog():
            for change in scenario["changes"]:
                rules = recommended(scenario["id"])
                for key, new_value in change["patch"].items():
                    group = next(group for group in scenario["rule_groups"] if group["key"] == key)
                    rules[key] = next(
                        option["value"]
                        for option in group["options"]
                        if option["value"] != new_value
                    )
                before = build_contract(scenario["id"], rules)
                after = build_contract(scenario["id"], {**rules, **change["patch"]}, 2)
                self.assertTrue(
                    any(
                        left["expected"] != right["expected"]
                        for left, right in zip(before["cases"], after["cases"], strict=False)
                    ),
                    change["id"],
                )

    def test_contract_data_is_detached_and_version_must_be_real_positive_integer(self):
        rules = recommended("signup_roster")
        contract = build_contract("signup_roster", rules)
        contract["cases"][0]["input"]["registrations"].append({"name": "x"})
        contract["rules"]["identity"] = "changed"
        self.assertEqual(
            build_contract("signup_roster", rules)["cases"][0]["input"], {"registrations": []}
        )
        self.assertEqual(rules["identity"], "phone")
        for version in [True, False, 0, -1, 1.0, "1", 10001]:
            with self.subTest(version=version), self.assertRaises(ValueError):
                build_contract("signup_roster", rules, version)

    def test_malformed_inputs_are_rejected_with_bounded_validation(self):
        bad_data = {
            "signup_roster": [
                None,
                [],
                {},
                {"registrations": [], "extra": 1},
                {"registrations": {}},
                {"registrations": [None]},
                {"registrations": [{"name": "x"}]},
                {"registrations": [{"name": True, "phone": "13800000001"}]},
                {"registrations": [{"name": "x", "phone": 13800000001}]},
                {"registrations": [{"name": "x", "phone": "13800000001", "group": []}]},
                {"registrations": [{"name": "x" * 41, "phone": "13800000001"}]},
                {"registrations": [{"name": "x", "phone": "13800000001"}] * 101},
            ],
            "event_waitlist": [
                {},
                {"capacity": True, "requests": []},
                {"capacity": 1.0, "requests": []},
                {"capacity": -1, "requests": []},
                {"capacity": 101, "requests": []},
                {"capacity": 1, "requests": [{"user_id": " ", "action": "join"}]},
                {"capacity": 1, "requests": [{"user_id": "x", "action": "unknown"}]},
                {"capacity": 1, "requests": [{"user_id": "x", "action": "join", "priority": True}]},
                {"capacity": 1, "requests": [{"user_id": "x", "action": "join", "priority": 10}]},
                {"capacity": 1, "requests": [{"user_id": "x", "action": "join", "other": 1}]},
                {"capacity": 1, "requests": [{"user_id": "x", "action": "join"}] * 101},
            ],
            "stock_orders": [
                {},
                {"stock": [], "orders": []},
                {"stock": {"x": True}, "orders": []},
                {"stock": {"x": -1}, "orders": []},
                {"stock": {"x": 10001}, "orders": []},
                {"stock": {str(index): 1 for index in range(31)}, "orders": []},
                {"stock": {"x": 1, " x ": 2}, "orders": []},
                {"stock": {"x": 1}, "orders": [{"order_id": "", "item": "x", "quantity": 1}]},
                {"stock": {"x": 1}, "orders": [{"order_id": "A", "item": "x", "quantity": 0}]},
                {"stock": {"x": 1}, "orders": [{"order_id": "A", "item": "x", "quantity": True}]},
                {"stock": {"x": 1}, "orders": [{"order_id": "A", "item": "x", "quantity": 1.5}]},
                {
                    "stock": {"x": 1},
                    "orders": [{"order_id": "A", "item": "x", "quantity": 1}] * 101,
                },
            ],
        }
        for scenario_id, invalid_inputs in bad_data.items():
            for data in invalid_inputs:
                with (
                    self.subTest(scenario_id=scenario_id, data=data),
                    self.assertRaises(ValueError),
                ):
                    evaluate_input(scenario_id, recommended(scenario_id), data)

    def test_boundary_maxima_and_input_strings_are_supported(self):
        event = evaluate_input(
            "event_waitlist",
            recommended("event_waitlist"),
            {
                "capacity": 100,
                "requests": [
                    {"user_id": str(index), "action": "join", "priority": 9} for index in range(100)
                ],
            },
        )
        self.assertEqual(len(event["confirmed"]), 100)
        self.assertEqual(event["waiting"], [])
        stock = evaluate_input(
            "stock_orders",
            recommended("stock_orders"),
            {
                "stock": {"x" * 32: 10000},
                "orders": [{"order_id": "A" * 32, "item": "x" * 32, "quantity": 10000}],
            },
        )
        self.assertEqual(stock["remaining"], {"x" * 32: 0})


if __name__ == "__main__":
    unittest.main()
