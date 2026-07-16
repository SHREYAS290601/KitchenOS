import pytest

from backend.app.pantry.quantity import (
    CAPACITY_BUCKETS,
    QuantityError,
    QuantityType,
    validate_quantity,
)


def test_capacity_bucket_accepts_only_allowed_values():
    for bucket in ("full", "3/4", "1/2", "1/4", "empty", "unknown"):
        validated = validate_quantity(QuantityType.capacity_bucket, bucket)
        assert validated.value == bucket
    assert CAPACITY_BUCKETS == ("full", "3/4", "1/2", "1/4", "empty", "unknown")


def test_capacity_bucket_rejects_arbitrary_fraction():
    with pytest.raises(QuantityError, match="2/3"):
        validate_quantity(QuantityType.capacity_bucket, "2/3")


def test_count_accepts_non_negative_int():
    assert validate_quantity(QuantityType.count, 3).value == 3
    assert validate_quantity(QuantityType.count, 0).value == 0
    with pytest.raises(QuantityError, match="-1"):
        validate_quantity(QuantityType.count, -1)


def test_count_rejects_bucket_value():
    with pytest.raises(QuantityError, match="count"):
        validate_quantity(QuantityType.count, "1/2")


def test_unknown_quantity_sets_needs_user_confirmation():
    validated = validate_quantity(QuantityType.unknown, None)
    assert validated.value is None
    assert validated.needs_user_confirmation is True


def test_unit_labels_for_counts():
    for label in ("piece", "pack", "box", "dozen"):
        validated = validate_quantity(QuantityType.count, 2, unit_label=label)
        assert validated.unit_label == label
    with pytest.raises(QuantityError, match="unit_label"):
        validate_quantity(QuantityType.count, 2, unit_label="hogshead")
