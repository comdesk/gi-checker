"""표시용 주의 문구 검증. 원본 CSV 가 없으면 건너뛴다.

주의: caution 은 화면 표시 전용이다. 신호등 등급(score.py)에는 절대 관여하지 않는다.
"""

import csv
import sys
from pathlib import Path

import pytest

BUILD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BUILD))

from normalize import load_records

CAUTION = BUILD / "data" / "caution.csv"
ALCOHOL = {"소주", "맥주", "와인", "막걸리"}
MAX_CAUTIONED = 10


def rows():
    if not CAUTION.exists():
        return []
    with CAUTION.open(encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.DictReader(f) if (r.get("key") or "").strip()]


def test_모든_줄에_출처가_있다():
    for r in rows():
        assert (r.get("source") or "").strip(), f"{r['key']}: source 없음"


def test_모든_줄에_주의문구가_있다():
    for r in rows():
        assert (r.get("caution") or "").strip(), f"{r['key']}: caution 없음"


@pytest.fixture(scope="module")
def records():
    if not (BUILD / "raw" / "원재료성_농진청.csv").exists():
        pytest.skip("원본 CSV 가 없습니다")
    recs, _ = load_records(BUILD / "raw", BUILD / "data" / "category_allow.csv")
    return recs


def test_술_4종에_주의문구가_붙는다(records):
    by_name = {r.name: r for r in records}
    for name in ALCOHOL:
        assert name in by_name, f"{name} 이 적재되지 않았습니다"
        assert by_name[name].caution, f"{name}: caution 이 비어 있습니다"


def test_caution이_남발되지_않는다(records):
    """caution.csv 에 등록된 키가 많은 레코드에 광범위하게 걸리면 아무도 안 읽는다."""
    cautioned = [r for r in records if r.caution]
    assert len(cautioned) <= MAX_CAUTIONED, (
        f"caution 붙은 레코드가 {len(cautioned)}건 — {MAX_CAUTIONED}건을 넘습니다: "
        f"{[r.name for r in cautioned]}"
    )


def test_caution은_등급을_바꾸지_않는다(records):
    """caution 이 붙어도 gi_value/gi_kind 등 판정 입력값 자체는 그대로다."""
    by_name = {r.name: r for r in records}
    soju = by_name.get("소주")
    if soju is not None:
        assert soju.gi_value is None
        assert soju.gi_kind == "none"
