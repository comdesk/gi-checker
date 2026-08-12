import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from group import PART_MARKERS, _find_method, _find_part, apply_groups, sample_tag
from normalize import load_records

RAW_DIR = Path(__file__).resolve().parent.parent / "raw"
ALLOW_PATH = Path(__file__).resolve().parent.parent / "data" / "category_allow.csv"
MAP_PATH = Path(__file__).resolve().parent.parent / "data" / "food_group.csv"


@pytest.fixture(scope="module")
def records():
    if not RAW_DIR.exists():
        pytest.skip("원본 raw 데이터가 없음")
    recs, _ = load_records(RAW_DIR, ALLOW_PATH)
    apply_groups(recs, MAP_PATH)
    return recs


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

    # 시료 표기(수과원의 '대표 7월'·'부산 5월')를 화면 이름에서 떼면서, 같은
    # 음식을 달마다 잰 레코드들이 여기서는 같은 이름이 된다. 그것은 정상이고
    # bundle.py 의 merge_same_name 이 최종 단계에서 정리한다 — 답이 같으면
    # 한 줄로 합치고, 갈리면 시료 표기를 되살린다. 화면에 이름이 겹쳐 나가지
    # 않는다는 보장은 test_bundle.py 의 test_이름이_겹치는_레코드가_없다 가 한다.
    #
    # 여기서 잡아야 할 것은 '시료 차이로 설명되지 않는' 충돌뿐이다
    # (원래 이 테스트가 잡았던 '말린 국수' 처럼 서로 다른 음식이 같은 이름을
    #  갖는 경우).
    real = [c for c in conflicts
            if len({sample_tag(n) for n in c[2]}) < len(c[2])]
    assert real == [], f"시료 차이로 설명되지 않는 display 충돌 {len(real)}건: {real[:5]}"


# ── Task 11B Step 1: 부위 분리 ──

def test_뿌리와_잎은_같은_그룹이_아니다(records):
    """조리법 비교는 같은 부위끼리만 의미가 있다."""
    roots = [r for r in records if r.name.startswith("고구마_") and "줄기" not in r.name and "잎" not in r.name]
    leaves = [r for r in records if "고구마" in r.name and ("줄기" in r.name or "잎" in r.name)]
    root_groups = {r.group for r in roots if r.group}
    leaf_groups = {r.group for r in leaves if r.group}
    assert root_groups.isdisjoint(leaf_groups), \
        f"뿌리와 잎이 같은 그룹에 있다: {root_groups & leaf_groups}"


def test_부위표시가_있으면_그룹_이름에_부위가_붙는다(records):
    stem = next(r for r in records if r.name == "고구마_줄기_데친것")
    leaf = next(r for r in records if r.name == "고구마_잎_데친것")
    root = next(r for r in records if r.name == "고구마_찐것")
    assert stem.group == "고구마 줄기"
    assert leaf.group == "고구마 잎"
    assert root.group == "고구마"


def test_괄호_설명이_붙은_부위도_잡는다(records):
    """'줄기(껍질 포함)' 처럼 괄호 설명이 붙어도 '줄기'로 잡아야 한다."""
    r = next(r for r in records if r.name == "고구마_줄기(껍질 포함)_생것")
    assert r.group == "고구마 줄기"


def test_순대_순두부는_부위_분리에_안_걸린다(records):
    """'순' 은 짧아서 다른 단어에 걸리기 쉽다 — 순대·순두부는 부위 표시가 아니다."""
    names = ("순대", "순대국", "순대볶음", "김치순두부", "순두부찌개_해물", "초당순두부")
    by_name = {r.name: r for r in records}
    for n in names:
        r = by_name.get(n)
        if r is None:
            continue
        # rep_name 이 이미 '순대'/'순두부' 등이므로 그룹은 rep_name 그대로이거나
        # (단독 그룹 해제로) None 이어야 한다 — '<rep_name> 순' 으로 갈라지면 안 된다.
        if r.group:
            assert not r.group.endswith(" 순"), f"{n}: 오탐으로 부위가 붙었다 ({r.group})"


@pytest.mark.parametrize("name,expected", [
    ("고구마_줄기_생것", "줄기"),
    ("고구마_줄기(껍질 포함)_생것", "줄기"),
    ("고구마_잎_생것", "잎"),
    ("메밀_싹_생것", "싹"),
    ("죽순_순_생것", "순"),
    ("순대", None),
    ("순두부찌개_해물", None),
    ("초당순두부", None),
    ("잎새버섯_생것", None),      # 첫 세그먼트가 rep_name 이지 부위 표시가 아니다
    ("어린잎_생것", None),        # '어린잎' 은 '잎' 과 정확히 일치하지 않는다
    ("고구마_찐것", None),
])
def test_find_part_오탐_방지(name, expected):
    assert _find_part(name) == expected


def test_품종_구분은_살아남는다(records):
    names = {r.name for r in records}
    for keep in ("고구마_분질(밤) 고구마_찐것", "고구마_점질(호박) 고구마_찐것"):
        assert keep in names, f"{keep} 이 중복 정리로 지워졌다"


def test_중복이었던_찐고구마는_지워졌다(records):
    """'고구마_찐고구마'(음식.csv) 는 '고구마_찐것'(원재료성) 과 같은 음식이라 지운다."""
    names = {r.name for r in records}
    assert "고구마_찐것" in names
    assert "고구마_찐고구마" not in names


# ── 대표식품명 아래에 서로 다른 음식이 묶여 있던 문제 ────────────────

def test_애호박과_단호박은_다른_그룹이다(records):
    """조리법 비교가 '삶으면 좋고 찌면 주의'로 읽혔지만 실제로는
    쥬키니(삶기)와 단호박(찌기)을 비교하고 있었다."""
    by_group = {}
    for r in records:
        if r.rep_name == "호박" and r.group:
            by_group.setdefault(r.group, set()).add(r.name)
    for name, group in [("애호박", "호박 애호박"), ("단호박", "호박 단호박"),
                        ("쥬키니", "호박 쥬키니")]:
        assert group in by_group, f"{name} 이 따로 갈리지 않았다: {sorted(by_group)}"
        assert all(name in n for n in by_group[group]), by_group[group]


def test_백미와_현미는_다른_그룹이다(records):
    groups = {r.group for r in records if r.rep_name == "멥쌀" and r.group}
    assert "멥쌀 백미" in groups and "멥쌀 현미" in groups, sorted(groups)


def test_품종은_여전히_같은_그룹이다(records):
    """감자 대지·수미는 답이 같은 품종이므로 갈라서는 안 된다.
    종 분리가 품종까지 쪼개면 사용자가 고친 문제가 되살아난다."""
    steamed = {r.group for r in records
               if r.rep_name == "감자" and r.method == "찌기"}
    assert steamed == {"감자"}, steamed


def test_갈린_종은_사람이_부르는_이름으로_보인다(records):
    """그룹 키는 '호박 단호박' 이지만 화면에는 '찐 단호박' 이라고 나와야 한다."""
    steamed = [r for r in records if r.name == "호박_단호박_찐것"]
    assert steamed, "테스트 대상이 사라졌다"
    assert steamed[0].display == "찐 단호박", steamed[0].display


def test_부위는_홀로_서지_않는다(records):
    """'데친 잎' 은 무슨 잎인지 알 수 없다. '데친 호박 잎' 이어야 한다."""
    leaf = [r for r in records if r.name == "호박_잎_데친것"]
    assert leaf, "테스트 대상이 사라졌다"
    assert leaf[0].display == "데친 호박 잎", leaf[0].display


def test_난백과_난황은_다른_그룹이다(records):
    """Task 11B 에서 '함께 먹는 부위' 라며 뺐던 판단을 뒤집었다.
    원본은 난백(탄수 0.1g)과 난황(5.8g)을 따로 재어 놓았다."""
    groups = {r.group for r in records if r.rep_name == "달걀" and r.group}
    assert "달걀 난백" in groups and "달걀 난황" in groups, sorted(groups)
