"""보충 레코드 검증. 원본 CSV 가 없으면 건너뛴다."""

import csv
import sys
from pathlib import Path

import pytest

BUILD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BUILD))

from normalize import load_records

EXTRA = BUILD / "data" / "extra_foods.csv"
CATEGORIES = {"채소", "과일", "밥·면·빵", "국·찌개", "고기·생선", "간식·음료", "기타"}


def rows():
    if not EXTRA.exists():
        return []
    with EXTRA.open(encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.DictReader(f) if (r.get("name") or "").strip()]


def test_모든_보충_레코드에_출처가_있다():
    for r in rows():
        assert (r.get("source") or "").strip(), f"{r['name']}: source 없음"


def test_카테고리가_허용된_7종이다():
    for r in rows():
        assert r["category"].strip() in CATEGORIES, f"{r['name']}: {r['category']}"


def test_영양성분이_숫자이고_음수가_아니다():
    for r in rows():
        for key in ("kcal", "carb", "sugar", "fiber", "fat"):
            value = float(r[key])
            assert value >= 0, f"{r['name']}.{key} = {value}"


def test_당류가_탄수화물을_넘지_않는다():
    """당류는 탄수화물의 일부다. 넘으면 입력 오류다."""
    for r in rows():
        carb, sugar = float(r["carb"]), float(r["sugar"])
        assert sugar <= carb + 0.1, f"{r['name']}: 당류 {sugar} > 탄수화물 {carb}"


@pytest.fixture(scope="module")
def records():
    if not (BUILD / "raw" / "원재료성_농진청.csv").exists():
        pytest.skip("원본 CSV 가 없습니다")
    recs, _ = load_records(BUILD / "raw", BUILD / "data" / "category_allow.csv")
    return recs


def test_보충_레코드가_실제로_적재된다(records):
    names = {r.name for r in records}
    for r in rows():
        assert r["name"] in names, f"{r['name']} 이 적재되지 않았습니다"


def test_보충_레코드에_source_가_붙는다(records):
    extra_names = {r["name"] for r in rows()}
    for rec in records:
        if rec.name in extra_names:
            assert rec.source, f"{rec.name}: source 가 비어 있습니다"
        # 원본 CSV 에서 온 레코드는 source 가 없어야 한다
    origin = [r for r in records if r.name not in extra_names]
    assert all(r.source is None for r in origin[:200])
