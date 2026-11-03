#!/usr/bin/env python3
"""Deterministic tests for the offline FAT/I-O CSV coverage checker."""
import csv
import io
import unittest

from check_fat_csv import HEADERS, review


def filled_record(**overrides):
    item = {
        "ID": "CASE-01",
        "Участок": "Демонстрационный участок",
        "Позиция": "XV-101",
        "Тип I/O": "DI",
        "Адрес ПЛК": "I0.0",
        "Начальные условия": "Стенд разрешён",
        "Проверочное воздействие": "Допущенная имитация",
        "Ожидается в ПЛК": "DI=TRUE",
        "Ожидается на HMI/SCADA": "Значение отображается",
        "Фактически": "Совпало со стендом",
        "Статус": "PASS",
        "Замечание": "",
        "Ответственный": "Демо-инженер",
        "Версия ПО": "DEMO-v1",
        "Дата": "2026-11-03",
    }
    item.update(overrides)
    return item


def report(records, strict=False, columns=HEADERS):
    data = io.StringIO()
    writer = csv.DictWriter(data, fieldnames=columns, delimiter=";", lineterminator="\n")
    writer.writeheader()
    for rec in records:
        writer.writerow(rec)
    data.seek(0)
    return review(csv.DictReader(data, delimiter=";"), strict=strict)


class FATCSVReviewTests(unittest.TestCase):
    def test_complete_pass(self):
        r = report([filled_record()], strict=True)
        self.assertEqual(r["exit_code"], 0)
        self.assertEqual(r["by_status"], {"PASS": 1})
        self.assertEqual(r["by_type"], {"DI": 1})

    def test_demo_examples_not_real(self):
        x = filled_record(ID="ПРИМЕР-01")
        r = report([x], strict=False)
        self.assertEqual(r["sample_rows_ignored"], 1)
        self.assertEqual(r["real_test_rows"], 0)
        self.assertEqual(r["exit_code"], 0)

    def test_blank_test_template_not_real(self):
        r = report([{"ID": "TEST-01"}], strict=False)
        self.assertEqual(r["blank_rows_ignored"], 1)
        self.assertEqual(r["real_test_rows"], 0)

    def test_duplicate_ids_report_line(self):
        r = report([filled_record(), filled_record()], strict=True)
        self.assertEqual(r["exit_code"], 2)
        self.assertTrue(any(x["code"] == "duplicate_id" and x["line"] == 3 for x in r["issues"]))

    def test_missing_expected_is_warning_then_strict_fails(self):
        x = filled_record(**{"Ожидается в ПЛК": ""})
        relaxed = report([x])
        strict = report([x], strict=True)
        self.assertEqual(relaxed["exit_code"], 0)
        self.assertGreater(relaxed["warnings"], 0)
        self.assertEqual(strict["exit_code"], 1)

    def test_pass_requires_documented_actual_result(self):
        x = filled_record(**{"Фактически": ""})
        r = report([x])
        self.assertEqual(r["exit_code"], 2)
        self.assertIn("missing_evidence", [p["code"] for p in r["issues"]])

    def test_fail_requires_defect_description(self):
        x = filled_record(Статус="FAIL", Замечание="")
        r = report([x])
        self.assertEqual(r["exit_code"], 2)
        self.assertIn("missing_defect", [p["code"] for p in r["issues"]])

    def test_com_diagnostic(self):
        r = report([filled_record(**{"Тип I/O": "COM", "Статус": "NOT_RUN"})])
        self.assertEqual(r["by_type"], {"COM": 1})
        self.assertEqual(r["by_status"], {"NOT_RUN": 1})

    def test_invalid_type_and_status(self):
        r = report([filled_record(**{"Тип I/O": "UNKNOWN", "Статус": "OKAY"})])
        self.assertEqual(r["exit_code"], 2)
        self.assertIn("invalid_type", [p["code"] for p in r["issues"]])
        self.assertIn("invalid_status", [p["code"] for p in r["issues"]])

    def test_bad_header(self):
        with self.assertRaisesRegex(ValueError, "Неверная структура CSV"):
            report([], columns=("ID",))

    def test_no_real_tests_strict(self):
        r = report([{"ID": "TEST-01"}], strict=True)
        self.assertEqual(r["exit_code"], 2)
        self.assertIn("no_real_tests", [p["code"] for p in r["issues"]])

    def test_leading_zero_bom_header(self):
        data = io.StringIO("\ufeff" + ";".join(HEADERS) + "\n")
        parsed = csv.DictReader(data, delimiter=";")
        # The production check_file explicitly uses encoding='utf-8-sig';
        # a raw text stream with an unstripped BOM is intentionally invalid.
        with self.assertRaises(ValueError):
            review(parsed)


if __name__ == "__main__":
    unittest.main()
