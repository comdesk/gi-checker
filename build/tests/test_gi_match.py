"""GI 매칭 검증. 원본 CSV 가 없으면 건너뛴다."""

import sys
from pathlib import Path

import pytest

BUILD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BUILD))

from gi_match import apply_gi, load_gi_map
from group import apply_groups
from normalize import load_records

GI_MAP = BUILD / "data" / "gi_map.csv"

# 이 음식들은 반드시 실측 GI 가 붙어야 한다. 당뇨 앱에서 가장 자주 검색될 것들이다.
#
# [리뷰 반영] 원래 "떡" 이었으나, needle 매칭이 "이름에 '떡'이 든 레코드 중
# 아무거나 하나"만 measured 면 통과하는 허술한 테스트였다 — 실제로는
# 찹쌀떡 5건만 실측이 붙고 가래떡·떡국·떡볶이·시루떡(멥쌀떡 계열)은 전부
# none 인데도 테스트는 통과했다. gi_map.csv 에 실측 근거(PDF 모찌 analog)가
# 있는 "찹쌀떡" 으로 좁혀 테스트가 실제로 커버하는 항목만 통과하게 한다.
MUST_HAVE = [
    "쌀밥", "현미밥", "보리밥", "식빵", "국수", "찹쌀떡",
    "감자", "고구마", "옥수수", "사과", "배", "바나나", "포도", "수박",
    "우유", "두유", "초콜릿", "아이스크림",
]


@pytest.fixture(scope="module")
def records():
    if not (BUILD / "raw" / "원재료성_농진청.csv").exists():
        pytest.skip("원본 CSV 가 없습니다")
    recs, _ = load_records(BUILD / "raw", BUILD / "data" / "category_allow.csv")
    apply_groups(recs, BUILD / "data" / "food_group.csv")
    apply_gi(recs, GI_MAP)
    return recs


def test_gi_map_이_비어있지_않다():
    table = load_gi_map(GI_MAP)
    assert len(table) >= 150, f"gi_map.csv 항목이 {len(table)}개뿐입니다"


def test_gi_값이_상식적인_범위에_있다():
    for key, gi in load_gi_map(GI_MAP).items():
        assert 0 < gi <= 150, f"{key}: GI {gi} 는 범위를 벗어납니다"


def test_자주_먹는_음식에_실측_GI_가_붙는다(records):
    missing = []
    for needle in MUST_HAVE:
        hits = [r for r in records if needle in (r.rep_name or "") or needle in r.name]
        if not hits:
            missing.append(f"{needle}(항목 자체 없음)")
        elif not any(r.gi_kind == "measured" for r in hits):
            missing.append(f"{needle}(GI 미매칭)")
    assert not missing, f"실측 GI 가 없는 필수 음식: {missing}"


def test_조리법에_따라_GI_가_갈린다(records):
    """고구마는 삶은 것과 구운 것의 GI 가 크게 다르다. 이게 이 앱의 핵심 기능이다."""
    boiled = [r for r in records if r.rep_name == "고구마" and r.method == "삶기"]
    roasted = [r for r in records if r.rep_name == "고구마" and r.method == "굽기"]
    if not boiled or not roasted:
        pytest.skip("고구마 삶기/굽기 항목이 없습니다")
    assert boiled[0].gi_value is not None and roasted[0].gi_value is not None
    assert roasted[0].gi_value > boiled[0].gi_value, "구운 고구마가 삶은 것보다 GI 가 높아야 합니다"


def test_추정_GI_에는_근거가_붙는다(records):
    for r in records:
        if r.gi_kind == "estimated":
            assert r.gi_basis, f"{r.name}: 추정인데 basis 가 없습니다"
        if r.gi_kind == "measured":
            assert r.gi_basis is None
        if r.gi_kind == "none":
            assert r.gi_value is None


def test_종을_나눈_그룹에_따로_GI_를_붙일_수_있다():
    """'감' 안에 단감(아삭)과 연시(물러야 먹는 것)가 함께 있다. 대표식품명
    키('감')로 붙이면 단감 값이 연시에까지 간다. 종을 나눴으면 그 그룹
    이름으로 각각 붙일 수 있어야 한다."""
    import tempfile, csv
    from pathlib import Path
    from gi_match import apply_gi

    class R:
        def __init__(self, name, rep, group, method):
            self.name, self.rep_name, self.group, self.method = name, rep, group, method
            self.gi_value, self.gi_kind, self.gi_basis = None, "none", None
            self.display = name

    recs = [R("감_단감_생것", "감", "감 단감", "생것"),
            R("감_연시_생것", "감", "감 연시", "생것")]
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "gi_map.csv"
        with p.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["key", "gi", "source", "note"])
            w.writerow(["감 단감", 42.9, "s", "n"])
            w.writerow(["감 연시", 61, "s", "n"])
        apply_gi(recs, p)
    assert [r.gi_value for r in recs] == [42.9, 61]
    assert [r.gi_kind for r in recs] == ["measured", "measured"]
