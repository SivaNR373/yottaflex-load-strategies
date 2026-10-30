
import argparse
import csv
import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path


STATUSES = ["created", "paid", "shipped", "delivered", "cancelled"]
START_DATE = date(2026, 10, 25)
NUMBER_OF_DAYS = 5


def make_customers(number):
    customers = []

    for i in range(1, number + 1):
        customers.append({
            "customer_id": f"CUST-{i:04d}",
            "customer_name": f"Customer {i}",
            "country": random.choice(["IN", "US", "UK", "DE"]),
            "created_at": "2026-01-01T10:00:00"
        })

    return customers


def make_order(order_number, customer_count, order_day):
    customer_number = random.randint(1, customer_count)
    order_time = datetime.combine(order_day, datetime.min.time())

    return {
        "order_id": f"ORD-{order_number:06d}",
        "customer_id": f"CUST-{customer_number:04d}",
        "order_date": order_day.isoformat(),
        "amount": f"{random.uniform(10, 1000):.2f}",
        "status": "created",
        "updated_at": (order_time + timedelta(hours=10)).isoformat()
    }


def write_csv(file_path, rows, columns):
    with open(file_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def generate_data(size, output_folder, seed):
    random.seed(seed)

    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    expected_folder = Path("data/expected")
    expected_folder.mkdir(parents=True, exist_ok=True)

    if size == "small":
        order_count = 200
        customer_count = 30
    else:
        order_count = 100000
        customer_count = 1000

    customers = make_customers(customer_count)

    customer_columns = [
        "customer_id", "customer_name", "country", "created_at"
    ]

    write_csv(
        output_folder / "customers.csv",
        customers,
        customer_columns
    )

    order_columns = [
        "order_id", "customer_id", "order_date",
        "amount", "status", "updated_at"
    ]

    daily_rows = [[] for _ in range(NUMBER_OF_DAYS)]
    valid_events = []
    final_orders = {}

    # Generate the required valid orders.
    for i in range(1, order_count + 1):
        day_number = (i - 1) % 4
        order_day = START_DATE + timedelta(days=day_number)

        order = make_order(i, customer_count, order_day)

        daily_rows[day_number].append(order)
        valid_events.append(order.copy())
        final_orders[order["order_id"]] = order.copy()

    # Add status updates for some existing orders.
    update_count = min(20, order_count)

    for i in range(1, update_count + 1):
        order_id = f"ORD-{i:06d}"
        updated_order = final_orders[order_id].copy()

        updated_order["status"] = "paid"
        updated_order["updated_at"] = (
            datetime.fromisoformat(updated_order["updated_at"])
            + timedelta(days=2)
        ).isoformat()

        daily_rows[2].append(updated_order)
        valid_events.append(updated_order.copy())
        final_orders[order_id] = updated_order.copy()

    # Add one late-arriving order with an earlier order date.
    late_order = make_order(
        order_count + 1,
        customer_count,
        START_DATE
    )
    daily_rows[3].append(late_order)
    valid_events.append(late_order.copy())
    final_orders[late_order["order_id"]] = late_order.copy()

    # Add one duplicate event in the same daily file.
    duplicate = final_orders["ORD-000001"].copy()
    daily_rows[0].append(duplicate.copy())
    valid_events.append(duplicate.copy())

    # Add deliberately invalid records.
    bad_records = [
        (
            {"order_id": "", "customer_id": "CUST-0001",
             "order_date": "2026-10-25", "amount": "50.00",
             "status": "created", "updated_at": "2026-10-25T10:00:00"},
            "missing_order_id"
        ),
        (
            {"order_id": "BAD-NULL", "customer_id": "CUST-0001",
             "order_date": "2026-10-25", "amount": "",
             "status": "created", "updated_at": "2026-10-25T10:00:00"},
            "missing_amount"
        ),
        (
            {"order_id": "BAD-TYPE", "customer_id": "CUST-0001",
             "order_date": "2026-10-25", "amount": "abc",
             "status": "created", "updated_at": "2026-10-25T10:00:00"},
            "invalid_amount_type"
        ),
        (
            {"order_id": "BAD-NEG", "customer_id": "CUST-0001",
             "order_date": "2026-10-25", "amount": "-50.00",
             "status": "created", "updated_at": "2026-10-25T10:00:00"},
            "negative_amount"
        ),
        (
            {"order_id": "BAD-STATUS", "customer_id": "CUST-0001",
             "order_date": "2026-10-25", "amount": "50.00",
             "status": "unknown", "updated_at": "2026-10-25T10:00:00"},
            "invalid_status"
        ),
        (
            {"order_id": "BAD-FK", "customer_id": "CUST-999999",
             "order_date": "2026-10-25", "amount": "50.00",
             "status": "created", "updated_at": "2026-10-25T10:00:00"},
            "orphan_customer"
        ),
        (
            {"order_id": "BAD-DATE", "customer_id": "CUST-0001",
             "order_date": "2099-01-01", "amount": "50.00",
             "status": "created", "updated_at": "2026-10-25T10:00:00"},
            "future_order_date"
        )
    ]

 

    daily_rows[0].extend([record for record, reason in bad_records])

    # Write the daily CSV files.
    for day_number in range(NUMBER_OF_DAYS):
        current_day = START_DATE + timedelta(days=day_number)
        file_name = f"orders_{current_day.isoformat()}.csv"
        file_path = output_folder / file_name

        if day_number == 4:
            # Empty file scenario: create only the CSV header.
            write_csv(file_path, [], order_columns)

        elif day_number == 3:
            # Extra column scenario: unexpected schema change.
            extra_columns = order_columns + ["coupon_code"]
            extra_rows = []

            for order in daily_rows[day_number]:
                row = order.copy()
                row["coupon_code"] = "SAVE10"
                extra_rows.append(row)

            write_csv(file_path, extra_rows, extra_columns)

        else:
            write_csv(file_path, daily_rows[day_number], order_columns)

    # Add a malformed CSV row with too many values.
    first_file = output_folder / f"orders_{START_DATE.isoformat()}.csv"

    with open(first_file, "a", encoding="utf-8") as file:
        file.write("BAD-MALFORMED,CUST-0001,2026-10-25,50,created,extra-value\n")

    # Write expected final orders.
    expected_columns = order_columns

    expected_orders = list(final_orders.values())
    expected_orders.sort(key=lambda row: row["order_id"])

    write_csv(
        expected_folder / "expected_final_orders.csv",
        expected_orders,
        expected_columns
    )

    # Write expected rejected records.
    expected_rejects = []

    for record, reason in bad_records:
        expected_rejects.append({
            "order_id": record["order_id"],
            "reject_reason": reason
        })

    expected_rejects.append({
        "order_id": "BAD-MALFORMED",
        "reject_reason": "malformed_csv_row"
    })

    write_csv(
        expected_folder / "expected_rejects.csv",
        expected_rejects,
        ["order_id", "reject_reason"]
    )

    # Write a simple summary.
    summary = {
        "size": size,
        "seed": seed,
        "valid_order_count": order_count + 1,
        "customer_count": customer_count,
        "status_update_count": update_count,
        "duplicate_event_count": 1,
        "expected_reject_count": len(expected_rejects),
        "empty_file_count": 1,
        "extra_column_file_count": 1,
        "malformed_row_count": 1
    }

    with open(expected_folder / "expected_summary.json", "w") as file:
        json.dump(summary, file, indent=4)

    print("Data generation completed.")
    print(f"Dataset size: {size}")
    print(f"Customers: {customer_count}")
    print(f"Valid orders: {order_count + 1}")
    print(f"Expected rejects: {len(expected_rejects)}")
    print(f"Output folder: {output_folder}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic customer and order data"
    )

    parser.add_argument(
        "--size",
        choices=["small", "large"],
        default="small"
    )

    parser.add_argument(
        "--output",
        default="data/raw"
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42
    )

    args = parser.parse_args()

    generate_data(args.size, args.output, args.seed)


if __name__ == "__main__":
    main()
