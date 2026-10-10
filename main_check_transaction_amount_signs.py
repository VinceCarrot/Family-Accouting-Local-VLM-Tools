import csv
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path


YEAR = 2026
MONTHS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

TRANSACTION_HISTORY_DIR = (
    Path(__file__).resolve().parent / "static" / "data" / "transaction_history"
)
NUMERIC_AMOUNT_PATTERN = re.compile(
    r"^[+-]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d*)?|\.\d+)$"
)


def parse_amount(value: str) -> Decimal:
    """Parse stored amounts, including thousands separators and trailing CR."""
    normalized = re.sub(r"\s+CR$", "", value.strip(), flags=re.IGNORECASE)
    return Decimal(normalized.replace(",", ""))


def is_numeric_amount(value: str) -> bool:
    """Return whether an amount contains only a numeric value and separators."""
    return NUMERIC_AMOUNT_PATTERN.fullmatch(value.strip()) is not None


def expected_sign(l0_category: str, l1_category: str) -> tuple[str, bool] | None:
    """Return the applicable rule and whether the amount should be negative."""
    l0 = l0_category.strip().lower()
    l1 = l1_category.strip().lower().replace(" ", "_")

    rules = []
    if l0 == "spend":
        rules.append(("l0=spend", True))
    elif l0 == "income":
        rules.append(("l0=income", False))

    if l1 == "transfer_out":
        rules.append(("l1=transfer_out", True))
    elif l1 == "transfer_in":
        rules.append(("l1=transfer_in", False))

    if not rules:
        return None
    if len({should_be_negative for _, should_be_negative in rules}) > 1:
        raise ValueError(f"Conflicting sign rules: {rules}")
    return rules[0]


def check_file(path: Path) -> tuple[int, list[str], list[str]]:
    checked = 0
    mismatches = []
    issues = []

    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        required_fields = {"amount", "l0_category", "l1_category"}
        if not reader.fieldnames or not required_fields.issubset(reader.fieldnames):
            return checked, mismatches, [
                f"{path.relative_to(TRANSACTION_HISTORY_DIR)}: missing required columns"
            ]

        for row in reader:
            if not any(value and value.strip() for value in row.values() if value):
                continue

            checked += 1
            relative_path = path.relative_to(TRANSACTION_HISTORY_DIR)
            raw_amount = row.get("amount") or ""
            amount_format_valid = is_numeric_amount(raw_amount)
            if not amount_format_valid:
                issues.append(
                    f"{relative_path}:{reader.line_num}: amount must be numeric "
                    f"{raw_amount!r}"
                )

            try:
                amount = parse_amount(raw_amount)
            except InvalidOperation:
                if amount_format_valid:
                    issues.append(
                        f"{relative_path}:{reader.line_num}: invalid amount "
                        f"{raw_amount!r}"
                    )
                continue

            try:
                rule = expected_sign(
                    row.get("l0_category") or "", row.get("l1_category") or ""
                )
            except ValueError as error:
                issues.append(f"{relative_path}:{reader.line_num}: {error}")
                continue

            if rule is None or amount == 0:
                continue

            rule_name, should_be_negative = rule
            if (amount < 0) != should_be_negative:
                mismatches.append(
                    f"{relative_path}:{reader.line_num}: amount={row.get('amount')!r}, "
                    f"rule={rule_name}, account={row.get('account', '')!r}, "
                    f"date={row.get('date', '')!r}, "
                    f"detail={row.get('transaction_detail', '')!r}"
                )

    return checked, mismatches, issues


def main() -> int:
    invalid_months = [month for month in MONTHS if not 1 <= month <= 12]
    if invalid_months:
        print(f"Invalid month values: {invalid_months}")
        return 2

    csv_files = []
    for month in MONTHS:
        month_dir = TRANSACTION_HISTORY_DIR / str(YEAR) / f"{month:02d}"
        if not month_dir.is_dir():
            print(f"Warning: directory not found: {month_dir.relative_to(TRANSACTION_HISTORY_DIR)}")
            continue
        csv_files.extend(sorted(month_dir.glob("*.csv")))

    checked = 0
    mismatches = []
    issues = []
    for path in csv_files:
        file_checked, file_mismatches, file_issues = check_file(path)
        checked += file_checked
        mismatches.extend(file_mismatches)
        issues.extend(file_issues)

    for mismatch in mismatches:
        print(f"SIGN MISMATCH: {mismatch}")
    for issue in issues:
        print(f"DATA ISSUE: {issue}")

    print(
        f"Scanned {len(csv_files)} CSV files and {checked} transactions "
        f"for {YEAR} months {MONTHS}; "
        f"sign mismatches: {len(mismatches)}, data issues: {len(issues)}."
    )
    return 1 if mismatches or issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
