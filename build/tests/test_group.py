import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bundle import build
from group import PART_MARKERS, _find_method, _find_part, apply_groups
from normalize import load_records

BUILD = Path(__file__).resolve().parent.parent
RAW_DIR = BUILD / "raw"
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
def test_이름_충돌은_뒷단계가_다_풀어낸다():
    """같은 이름 두 줄이 화면에 나가면 사용자는 어느 쪽을 봐야 할지 모른다
    (리뷰에서 지적됐던 '말린 국수' 충돌).

    이 단계(apply_groups 직후)에서는 이름이 겹치는 것이 **정상**이다.
    화면 이름에서 시료 표기('대표 7월')·크기 표기('(25-29cm)')·영문 품종명을
    떼어내므로, 같은 음식을 달마다·크기별로 잰 레코드들이 여기서 같은 이름이
    된다. bundle.py 의 merge_variants 와 merge_same_name 이 최종 단계에서
    정리한다 — 답이 같으면 한 줄로 합치고, 갈리면 시료 표기를 되살린다.

    그래서 여기서는 '충돌이 있다/없다' 가 아니라 **뒷단계가 전부 풀어냈는지**를
    본다. 실제 보장은 test_bundle.py 의 test_이름이_겹치는_레코드가_없다 가 한다.
    이 테스트는 그 둘을 잇는 확인이다 — 앞단계 충돌이 늘어나는 것 자체는
    괜찮지만, 뒷단계를 통과해 화면까지 나가면 안 된다.
    """
    recs, _ = load_records(RAW_DIR, ALLOW_PATH)
    apply_groups(recs, MAP_PATH)

    by_display: dict[str, set] = {}
    for r in recs:
        if r.group:
            by_display.setdefault(r.display, set()).add(
                (r.nutrients.kcal, r.nutrients.carb, r.nutrients.fiber))
    colliding = {d for d, values in by_display.items() if len(values) > 1}
    assert colliding, "앞단계 충돌이 하나도 없다 — 이름 정리가 꺼진 것 아닌지 확인하라"

    shipped = build(BUILD)[0]
    leaked = [d for d in colliding
              if sum(1 for f in shipped["foods"] if f["display"] == d) > 1]
    assert leaked == [], f"앞단계 충돌이 화면까지 새어나갔다: {leaked[:5]}"


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


# ── 고기 부위 ──────────────────────────────────────────────
# 합치기 억제(_too_spread_to_merge)가 탄수화물만 보는데 고기는 탄수화물이
# 0에 가깝다. 그래서 지방이 몇 배 달라도 한 줄로 합쳐졌다 — 돼지고기 30부위가
# '생 돼지고기' 하나가 되고 대표로 뽑힌 갈비의 지방 17.1g 이 표시됐다.
# 삼겹살(35.7g)을 찾은 사람에게 절반을 보여준 셈이다.

def test_돼지_부위가_갈린다(records):
    by_group = {}
    for r in records:
        if r.rep_name == "돼지고기" and r.group:
            by_group.setdefault(r.group, []).append(r)
    for cut in ("삼겹살", "안심", "등심", "목심", "앞다리", "뒷다리"):
        assert f"돼지고기 {cut}" in by_group, sorted(by_group)


def test_삼겹살은_삼겹살_지방을_보여준다(records):
    """예전에는 '생 돼지고기'(갈비 17.1g) 안에 묻혀 있었다."""
    r = next(r for r in records if r.name == "돼지고기_삼겹살_생것")
    assert r.group == "돼지고기 삼겹살"
    assert r.display == "생 삼겹살", r.display
    assert r.nutrients.fat > 30


def test_괄호_안쪽_이름도_부위로_잡는다(records):
    """원본이 '앞다리(항정살)' 로 적는다. 바깥쪽만 보면 항정살(지방 24.5g)이
    앞다리(7.9g) 안에 묻힌다 — 둘 다 마커면 좁은 쪽으로 가야 한다.

    (레코드가 하나뿐이라 그룹은 단독그룹해제로 풀린다. 이름만 본다)"""
    r = next(r for r in records if r.name == "돼지고기_앞다리(항정살)_생것")
    assert r.display == "생 항정살", r.display


def test_같은_부위의_다른_이름은_안_갈린다(records):
    """'앞다리(앞다리살)' 은 앞다리를 되풀이한 것뿐이다. 갈라놓으면
    앞다리가 두 줄로 나온다."""
    r = next(r for r in records if r.name == "돼지고기_앞다리(앞다리살)_생것")
    assert r.group == "돼지고기 앞다리"


def test_등심덧살은_등심으로_뭉개지_않는다(records):
    """'등심(등심살)' 은 되풀이지만 '등심(등심덧살)' 은 지방이 세 배인 다른
    부위다. 괄호를 무조건 떼면 등심덧살이 등심으로 둔갑한다."""
    plain = next(r for r in records if r.name == "돼지고기_등심(등심살)_생것")
    extra = next(r for r in records if r.name == "돼지고기_등심(등심덧살)_생것")
    assert plain.display == "생 돼지 등심", plain.display
    assert "등심덧살" in extra.display, extra.display


def test_소_등급은_갈리지_않는다(records):
    """1++·1+ 등급 차이는 혈당과 무관한 잡음이다. 갈라놓으면 등심이
    등급 수만큼 줄이 늘어난다 — 등급별로 갈린 그룹이 있으면 안 된다."""
    groups = {r.group for r in records
              if r.rep_name == "소고기" and r.group and "등심" in r.group}
    assert groups <= {"소고기 등심", "소고기 꽃등심살", "소고기 살치살"}, groups
    assert "소고기 등심" in groups, groups
    assert not any("등급" in g for g in groups), groups


def test_난백과_난황은_다른_그룹이다(records):
    """Task 11B 에서 '함께 먹는 부위' 라며 뺐던 판단을 뒤집었다.
    원본은 난백(탄수 0.1g)과 난황(5.8g)을 따로 재어 놓았다."""
    groups = {r.group for r in records if r.rep_name == "달걀" and r.group}
    assert "달걀 난백" in groups and "달걀 난황" in groups, sorted(groups)


def test_분류명_앞머리를_이름에서_뗀다():
    """'파이/만주' 는 음식 이름이 아니라 식약처가 쓰는 서랍 이름이다.
    사과파이를 검색했는데 화면에 '파이/만주 사과파이' 라고 나오면
    정작 찾은 이름이 뒤에 붙어 있다.

    '~류' 를 떼는 것과 같은 이유다 (오징어류 오징어 -> 오징어).
    """
    from group import _readable
    assert _readable("파이/만주_사과파이") == "사과파이"
    assert _readable("비스킷/쿠키/크래커_꿀오란다") == "꿀오란다"
    assert _readable("밀크티/버블티_초코 버블티") == "초코 버블티"
    # 뒤에 아무것도 없으면 그것이 이름이다 — 떼면 이름이 사라진다
    assert _readable("리소토/리조또") == "리소토/리조또"
    # 괄호 안의 '/' 는 분류명이 아니라 다른 이름을 병기한 것이다
    assert _readable("완자전_소고기(동그랑땡/육원전)") == "완자전 소고기(동그랑땡/육원전)"


def test_종분리_마커와_화면이름을_따로_둘_수_있다():
    """마커는 원본 이름에서 찾을 조각이고, 화면 이름은 사람이 부르는 말이다.
    보통은 같지만('애호박', '단호박') 다를 때가 있다 —
    '복숭아_천도_생것' 의 조각은 '천도' 지만 사람은 '천도복숭아' 라고 한다.
    label 을 안 적으면 마커를 그대로 쓴다."""
    import csv, tempfile
    from pathlib import Path
    from group import load_species_split
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "species_split.csv"
        with p.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["rep_name", "marker", "note", "label"])
            w.writerow(["복숭아", "천도", "근거", "천도복숭아"])
            w.writerow(["호박", "애호박", "근거", ""])
        out = load_species_split(p)
    assert out["복숭아"]["천도"] == "천도복숭아"
    assert out["호박"]["애호박"] == "애호박"


def test_품종이_더하기로_붙어_있어도_찾는다():
    """원본은 '감_단감+부유_생것' 처럼 종 아래 품종을 '+' 로 붙여 적었다.
    조각 전체가 '단감+부유' 라서 마커 '단감' 과 정확히 일치하지 않는다.
    '+' 앞부분으로도 봐야 단감 네 품종이 다 걸린다."""
    from group import _find_species
    splits = {"감": {"단감": "단감", "연시": "연시"}}
    assert _find_species("감_단감+부유_생것", "감", splits) == "단감"
    assert _find_species("감_연시+청도반시_생것", "감", splits) == "연시"
    assert _find_species("감_단감_생것", "감", splits) == "단감"
    assert _find_species("감_대봉(갑주백목)_생것", "감", splits) is None
