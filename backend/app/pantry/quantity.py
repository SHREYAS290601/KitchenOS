from dataclasses import dataclass
from enum import StrEnum


class QuantityType(StrEnum):
    count = "count"
    capacity_bucket = "capacity_bucket"
    unknown = "unknown"


CAPACITY_BUCKETS: tuple[str, ...] = ("full", "3/4", "1/2", "1/4", "empty", "unknown")

COUNT_UNIT_LABELS: tuple[str, ...] = ("piece", "pack", "box", "dozen")


class QuantityError(ValueError):
    """Raised when a quantity value is invalid for its quantity type.

    Messages always name the offending value and list the allowed values,
    so the caller (and the user) knows how to fix the input.
    """


@dataclass(frozen=True)
class ValidatedQuantity:
    quantity_type: QuantityType
    value: str | int | None
    unit_label: str | None = None
    needs_user_confirmation: bool = False


def validate_quantity(
    quantity_type: QuantityType,
    value: str | int | None,
    *,
    unit_label: str | None = None,
) -> ValidatedQuantity:
    if quantity_type is QuantityType.unknown:
        if value is not None:
            raise QuantityError(
                f"quantity value {value!r} not allowed for quantity_type 'unknown' — "
                "send value null and let the user confirm"
            )
        return ValidatedQuantity(quantity_type, None, needs_user_confirmation=True)

    if quantity_type is QuantityType.capacity_bucket:
        if value not in CAPACITY_BUCKETS:
            raise QuantityError(
                f"quantity value {value!r} is not an allowed capacity bucket — "
                f"use one of {', '.join(CAPACITY_BUCKETS)}"
            )
        return ValidatedQuantity(quantity_type, value)

    # QuantityType.count
    if not isinstance(value, int) or isinstance(value, bool):
        raise QuantityError(
            f"quantity value {value!r} is invalid for a count item — "
            "counts take a non-negative integer, not a bucket value"
        )
    if value < 0:
        raise QuantityError(
            f"quantity value {value} is invalid for a count item — "
            "counts must be zero or greater"
        )
    if unit_label is not None and unit_label not in COUNT_UNIT_LABELS:
        raise QuantityError(
            f"unit_label {unit_label!r} is not allowed — "
            f"use one of {', '.join(COUNT_UNIT_LABELS)}"
        )
    return ValidatedQuantity(quantity_type, value, unit_label=unit_label)
