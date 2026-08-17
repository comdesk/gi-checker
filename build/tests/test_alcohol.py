"""술 판정 검증.

술은 이 앱의 판정 체계가 다룰 수 있는 대상이 아니다. 규칙 1~4 는 전부
탄수화물이 혈당을 얼마나 올리는가를 재는데, 알코올은 탄수화물이 아니고
작용 방향도 반대다 — 간의 포도당 생성을 막아 혈당을 '떨어뜨린다'.

그래서 소주(소화탄수화물 0.08g)가 규칙 1로 초록이 되어 화면에
'좋음 / 탄수화물이 적어 혈당에 거의 영향 없어요' 가 떴었다. 밑에
저혈당 주의 문구가 붙어 있었지만 머리글이 그 문구를 정면으로 부정했다.

이제는 data/alcohol.csv 에 있는 것을 '주의' 로 고정한다. 대한당뇨병학회
진료지침이 '삼가는 것이 좋으나 마신다면 하루 1~2잔으로 제한' 이라
'피하기'(빨강)가 아니라 '주의'(노랑)다.
"""

import csv
import sys
from pathlib import Path

import pytest

BUILD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BUILD))

from normalize import load_records
from score import Nutrients, judge

ALCOHOL_CSV = BUILD / "data" / "alcohol.csv"
CAUTION_CSV = BUILD / "data" / "caution.csv"
MAX_ALCOHOL = 10


def _keys(path: Path) -> set[str]:
    rows = [ln for ln in path.read_text(encoding="utf-8-sig").splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]
    return {(r.get("key") or "").strip()
            for r in csv.DictReader(rows) if (r.get("key") or "").strip()}


# ── 표 자체 ────────────────────────────────────────────────

def test_표가_비어_있지_않다():
    assert _keys(ALCOHOL_CSV), "alcohol.csv 가 비어 있습니다"


def test_모든_줄에_근거가_있다():
    rows = [ln for ln in ALCOHOL_CSV.read_text(encoding="utf-8-sig").splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]
    for r in csv.DictReader(rows):
        key = (r.get("key") or "").strip()
        if not key:
            continue
        assert (r.get("note") or "").strip(), f"{key}: note 가 없습니다"


def test_술마다_주의문구도_있다():
    """두 표가 갈라지면 '주의로는 뜨는데 왜 위험한지는 안 알려주는' 술이 생긴다.

    등급은 alcohol.csv 가, 저혈당 설명은 caution.csv 가 담당한다. 한쪽에만
    적고 다른 쪽을 잊는 것이 이 구조의 유일한 실수 경로라 여기서 막는다.
    """
    missing = _keys(ALCOHOL_CSV) - _keys(CAUTION_CSV)
    assert not missing, f"caution.csv 에 주의 문구가 없는 술: {sorted(missing)}"


def test_남발되지_않는다():
    keys = _keys(ALCOHOL_CSV)
    assert len(keys) <= MAX_ALCOHOL, (
        f"alcohol.csv 가 {len(keys)}건입니다. 이 표는 '술이라서 판정 체계 밖' "
        f"이라는 예외 목록이지 일반적인 등급 조정 수단이 아닙니다")


# ── 판정 규칙(score.py) ────────────────────────────────────

def test_술은_탄수화물이_0이어도_주의다():
    """규칙 1(저탄수 → 초록)보다 앞선다. 소주가 정확히 이 경우다."""
    soju = Nutrients(kcal=127, carb=0.08, sugar=0.0, fiber=0.0, fat=0.0)
    assert judge(soju, gi=None).level == "green", "전제: 표시가 없으면 초록이었다"
    v = judge(soju, gi=None, is_alcohol=True)
    assert v.level == "amber"
    assert v.reason == "alcohol"


def test_술_표시는_GI가_낮아도_주의다():
    """GI 규칙(규칙 2)도 이긴다."""
    v = judge(Nutrients(kcal=63, carb=8.0, sugar=1.0, fiber=0.0, fat=0.0),
              gi=30, is_alcohol=True)
    assert v.level == "amber"
    assert v.reason == "alcohol"


def test_술_표시가_없으면_아무것도_안_바뀐다():
    """이 매개변수는 기본값으로 꺼져 있어야 한다 — 3,556건은 그대로여야 한다."""
    rice = Nutrients(kcal=130, carb=28.1, sugar=0.1, fiber=0.3, fat=0.3)
    assert judge(rice, gi=86) == judge(rice, gi=86, is_alcohol=False)


# ── 실제 번들 ──────────────────────────────────────────────

@pytest.fixture(scope="module")
def records():
    if not (BUILD / "raw" / "원재료성_농진청.csv").exists():
        pytest.skip("원본 CSV 가 없습니다")
    recs, _ = load_records(BUILD / "raw", BUILD / "data" / "category_allow.csv")
    return recs


def test_표의_모든_키가_실제로_붙는다(records):
    """이름이 안 맞아 아무 데도 안 붙으면 표가 조용히 무효가 된다."""
    flagged = {r.name for r in records if r.is_alcohol} | {
        r.rep_name for r in records if r.is_alcohol}
    for key in _keys(ALCOHOL_CSV):
        assert key in flagged, f"alcohol.csv 의 '{key}' 가 어느 레코드에도 안 붙었습니다"


def test_술이_아닌_것에는_안_붙는다(records):
    flagged = sorted(r.name for r in records if r.is_alcohol)
    assert len(flagged) <= MAX_ALCOHOL, f"술 표시가 너무 많습니다: {flagged}"
