"""번들 산출물 검증. 원본 CSV 가 없으면 건너뛴다."""

import json
import sys
from pathlib import Path

import pytest

BUILD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BUILD))

from bundle import build, chosung_of, search_aliases, search_norm

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
        ps = f["perServing"]
        if g is None:
            assert ps is None, f["name"]
            continue
        assert ps is not None, f["name"]
        expected = round(f["nutrients"]["carb"] * g / 100.0, 1)
        assert abs(ps["carb"] - expected) < 0.15, f"{f['name']}: {ps['carb']} vs {expected}"


def test_나트륨이_모든_레코드에_있다(bundle):
    for f in bundle["foods"]:
        assert "sodium" in f["nutrients"]
        assert f["nutrients"]["sodium"] >= 0


def test_판정은_나트륨과_무관하다(bundle):
    """신호등은 혈당만 본다. 나트륨이 높다고 등급이 내려가면 안 된다."""
    salty = [f for f in bundle["foods"] if f["nutrients"]["sodium"] >= 600]
    assert any(f["verdict"]["level"] == "green" for f in salty), \
        "나트륨 높은 음식이 전부 초록이 아니게 됐다면 판정에 나트륨이 섞인 것"


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
