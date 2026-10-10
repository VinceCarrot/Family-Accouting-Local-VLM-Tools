import csv
from pathlib import Path


YEAR = 2026
MONTHS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

TRANSACTION_HISTORY_DIR = (
    Path(__file__).resolve().parent / "static" / "data" / "transaction_history"
)


def check_file(path: Path) -> tuple[int, list[str], list[str]]:
    checked = 0
    missing_dates = []
    issues = []

    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        if not reader.fieldnames or "date" not in reader.fieldnames:
            return checked, missing_dates, [
                f"{path.relative_to(TRANSACTION_HISTORY_DIR)}: missing date column"
            ]

        for row in reader:
            if not any(value and value.strip() for value in row.values() if value):
                continue

            checked += 1
            date_value = row.get("date")
            if date_value is None or date_value == "":
                relative_path = path.relative_to(TRANSACTION_HISTORY_DIR)
                missing_dates.append(
                    f"{relative_path}:{reader.line_num}: "
                    f"account={row.get('account', '')!r}, "
                    f"amount={row.get('amount', '')!r}, "
                    f"detail={row.get('transaction_detail', '')!r}"
                )

    return checked, missing_dates, issues


def main() -> int:
    invalid_months = [month for month in MONTHS if not 1 <= month <= 12]
    if invalid_months:
        print(f"Invalid month values: {invalid_months}")
        return 2

    csv_files = []
    for month in MONTHS:
        month_dir = TRANSACTION_HISTORY_DIR / str(YEAR) / f"{month:02d}"
        if not month_dir.is_dir():
            print(
                "Warning: directory not found: "
                f"{month_dir.relative_to(TRANSACTION_HISTORY_DIR)}"
            )
            continue
        csv_files.extend(sorted(month_dir.glob("*.csv")))

    checked = 0
    missing_dates = []
    issues = []
    for path in csv_files:
        file_checked, file_missing_dates, file_issues = check_file(path)
        checked += file_checked
        missing_dates.extend(file_missing_dates)
        issues.extend(file_issues)

    for missing_date in missing_dates:
        print(f"EMPTY DATE: {missing_date}")
    for issue in issues:
        print(f"DATA ISSUE: {issue}")

    print(
        f"Scanned {len(csv_files)} CSV files and {checked} transactions "
        f"for {YEAR} months {MONTHS}; "
        f"empty dates: {len(missing_dates)}, data issues: {len(issues)}."
    )
    return 1 if missing_dates or issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
