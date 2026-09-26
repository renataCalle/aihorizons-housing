import pytest

from navigator_api.parcel_ids import normalize_county_id


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("0088-B-00044-0000-00", "0088-B-00044-0000-00"),
        ("0088B00044000000", "0088-B-00044-0000-00"),
        (" 0088-b-00044-0000-00 ", "0088-B-00044-0000-00"),
        ("0088B-00044000000", "0088-B-00044-0000-00"),
    ],
)
def test_normalizes_complete_county_ids(text: str, expected: str) -> None:
    assert normalize_county_id(text) == expected


@pytest.mark.parametrize("text", ["16-E-25", "0088-B-0004", "3525 Beechwood Blvd", ""])
def test_rejects_everything_else(text: str) -> None:
    assert normalize_county_id(text) is None
