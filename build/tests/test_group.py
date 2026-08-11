import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from group import _find_method, apply_groups
from normalize import load_records

RAW_DIR = Path(__file__).resolve().parent.parent / "raw"
ALLOW_PATH = Path(__file__).resolve().parent.parent / "data" / "category_allow.csv"
MAP_PATH = Path(__file__).resolve().parent.parent / "data" / "food_group.csv"


def test_compound_method_picks_last_process():
    """'A것을 B것' 표기는 목록 순서가 아니라 이름에서 가장 뒤에 오는 표기를 고른다.

    리뷰 Critical 1: 예전 코드는 METHOD_WORDS 리스트 순서상 먼저 나오는
    '말린것' 에 걸려 '삶은것'/'구운것' 같은 실제 최종 공정을 놓쳤다.
    """
    assert _find_method("국수_말린것을 삶은것") == "삶기"
    assert _find_method("취나물_미역취_삶아서 말린것을 삶은것") == "삶기"
    assert _find_method("가자미류_참가자미_육_반정도 말린것을 구운것_포항_3월") == "굽기"
    assert _find_method("새우류_새우_육_말린것을 볶은것_대표_평균") == "볶기"
    # 단순 표기는 그대로 하나만 잡혀야 한다.
    assert _find_method("고구마_찐것") == "찌기"
    assert _find_method("고구마_생것") == "생것"


def test_simple_display_requires_exact_method_token():
    """두 번째 조각이 조리법 표기를 '포함'만 해서는 simple 로 보면 안 된다.

    리뷰 Critical 2: '매실 절임_당류에 절인것' 을 '절인 매실 절임' 으로 뭉개면
    '당류에' 라는, 당뇨 앱에서 가장 중요한 수식어가 사라진다.
    """
    from normalize import FoodRecord
    from score import Nutrients

    n = Nutrients(kcal=100, carb=10, sugar=1, fiber=1, fat=0.1)
    records = [
        FoodRecord(id="a", name="매실 절임_당류에 절인것", display=None,
                   category="양념·소스", rep_name="매실 절임", serving_label="100g 기준", nutrients=n),
        FoodRecord(id="b", name="매실 절임_소금에 절인것", display=None,
                   category="양념·소스", rep_name="매실 절임", serving_label="100g 기준", nutrients=n),
        # 진짜 simple 케이스는 여전히 '조리법 재료' 형태로 나와야 한다.
        FoodRecord(id="c", name="고구마_찐것", display=None,
                   category="채소", rep_name="고구마", serving_label="100g 기준", nutrients=n),
    ]

    import tempfile
    with tempfile.TemporaryDirectory() as d:
        empty_map = Path(d) / "food_group.csv"
        empty_map.write_text("name,group,method\n", encoding="utf-8")
        apply_groups(records, empty_map)

    assert records[0].display == "매실 절임 당류에 절인것"
    assert records[1].display == "매실 절임 소금에 절인것"
    assert records[0].display != records[1].display
    assert records[2].display == "찐 고구마"


def test_solo_group_release_keeps_display():
    """단독그룹해제(group=None) 되어도 display 는 비어 있으면 안 된다."""
    from normalize import FoodRecord
    from score import Nutrients

    n = Nutrients(kcal=50, carb=5, sugar=1, fiber=1, fat=0.1)
    records = [
        FoodRecord(id="only", name="유일무이한재료_생것", display=None,
                   category="채소", rep_name="유일무이한재료", serving_label="100g 기준", nutrients=n),
    ]

    import tempfile
    with tempfile.TemporaryDirectory() as d:
        empty_map = Path(d) / "food_group.csv"
        empty_map.write_text("name,group,method\n", encoding="utf-8")
        apply_groups(records, empty_map)

    assert records[0].group is None
    assert records[0].display
    assert records[0].display == "생 유일무이한재료"


@pytest.mark.skipif(not RAW_DIR.exists(), reason="원본 raw 데이터가 없음")
def test_no_display_collision_within_group_on_real_data():
    """같은 그룹 안에서 영양성분이 다른 두 레코드가 같은 display 를 가지면 안 된다.

    사용자가 화면에서 서로 다른 두 식품을 같은 이름으로 보게 되는 것이
    가장 심각한 버그다 (리뷰에서 지적된 '말린 국수' 충돌).
    """
    recs, _ = load_records(RAW_DIR, ALLOW_PATH)
    apply_groups(recs, MAP_PATH)

    by_group_display: dict[tuple[str, str], list] = {}
    for r in recs:
        if r.group:
            by_group_display.setdefault((r.group, r.display), []).append(r)

    conflicts = []
    for (group, display), items in by_group_display.items():
        if len(items) < 2:
            continue
        nutrient_sets = {
            (i.nutrients.kcal, i.nutrients.carb, i.nutrients.sugar, i.nutrients.fiber, i.nutrients.fat)
            for i in items
        }
        if len(nutrient_sets) > 1:
            conflicts.append((group, display, [i.name for i in items]))

    assert conflicts == [], f"display 충돌 {len(conflicts)}건: {conflicts[:5]}"
