
import argparse
import csv
import json
from datetime import date, datetime
from pathlib import Path


REQUIRED_COLUMNS = [
    "order_id",
    "customer_id",
    "order_date",
    "amount",
    "status",
    "updated_at",
]

VALID_STATUSES = {
    "created",
    "paid",
    "shipped",
    "delivered",
    "cancelled",
}


def load_customer_ids(file_path):
    with open(file_path, "r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        return {
            row["customer_id"].strip()
            for row in reader
            if row.get("customer_id")
        }


def validate_record(row, customer_ids):
    for column in REQUIRED_COLUMNS:
        if not row.get(column) or not row[column].strip():
            return f"missing_required_field: {column}"

    if row["customer_id"].strip() not in customer_ids:
        return "unknown_customer_id"

    try:
        amount = float(row["amount"])
    except ValueError:
        return "invalid_amount_type"

    if amount <= 0:
        return "amount_must_be_positive"

    if row["status"].strip() not in VALID_STATUSES:
        return "invalid_status"

    try:
        order_date = date.fromisoformat(row["order_date"].strip())
    except ValueError:
        return "invalid_order_date"

    if order_date > date.today():
        return "future_order_date"

    try:
        datetime.fromisoformat(row["updated_at"].strip())
    except ValueError:
        return "invalid_updated_at"

    return None


def validate_dataset(input_folder, output_folder):
    input_folder = Path(input_folder)
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    customer_ids = load_customer_ids(input_folder / "customers.csv")

    valid_records = []
    rejected_records = []
    duplicate_records = []

    order_files = sorted(input_folder.glob("orders_*.csv"))

    for file_path in order_files:
        with open(file_path, "r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)

            missing_columns = set(REQUIRED_COLUMNS) - set(reader.fieldnames or [])

            if missing_columns:
                raise ValueError(
                    f"{file_path.name} is missing columns: {missing_columns}"
                )

            extra_columns = set(reader.fieldnames or []) - set(REQUIRED_COLUMNS)

            if extra_columns:
                print(
                    f"Schema warning in {file_path.name}: "
                    f"extra columns {extra_columns}"
                )

            file_orders = {}

            for row_number, row in enumerate(reader, start=2):
                if None in row:
                    reason = "malformed_row"
                else:
                    reason = validate_record(row, customer_ids)

                if reason:
                    rejected_records.append({
                        "raw_record": json.dumps(row),
                        "reject_reason": reason,
                        "source_file": file_path.name,
                        "row_number": row_number,
                    })
                    continue

                row["amount"] = float(row["amount"])
                row["source_file"] = file_path.name
                row["row_number"] = row_number

                order_id = row["order_id"]
                updated_at = datetime.fromisoformat(row["updated_at"])

                if order_id not in file_orders:
                    file_orders[order_id] = row
                    continue

                existing = file_orders[order_id]
                existing_time = datetime.fromisoformat(existing["updated_at"])

                if updated_at >= existing_time:
                    dropped = existing
                    file_orders[order_id] = row
                    kept = row
                else:
                    dropped = row
                    kept = existing

                duplicate_records.append({
                    "order_id": order_id,
                    "dropped_source_file": dropped["source_file"],
                    "dropped_row_number": dropped["row_number"],
                    "kept_source_file": kept["source_file"],
                    "kept_row_number": kept["row_number"],
                })

            valid_records.extend(file_orders.values())

    write_csv(
        output_folder / "rejects.csv",
        rejected_records,
        ["raw_record", "reject_reason", "source_file", "row_number"],
    )

    write_csv(
        output_folder / "duplicate_log.csv",
        duplicate_records,
        [
            "order_id",
            "dropped_source_file",
            "dropped_row_number",
            "kept_source_file",
            "kept_row_number",
        ],
    )

    return valid_records, rejected_records, duplicate_records


def write_csv(file_path, records, columns):
    with open(file_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/sample")
    parser.add_argument("--output", default="output")

    args = parser.parse_args()

    valid, rejected, duplicates = validate_dataset(
        args.input,
        args.output,
    )

    print("\nValidation completed.")
    print(f"Valid orders: {len(valid)}")
    print(f"Rejected records: {len(rejected)}")
    print(f"Dropped duplicate records: {len(duplicates)}")
    print(f"Results saved in: {args.output}")
