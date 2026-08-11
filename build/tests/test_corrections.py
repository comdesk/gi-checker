"""원본 표기 오류 정정이 실제로 적용되는지 검증한다.

원본 CSV 가 없으면 건너뛴다.
"""

import sys
from collections import Counter
from pathlib import Path

import pytest

BUILD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BUILD))

from normalize import load_item_category_overrides, load_records


@pytest.fixture(scope="module")
def records():
    if not (BUILD / "raw" / "원재료성_농진청.csv").exists():
        pytest.skip("원본 CSV 가 없습니다")
    recs, _ = load_records(BUILD / "raw", BUILD / "data" / "category_allow.csv")
    return recs


def test_밥_오타가_정정된다(records):
    names = {r.name for r in records}
    assert "밥_옥광_구운것" not in names
    assert "밤_옥광_구운것" in names


def test_모든_그룹의_카테고리가_하나로_통일된다(records):
    """대표식품명 단위로 카테고리가 하나로 통일돼야 한다.

    단, 개별 식품명 override(category_override_item.csv)로 강제 지정된 항목은
    제외한다 — 들깨·꾸지뽕·구기자처럼 같은 대표식품명 안에 씨앗/열매와 잎이
    실제로 섞여 있어, 그 부분만 의도적으로 다른 카테고리를 갖기 때문이다.
    """
    item_override = load_item_category_overrides(BUILD / "data" / "category_override_item.csv")
    by_rep: dict[str, Counter] = {}
    for r in records:
        if r.name in item_override:
            continue
        by_rep.setdefault(r.rep_name, Counter())[r.category] += 1
    갈린그룹 = {rep: dict(c) for rep, c in by_rep.items() if len(c) > 1}
    assert 갈린그룹 == {}, f"카테고리가 갈린 그룹: {갈린그룹}"


def test_밥으로_검색해도_밤이_안_섞인다(records):
    """'밥' 은 주식, '밤' 은 견과다. 당뇨 관점에서 완전히 다르다."""
    rice_items = [r for r in records if r.name.startswith("밥_") or r.display == "밥"]
    for r in rice_items:
        assert "옥광" not in r.name


def test_잎_항목은_채소로_분류된다(records):
    """들깨·꾸지뽕·구기자는 씨앗/열매와 잎(순·싹)이 같은 대표식품명에 섞여 있다.
    잎/순/싹은 잎채소이므로 '채소' 여야 한다.

    '_잎' 만으로 전체를 걸면 '녹차_잎_말린것'처럼 차류(정당하게 간식·음료)까지
    걸려 오탐이 나므로, 실제로 이 문제가 있는 세 대표식품명으로 범위를 좁힌다.
    """
    LEAF_GROUPS = {"들깨", "꾸지뽕", "구기자"}
    leaf_tokens = ("_잎", "_순", "_싹")
    checked = 0
    for r in records:
        if r.rep_name not in LEAF_GROUPS:
            continue
        if any(tok in r.name for tok in leaf_tokens):
            assert r.category == "채소", f"{r.name} -> {r.category}"
            checked += 1
    assert checked == 9, f"들깨·꾸지뽕·구기자의 잎/순/싹 항목이 9건이어야 하는데 {checked}건 걸림"
