from navigator_pipeline.publish import display_name


def test_display_name_keeps_ordinals_lowercase() -> None:
    assert display_name("4800 2ND AVE") == "4800 2nd Ave"
    assert display_name("44TH ST") == "44th St"
    assert display_name("1ST AVE") == "1st Ave"
    assert display_name("356 BIGELOW ST") == "356 Bigelow St"
    assert display_name("55-A-225") == "55-A-225"
