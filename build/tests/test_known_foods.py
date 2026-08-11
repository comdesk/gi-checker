"""정답표(known_foods.csv) 검증. 원본 CSV 가 없으면 건너뛴다.

Task 7 Step 3(컷 확정)의 회귀 도구. name_contains 로 화면 이름(display)에 그
문자열을 포함하는 레코드를 모두 찾고, 그중 하나라도 expected_level 과 같은
등급이면 통과시킨다. '전부 일치'가 아니라 '대표 사례가 존재하는가'를 본다 —
예를 들어 '두부' 는 저탄수 반찬부터 국물 요리까지 다양한 등급이 섞여 있어서,
전부 초록이길 요구하면 무관한 조합요리 때문에 항상 실패한다. 반대로 이 방식은
sugar_abs 컷을 조정할 때 건포도·초콜릿처럼 '반드시 걸려야 하는' 항목이 실제로
걸리는지, 사과·바나나처럼 '반드시 살아남아야 하는' 항목이 실제로 살아남는지를
정확히 잡아낸다.
"""

import csv
import re
import sys
from pathlib import Path

import pytest

BUILD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BUILD))

from bundle import build

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "known_foods.csv"


def rows():
    with FIXTURE.open(encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.DictReader(f) if (r.get("name_contains") or "").strip()]


@pytest.fixture(scope="module")
def foods():
    if not (BUILD / "raw" / "원재료성_농진청.csv").exists():
        pytest.skip("원본 CSV 가 없습니다")
    data, _ = build(BUILD)
    return data["foods"]


def matching(all_foods, term):
    return [f for f in all_foods if term in f["display"]]


@pytest.mark.parametrize("row", rows(), ids=lambda r: r["name_contains"])
def test_아는_음식이_기대한_등급으로_존재한다(foods, row):
    term, expected = row["name_contains"], row["expected_level"]
    found = matching(foods, term)
    assert found, f"'{term}' 을 포함하는 레코드가 없습니다 — 원본 갱신을 확인하세요"

    levels = {f["verdict"]["level"] for f in found}
    assert expected in levels, (
        f"'{term}': 기대 등급 {expected!r} 인 레코드가 하나도 없습니다 "
        f"(실제 등급: {sorted(levels)}) — {row.get('note', '')}"
    )


def test_생과일_생것이_전부_초록이다(foods):
    """생과일은 반드시 초록이어야 한다 — sugar_abs 컷이 너무 낮으면 여기서 잡힌다.

    원본 name 은 '용어_품종_조리법' 형태로 '_' 구분자를 쓴다('배_신고_생것').
    단순 substring 은 '멥쌀_배아미_생것'(배아미≠배) 같은 오탐을 낳으므로,
    여기서는 토큰 경계를 지켜 정확히 해당 재료만 골라낸다.
    """
    for term in ("사과", "배", "딸기", "수박", "바나나"):
        token = re.compile(rf"(?:^|_){re.escape(term)}(?:_|$)")
        raw = [f for f in foods if token.search(f["name"]) and "생것" in f["name"]]
        assert raw, f"{term}: '생것' 레코드를 찾지 못했습니다"
        offenders = [f["display"] for f in raw if f["verdict"]["level"] != "green"]
        assert not offenders, f"{term}: 생것인데 초록이 아닌 레코드 — {offenders}"
