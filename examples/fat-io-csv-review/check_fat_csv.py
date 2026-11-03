#!/usr/bin/env python3
"""Offline review of the CSV FAT/I-O template published by DLV Automation.

This does not connect to PLCs, issue commands, verify wiring or certify safety.
It checks documentation completeness only. Python standard library, no network.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

HEADERS = (
    "ID", "Участок", "Позиция", "Тип I/O", "Адрес ПЛК",
    "Начальные условия", "Проверочное воздействие", "Ожидается в ПЛК",
    "Ожидается на HMI/SCADA", "Фактически", "Статус", "Замечание",
    "Ответственный", "Версия ПО", "Дата",
)
SIGNAL_TYPES = frozenset(("DI", "DO", "AI", "AO", "COM"))
STATUSES = frozenset(("PASS", "FAIL", "BLOCKED", "NOT_RUN"))
PRECONDITIONS = ("Участок", "Позиция", "Тип I/O", "Адрес ПЛК",
                 "Начальные условия", "Проверочное воздействие",
                 "Ожидается в ПЛК", "Ожидается на HMI/SCADA")
ACCEPTANCE = ("Фактически", "Ответственный", "Версия ПО", "Дата")


def issue(level: str, line: int, code: str, message: str) -> dict:
    return {"level": level, "line": line, "code": code, "message": message}


def review(reader: csv.DictReader, strict: bool = False) -> dict:
    """Return a deterministic QA report; do not touch hardware or network."""
    columns = reader.fieldnames
    if columns is None:
        raise ValueError("CSV пустой или заголовок отсутствует")
    missing = [name for name in HEADERS if name not in columns]
    duplicated = [name for name, count in Counter(columns).items() if count > 1]
    if missing or duplicated:
        raise ValueError(
            "Неверная структура CSV: отсутствуют "
            + ", ".join(missing or ["—"])
            + "; повторяются " + ", ".join(duplicated or ["—"])
        )
    # Extra named columns are kept for compatibility with local engineering notes.
    problems = []
    counts = Counter()
    statuses = Counter()
    seen_ids = {}
    samples = blanks = actual = 0

    for line_no, row in enumerate(reader, start=2):
        if None in row:
            problems.append(issue("error", line_no, "extra_cells",
                                  "Число ячеек превышает число колонок"))
            continue
        values = {key: (value or "").strip() for key, value in row.items()}
        if not any(values.values()):
            blanks += 1
            continue
        identifier = values["ID"]
        if identifier.upper().startswith("ПРИМЕР-"):
            samples += 1
            continue
        if (identifier.upper().startswith("TEST-") and
                not any(v for k, v in values.items() if k != "ID")):
            blanks += 1
            continue
        actual += 1
        if not identifier:
            problems.append(issue("error", line_no, "missing_id", "Не заполнен ID"))
        else:
            token = identifier.casefold()
            if token in seen_ids:
                problems.append(issue("error", line_no, "duplicate_id",
                                      f"ID повторяется (строка {seen_ids[token]})"))
            else:
                seen_ids[token] = line_no

        signal = values["Тип I/O"].upper()
        if signal not in SIGNAL_TYPES:
            problems.append(issue("error", line_no, "invalid_type",
                                  "Тип I/O должен быть DI, DO, AI, AO или COM"))
        else:
            counts[signal] += 1
        for field in PRECONDITIONS:
            if not values[field]:
                problems.append(issue("warning", line_no, "missing_input",
                                      f"Не заполнено поле «{field}»"))
        status = values["Статус"].upper()
        if not status:
            problems.append(issue("warning", line_no, "not_tested",
                                  "Статус не указан: результат не подтверждён"))
            statuses["EMPTY"] += 1
        elif status not in STATUSES:
            problems.append(issue("error", line_no, "invalid_status",
                                  "Используйте PASS, FAIL, BLOCKED или NOT_RUN"))
            statuses["INVALID"] += 1
        else:
            statuses[status] += 1
        if status in ("PASS", "FAIL"):
            for field in ACCEPTANCE:
                if not values[field]:
                    problems.append(issue("error", line_no, "missing_evidence",
                                          f"Для {status} нужно поле «{field}»"))
        if status == "FAIL" and not values["Замечание"]:
            problems.append(issue("error", line_no, "missing_defect",
                                  "FAIL требует описания замечания"))

    if strict and actual == 0:
        problems.append(issue("error", 0, "no_real_tests",
                              "Нет заполненных строк реального протокола"))
    errors = sum(p["level"] == "error" for p in problems)
    warnings = sum(p["level"] == "warning" for p in problems)
    exit_code = 2 if errors else (1 if strict and warnings else 0)
    return {
        "schema": "DLV FAT/I-O CSV 1.0",
        "real_test_rows": actual,
        "sample_rows_ignored": samples,
        "blank_rows_ignored": blanks,
        "by_type": dict(sorted(counts.items())),
        "by_status": dict(sorted(statuses.items())),
        "errors": errors,
        "warnings": warnings,
        "issues": problems,
        "exit_code": exit_code,
    }


def check_file(path: Path, strict: bool = False) -> dict:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return review(csv.DictReader(stream, delimiter=";", restkey=None),
                      strict=strict)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Проверка CSV-протокола FAT/I-O без связи с ПЛК")
    parser.add_argument("csv_file", type=Path, help="CSV с сайта DLV (UTF-8 BOM, разделитель ;)")
    parser.add_argument("--strict", action="store_true",
                        help="ошибка при незаполненных обязательных данных")
    parser.add_argument("--json", action="store_true",
                        help="машиночитаемый отчёт, без сохранения исходных данных")
    args = parser.parse_args(argv)
    try:
        result = check_file(args.csv_file, strict=args.strict)
    except (OSError, UnicodeError, csv.Error, ValueError) as exc:
        print(f"Ошибка проверки CSV: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("DLV FAT/I-O — проверка полноты протокола")
        print("Реальных строк:", result["real_test_rows"],
              "| примеров пропущено:", result["sample_rows_ignored"],
              "| пустых строк пропущено:", result["blank_rows_ignored"])
        print("Типы:", result["by_type"])
        print("Статусы:", result["by_status"])
        print("Ошибок:", result["errors"], "| предупреждений:", result["warnings"])
        for x in result["issues"]:
            print(f"{x['level']} строка {x['line']}: {x['message']}")
        print("Проверка не подтверждает безопасность, работоспособность I/O или завершение ПНР.")
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
