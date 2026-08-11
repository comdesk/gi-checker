"""번들 산출물 검증. 원본 CSV 가 없으면 건너뛴다."""

import json
import sys
from pathlib import Path

import pytest

BUILD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BUILD))

from bundle import PACKAGE_GRAMS, PACKAGE_NAME_MARKERS, build, chosung_of, search_aliases, search_norm
from group import PART_PATTERN

LEVELS = {"green", "amber", "red"}
KINDS = {"measured", "estimated", "na", "none"}
REASONS = {"low-carb", "gi", "gi+sweet", "nutrient", "nutrient+sweet"}
CATEGORIES = {"채소", "과일", "밥·면·빵", "국·찌개", "고기·생선", "간식·음료", "기타"}


def test_초성_추출():
    assert chosung_of("고구마") == "ㄱㄱㅁ"
    assert chosung_of("된장찌개") == "ㄷㅈㅉㄱ"
    assert chosung_of(search_norm("고구마, 찐 것")) == "ㄱㄱㅁㅉㄱ"


def test_display_가_alias_에_반드시_들어간다():
    """group.py 가 채워주지 않아도 bundle.py 가 스스로 넣어야 한다."""
    out = search_aliases(name="고구마_찐것", display="찐 고구마", alias=[])
    assert "찐고구마" in out


def test_원본표기와_같은_별칭은_중복으로_넣지_않는다():
    out = search_aliases(name="사과", display="사과", alias=["사과"])
    assert out == []


def test_group_이_준_별칭도_보존된다():
    out = search_aliases(name="고구마_찐것", display="찐 고구마", alias=["찐고구마", "군고구마"])
    assert "군고구마" in out and "찐고구마" in out


@pytest.fixture(scope="module")
def bundle():
    if not (BUILD / "raw" / "원재료성_농진청.csv").exists():
        pytest.skip("원본 CSV 가 없습니다")
    data, _ = build(BUILD)
    return data


def test_스키마_값이_규약을_지킨다(bundle):
    for f in bundle["foods"]:
        assert f["verdict"]["level"] in LEVELS, f
        assert f["verdict"]["reason"] in REASONS, f
        assert f["gi"]["kind"] in KINDS, f
        assert f["category"] in CATEGORIES, f
        assert f["display"], f"{f['name']}: display 가 비었습니다"
        assert f["serving"]["label"], f["name"]


def test_na_와_none_은_GI_숫자가_없다(bundle):
    for f in bundle["foods"]:
        if f["gi"]["kind"] in ("na", "none"):
            assert f["gi"]["value"] is None, f["name"]
        else:
            assert f["gi"]["value"] is not None, f["name"]


def test_추정에만_근거가_붙는다(bundle):
    for f in bundle["foods"]:
        if f["gi"]["kind"] == "estimated":
            assert f["gi"]["basis"], f["name"]
        else:
            assert f["gi"]["basis"] is None, f["name"]


def test_low_carb_는_반드시_na_이고_초록이다(bundle):
    for f in bundle["foods"]:
        if f["verdict"]["reason"] == "low-carb":
            assert f["gi"]["kind"] == "na", f["name"]
            assert f["verdict"]["level"] == "green", f["name"]


def test_id_가_중복되지_않는다(bundle):
    ids = [f["id"] for f in bundle["foods"]]
    assert len(ids) == len(set(ids))


def test_그룹_구성원이_모두_실재하고_2개_이상이다(bundle):
    ids = {f["id"] for f in bundle["foods"]}
    for name, members in bundle["groups"].items():
        assert len(members) >= 2, name
        for fid in members:
            assert fid in ids, f"{name}: {fid} 없음"


def test_그룹이_GI_오름차순이다(bundle):
    by_id = {f["id"]: f for f in bundle["foods"]}
    for name, members in bundle["groups"].items():
        keys = [(by_id[i]["gi"]["value"] is None, by_id[i]["gi"]["value"] or 0)
                for i in members]
        assert keys == sorted(keys), name


def test_검색_인덱스가_채워진다(bundle):
    for f in bundle["foods"]:
        assert f["search"]["norm"], f["name"]
        assert f["search"]["chosung"], f["name"]
        assert search_norm(f["name"]) not in f["search"]["alias"]


def test_화면_이름으로도_검색된다(bundle):
    """display 가 원본 표기와 다르면 alias 에 들어가야 한다."""
    for f in bundle["foods"]:
        dn = search_norm(f["display"])
        if dn and dn != f["search"]["norm"]:
            assert dn in f["search"]["alias"], f"{f['display']} 로 검색 불가"


def test_손으로_쓴_주의문구는_남발되지_않는다(bundle):
    """caution.csv 로 손으로 붙인 것은 여전히 적어야 한다.

    나트륨 자동 생성 문구는 별도(test_나트륨_주의가_5퍼센트를_넘지_않는다)로 검증한다 —
    둘을 같은 상한으로 묶으면 나트륨 기능 자체가 성립할 수 없다.
    """
    hand = [f for f in bundle["foods"]
            if f["caution"] and not f["caution"].startswith("나트륨이 한 번에")]
    assert len(hand) <= 10, f"손으로 쓴 주의 문구 {len(hand)}건 — 너무 많습니다"


def test_나트륨_주의가_5퍼센트를_넘지_않는다(bundle):
    """경고가 흔해지면 아무도 안 읽는다 — 전체의 5% 를 넘으면 SODIUM_CAUTION_MG 를 올려야 한다."""
    total = len(bundle["foods"])
    salty = [f for f in bundle["foods"]
             if f["caution"] and f["caution"].startswith("나트륨이 한 번에")]
    assert len(salty) <= total * 0.05, f"나트륨 주의 {len(salty)}건 — 전체의 5% 초과"


def test_1회분량_환산이_100g_기준과_일관된다(bundle):
    for f in bundle["foods"]:
        g = f["serving"]["grams"]
        is_package = f["serving"]["isPackage"]
        ps = f["perServing"]
        if g is None or is_package:
            assert ps is None, f["name"]
            continue
        assert ps is not None, f["name"]
        expected = round(f["nutrients"]["carb"] * g / 100.0, 1)
        assert abs(ps["carb"] - expected) < 0.15, f"{f['name']}: {ps['carb']} vs {expected}"


def test_나트륨이_모든_레코드에_있다(bundle):
    """나트륨은 있으면 0 이상, 없으면 None(모름) 이어야 한다. 0 으로 채우면 안 된다."""
    for f in bundle["foods"]:
        assert "sodium" in f["nutrients"]
        s = f["nutrients"]["sodium"]
        assert s is None or s >= 0, f["name"]


def test_판정은_나트륨과_무관하다(bundle):
    """신호등은 혈당만 본다. 나트륨이 높다고 등급이 내려가면 안 된다."""
    salty = [f for f in bundle["foods"]
             if f["nutrients"]["sodium"] is not None and f["nutrients"]["sodium"] >= 600]
    assert any(f["verdict"]["level"] == "green" for f in salty), \
        "나트륨 높은 음식이 전부 초록이 아니게 됐다면 판정에 나트륨이 섞인 것"


def test_나트륨_주의가_실제로_붙는다(bundle):
    """상한만 보는 테스트는 기능이 통째로 사라져도 통과한다. 생성 자체를 검증한다."""
    salty = [f for f in bundle["foods"]
             if f["caution"] and "나트륨" in f["caution"]]
    assert len(salty) >= 50, f"나트륨 주의가 {len(salty)}건뿐입니다"
    # 실제로 짠 음식에 붙었는지도 확인
    for f in salty[:20]:
        ps = f["perServing"]
        assert ps and ps["sodium"] and ps["sodium"] >= 1000, f["display"]


def test_포장_전체는_1인분으로_취급하지_않는다(bundle):
    """이름에 포장 표시(간편조리세트 등)가 있고 무게도 큰 경우만 1회 분량 환산·
    나트륨 주의를 건너뛴다. 무게만으로는 밀키트와 큰 그릇을 못 가른다."""
    found_package = False
    for f in bundle["foods"]:
        if f["serving"]["isPackage"]:
            found_package = True
            g = f["serving"]["grams"]
            assert g and g >= PACKAGE_GRAMS, f["display"]
            assert f["perServing"] is None, f["display"]
            assert not (f["caution"] and "나트륨" in f["caution"]), f["display"]
    assert found_package, "포장으로 표시된 레코드가 하나도 없습니다 — 검증이 공허합니다"


def test_큰_그릇은_포장으로_오해하지_않는다(bundle):
    """해장국·국밥처럼 원래 1kg 넘는 1인분 요리는 제외 대상이 아니다."""
    found_big_bowl = False
    for f in bundle["foods"]:
        g = f["serving"]["grams"]
        if g and g >= PACKAGE_GRAMS and not any(m in f["name"] for m in PACKAGE_NAME_MARKERS):
            found_big_bowl = True
            assert f["serving"]["isPackage"] is False, f["display"]
            assert f["perServing"] is not None, f["display"]
        if f["serving"]["isPackage"]:
            assert any(m in f["name"] for m in PACKAGE_NAME_MARKERS), \
                f"{f['display']}: 이름에 포장 표시가 없는데 제외됨"
    assert found_big_bowl, "1kg 넘는 비-포장 레코드가 하나도 없습니다 — 검증이 공허합니다"


def test_아는_음식의_판정이_상식에_맞는다(bundle):
    by_display = {}
    for f in bundle["foods"]:
        by_display.setdefault(f["display"], f)

    def level_of(display):
        f = by_display.get(display)
        return f["verdict"]["level"] if f else None

    # 있으면 검사하고, 없으면 건너뛴다 (원본 갱신으로 이름이 바뀔 수 있다)
    for display, expected in (("콜라", "red"), ("사이다", "red"), ("두부", "green")):
        actual = level_of(display)
        if actual is not None:
            assert actual == expected, f"{display}: {actual} (기대 {expected})"


def _part_of(name: str) -> str | None:
    """group.py 의 부위 판정을 그대로 재사용해, 이름의 부위 표시를 뽑는다."""
    for seg in (p.strip() for p in name.split("_") if p.strip()):
        for marker, pattern in PART_PATTERN.items():
            if pattern.match(seg):
                return marker
    return None


def test_부위_표시가_다른_음식은_같은_그룹에_섞이지_않는다(bundle):
    """Task 11B Step 1: 고구마만이 아니라 전체 데이터에서, 부위 표시(줄기·잎·순·싹)가
    있는 이름과 없는 이름(또는 다른 부위 표시)이 같은 조리법 비교 그룹에 있으면 안 된다.

    group.py 가 부위를 그룹 이름에 붙이는 한 이 테스트는 구성상 항상 통과해야
    한다 — 그 보장 자체를 회귀 테스트로 고정한다.
    """
    by_id = {f["id"]: f for f in bundle["foods"]}
    offenders = []
    for gname, ids in bundle["groups"].items():
        parts = {_part_of(by_id[fid]["name"]) for fid in ids}
        if len(parts) > 1:
            offenders.append((gname, parts))
    assert offenders == [], f"부위가 섞인 그룹: {offenders[:10]}"


def test_찐_고구마_중복이_사라졌다(bundle):
    """Task 11B Step 2: '고구마_찐고구마'(음식.csv) 는 '고구마_찐것'(원재료성) 과
    같은 음식이라 지워야 한다. 사용자가 검색하면 한 번만 나와야 한다."""
    names = {f["name"] for f in bundle["foods"]}
    assert "고구마_찐것" in names
    assert "고구마_찐고구마" not in names

    displays = [f["display"] for f in bundle["foods"] if "고구마" in f["display"] and "찐" in f["display"]]
    assert displays.count("찐 고구마") == 1, displays


def test_출처_중복_정리는_품종_구분을_남긴다(bundle):
    """'분질(밤) 고구마'·'점질(호박) 고구마' 처럼 품종을 더하는 이름은
    중복 정리로 지우면 안 된다."""
    names = {f["name"] for f in bundle["foods"]}
    for keep in ("고구마_분질(밤) 고구마_찐것", "고구마_점질(호박) 고구마_찐것"):
        assert keep in names, f"{keep} 이 중복 정리로 지워졌다"


def test_100g_기준뿐이면_실제_분량이_없다(bundle):
    """serving.label 이 '기준' 으로 끝나기만 하고 grams 를 모르면(원재료성),
    화면에서 '보통 한 번에' 문구를 달면 안 된다 — render.js 가 이 값으로 판단한다."""
    for f in bundle["foods"]:
        if f["serving"]["label"].endswith("기준") and f["serving"]["grams"] is None:
            assert f["perServing"] is None, f["name"]
