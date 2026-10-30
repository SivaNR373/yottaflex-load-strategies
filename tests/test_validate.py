
import csv
import pytest

from src.validate import validate_record, validate_dataset


CUSTOMER_IDS = {"CUST-0001"}

VALID_RECORD = {
    "order_id": "ORD-000001",
    "customer_id": "CUST-0001",
    "order_date": "2026-10-25",
    "amount": "100.00",
    "status": "created",
    "updated_at": "2026-10-25T10:00:00"
}


def test_valid_record():
    result = validate_record(VALID_RECORD.copy(), CUSTOMER_IDS)

    assert result is None


@pytest.mark.parametrize(
    "field, expected_reason",
    [
        ("order_id", "missing_required_field: order_id"),
        ("customer_id", "missing_required_field: customer_id"),
        ("order_date", "missing_required_field: order_date"),
        ("amount", "missing_required_field: amount"),
        ("status", "missing_required_field: status"),
        ("updated_at", "missing_required_field: updated_at"),
    ]
)
def test_missing_required_fields(field, expected_reason):
    record = VALID_RECORD.copy()
    record[field] = ""

    result = validate_record(record, CUSTOMER_IDS)

    assert result == expected_reason


def test_invalid_amount_type():
    record = VALID_RECORD.copy()
    record["amount"] = "abc"

    result = validate_record(record, CUSTOMER_IDS)

    assert result == "invalid_amount_type"


@pytest.mark.parametrize("amount", ["0", "-50"])
def test_non_positive_amount(amount):
    record = VALID_RECORD.copy()
    record["amount"] = amount

    result = validate_record(record, CUSTOMER_IDS)

    assert result == "amount_must_be_positive"


def test_invalid_status():
    record = VALID_RECORD.copy()
    record["status"] = "unknown"

    result = validate_record(record, CUSTOMER_IDS)

    assert result == "invalid_status"


def test_unknown_customer():
    record = VALID_RECORD.copy()
    record["customer_id"] = "CUST-999999"

    result = validate_record(record, CUSTOMER_IDS)

    assert result == "unknown_customer_id"


def test_invalid_order_date():
    record = VALID_RECORD.copy()
    record["order_date"] = "not-a-date"

    result = validate_record(record, CUSTOMER_IDS)

    assert result == "invalid_order_date"


def test_future_order_date():
    record = VALID_RECORD.copy()
    record["order_date"] = "2099-01-01"

    result = validate_record(record, CUSTOMER_IDS)

    assert result == "future_order_date"


def test_invalid_updated_at():
    record = VALID_RECORD.copy()
    record["updated_at"] = "not-a-timestamp"

    result = validate_record(record, CUSTOMER_IDS)

    assert result == "invalid_updated_at"


def write_test_csv(file_path, rows, columns):
    with open(file_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def test_malformed_csv_row(tmp_path):
    input_folder = tmp_path / "input"
    output_folder = tmp_path / "output"
    input_folder.mkdir()

    customer_columns = [
        "customer_id", "customer_name", "country", "created_at"
    ]

    customers = [{
        "customer_id": "CUST-0001",
        "customer_name": "Customer 1",
        "country": "IN",
        "created_at": "2026-01-01T10:00:00"
    }]

    write_test_csv(
        input_folder / "customers.csv",
        customers,
        customer_columns
    )

    order_columns = [
        "order_id", "customer_id", "order_date",
        "amount", "status", "updated_at"
    ]

    order_file = input_folder / "orders_2026-10-25.csv"

    with open(order_file, "w", encoding="utf-8") as file:
        file.write(
            "order_id,customer_id,order_date,amount,status,updated_at\n"
        )
        file.write(
            "BAD-ROW,CUST-0001,2026-10-25,50,created,"
            "2026-10-25T10:00:00,EXTRA\n"
        )

    valid, rejected, duplicates = validate_dataset(
        input_folder,
        output_folder
    )

    assert len(valid) == 0
    assert len(rejected) == 1
    assert rejected[0]["reject_reason"] == "malformed_row"


def test_duplicate_handling(tmp_path):
    input_folder = tmp_path / "input"
    output_folder = tmp_path / "output"
    input_folder.mkdir()

    customer_columns = [
        "customer_id", "customer_name", "country", "created_at"
    ]

    customers = [{
        "customer_id": "CUST-0001",
        "customer_name": "Customer 1",
        "country": "IN",
        "created_at": "2026-01-01T10:00:00"
    }]

    write_test_csv(
        input_folder / "customers.csv",
        customers,
        customer_columns
    )

    order_columns = [
        "order_id", "customer_id", "order_date",
        "amount", "status", "updated_at"
    ]

    first_order = VALID_RECORD.copy()

    second_order = VALID_RECORD.copy()
    second_order["status"] = "paid"
    second_order["updated_at"] = "2026-10-25T12:00:00"

    write_test_csv(
        input_folder / "orders_2026-10-25.csv",
        [first_order, second_order],
        order_columns
    )

    valid, rejected, duplicates = validate_dataset(
        input_folder,
        output_folder
    )

    assert len(valid) == 1
    assert len(rejected) == 0
    assert len(duplicates) == 1

    assert valid[0]["status"] == "paid"
    assert valid[0]["updated_at"] == "2026-10-25T12:00:00"
