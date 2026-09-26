import pytest

from navigator_api.parcel_ids import normalize_county_id


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("0055A00137000000", "0055A00137000000"),
        ("0055-A-00137-0000-00", "0055A00137000000"),
        (" 0055-a-00137-0000-00 ", "0055A00137000000"),
        ("0055A-00137000000", "0055A00137000000"),
    ],
)
def test_normalizes_complete_county_ids(text: str, expected: str) -> None:
    assert normalize_county_id(text) == expected


@pytest.mark.parametrize("text", ["55-A-137", "0055-A-0013", "3525 Beechwood Blvd", ""])
def test_rejects_everything_else(text: str) -> None:
    assert normalize_county_id(text) is None
