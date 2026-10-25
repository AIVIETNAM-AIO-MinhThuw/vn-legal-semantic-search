import random

from scripts.make_eval_queries import no_diacritic, telex, typo


def test_no_diacritic():
    assert no_diacritic("Đăng ký hộ kinh doanh") == "Dang ky ho kinh doanh"


def test_telex_example_from_spec():
    assert telex("học") == "hojc"


def test_typo_count_rule():
    rng = random.Random(1)
    short, kinds = typo("thuế toàn cầu", rng)
    assert len(kinds) == 1 and short != "thuế toàn cầu"
    _, kinds = typo("Doanh nghiệp nhỏ và vừa cần hồ sơ gì để vay vốn", random.Random(2))
    assert len(kinds) == 2
