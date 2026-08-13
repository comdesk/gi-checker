"""식품교환표 1교환단위량 검증.

이 값은 화면에 '한 번에 이만큼' 으로 나간다. 틀린 분량을 알려주는 것은
아무 분량도 안 알려주는 것보다 나쁘다 — 그래서 안전장치를 세 겹 두었고,
이 파일이 그 안전장치가 살아 있는지 지킨다.
"""

import sys
from pathlib import Path

import pytest

BUILD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BUILD))

from exchange import (   # noqa: E402
    CARB_BAND, DAILY, apply_exchange, load_exchange, unused_keys)
from gi_match import apply_gi   # noqa: E402
from group import apply_groups  # noqa: E402
from normalize import load_records  # noqa: E402
from score import judge  # noqa: E402

EXCHANGE = BUILD / "data" / "exchange.csv"


@pytest.fixture(scope="module")
def table():
    return load_exchange(EXCHANGE)


@pytest.fixture(scope="module")
def records():
    recs, _ = load_records(BUILD / "raw", BUILD / "data" / "category_allow.csv")
    apply_groups(recs, BUILD / "data" / "food_group.csv")
    apply_exchange(recs, EXCHANGE)
    return recs


def find(records, name):
    """원본 표기(name)로 찾는다. 화면 이름(display)은 bundle 의 합치기 단계에서
    다시 정해지므로 여기서는 아직 최종형이 아니다 — '멥쌀밥' 이 아니라
    '멥쌀밥_백미' 다."""
    for r in records:
        if r.name == name:
            return r
    raise AssertionError(f"레코드를 찾지 못했습니다: {name}")


# ── 자료 자체 ──

def test_표가_비어_있지_않다(table):
    assert len(table) >= 60


def test_모든_분량이_양수다(table):
    for key, entry in table.items():
        assert entry["grams"] > 0, key


def test_모든_줄에_식품군이_있다(table):
    for key, entry in table.items():
        assert entry["foodGroup"] in CARB_BAND, f"{key} 의 식품군 {entry['foodGroup']!r}"


def test_하루_횟수는_과일군과_우유군에만_붙는다(table):
    for key, entry in table.items():
        has_daily = "daily" in entry
        assert has_daily == (entry["foodGroup"] in DAILY), key


def test_안_쓰이는_키가_없다(records):
    """오타를 잡는다. 키가 데이터와 안 맞으면 조용히 아무 데도 안 붙는다 —
    표를 고칠 때 이 테스트가 없으면 고쳐놓고 안 붙은 줄 모른다."""
    assert unused_keys(records, EXCHANGE) == []


# ── 실제로 붙은 값 ──

@pytest.mark.parametrize("name,grams", [
    ("사과_생것", 80),               # Table 9: 사과 80g
    ("감_단감+부유_생것", 50),         # Table 9: 단감 50g — 연시(80g)와 다르다
    ("감_연시+월하시_생것", 80),        # Table 9: 연시·홍시 80g
    ("수박_적육질_생것", 150),         # Table 9: 수박 150g
    ("바나나_생것", 50),             # Table 9: 바나나 50g
    ("배_생것", 110),               # 학회 홈페이지: 배 110g (대 1/4개)
    ("포도_말린것", 15),             # Table 9: 건조과일 15g — 생포도(80g)의 1/5
    ("바나나_말린것", 10),            # Table 9: 건조과일 중 바나나만 10g
    ("멥쌀밥_백미", 70),             # Table 4: 밥 70g (1/3공기)
    ("식빵", 35),                  # Table 4: 빵류 35g (1쪽)
    ("우유", 200),                 # Table 8: 우유 200mL
    ("마늘_구근_생것", 7),            # Table 6: 마늘 7g
])
def test_알려진_분량이_맞다(records, name, grams):
    assert find(records, name).exchange["grams"] == grams


def test_액체는_mL_로_적는다(records):
    """'우유 200g' 이라고 쓰면 저울을 찾게 된다."""
    assert find(records, "우유").exchange["unit"] == "mL"
    # 고체는 단위를 싣지 않는다 — 화면 기본값이 g 다
    assert "unit" not in find(records, "사과_생것").exchange


def test_말린_것과_생것의_분량이_다르다(records):
    """수분이 빠지면 같은 무게에 든 탄수화물이 몇 배가 된다."""
    fresh = find(records, "포도_거봉_생것").exchange["grams"]
    dried = find(records, "포도_말린것").exchange["grams"]
    assert dried < fresh / 3


def test_과일에는_하루_횟수가_붙는다(records):
    assert find(records, "사과_생것").exchange["daily"] == "하루 1~2번"


def test_곡류에는_하루_횟수를_말하지_않는다(records):
    """열량별 식단안마다 5~11 단위로 크게 달라 하나로 말할 수 없다."""
    assert "daily" not in find(records, "멥쌀밥_백미").exchange


# ── 안전장치 ──

def test_안전장치1_부위가_다르면_안_붙는다(records):
    """고구마 줄기·잎은 고구마가 아니다. 탄수화물이 5g 대 31g 이다."""
    for r in records:
        if r.name.startswith("고구마_줄기") or r.name.startswith("고구마_잎"):
            assert r.exchange is None, r.name


def test_안전장치1_키가_그_부위를_가리키면_붙는다(records):
    """부위 자체가 음식인 경우까지 막으면 안 된다 — 깻잎(들깨 잎)은 잎을 먹는다."""
    assert find(records, "들깨_잎_생것").exchange["grams"] == 40
    assert find(records, "도라지_뿌리_생것").exchange["grams"] == 40
    # 반면 순은 뿌리가 아니다
    assert find(records, "도라지_순_생것").exchange is None


def test_안전장치2_교환단위_정의와_어긋나면_안_붙는다(records):
    """누룽지(탄수화물 86.8g)에 밥 70g 을 붙이면 60.8g — 1교환단위의 2.6배다."""
    assert find(records, "멥쌀밥_누룽지").exchange is None


def test_안전장치3_말린_것에_생것_분량이_안_붙는다(records):
    """말린 도라지 뿌리에 생 도라지의 40g 을 붙이면 당질이 30g 이 된다."""
    assert find(records, "도라지_뿌리_말린것").exchange is None
    assert find(records, "도라지_뿌리_분말화한것").exchange is None
    assert find(records, "도라지_뿌리_생것").exchange["grams"] == 40


def test_붙은_값은_모두_교환단위_정의를_지킨다(records):
    """표시된 분량 x 탄수화물이 그 식품군의 1교환단위 근처여야 한다.
    이것이 어긋나면 키를 잘못 붙였다는 뜻이다 — 표가 스스로를 검산한다."""
    for r in records:
        if not r.exchange:
            continue
        target, low, high = CARB_BAND[r.exchange["foodGroup"]]
        ratio = (r.nutrients.carb * r.exchange["grams"] / 100.0) / target
        assert low <= ratio <= high, (
            f"{r.name}: {r.exchange['grams']:g}g x 탄{r.nutrients.carb:g}g "
            f"= 기준의 {ratio:.1f}배")


# ── 판정에 영향을 주지 않는다 ──

def test_교환단위는_판정을_바꾸지_않는다():
    """1교환단위는 '한 번에 먹는 양' 이 아니라 '탄수화물이 12g 되는 양' 이다.
    이것을 규칙 4 에 넣으면 GI 80 인 과일도 GL 9.6 으로 전부 초록이 되어
    규칙 4 가 아무 일도 하지 않게 된다. 그래서 표시 전용으로만 쓴다."""
    recs, _ = load_records(BUILD / "raw", BUILD / "data" / "category_allow.csv")
    apply_groups(recs, BUILD / "data" / "food_group.csv")
    apply_gi(recs, BUILD / "data" / "gi_map.csv")

    before = [judge(r.nutrients, r.gi_value, serving_grams=r.serving_grams)
              for r in recs]
    apply_exchange(recs, EXCHANGE)
    after = [judge(r.nutrients, r.gi_value, serving_grams=r.serving_grams)
             for r in recs]
    assert before == after


def test_교환단위는_영양성분을_건드리지_않는다(records):
    for r in records:
        if r.exchange:
            assert r.nutrients.carb is not None
            # exchange 는 별도 필드다. serving_grams(원본 1회 분량)와 다른 값이다.
            assert r.exchange["grams"] != r.serving_grams or r.serving_grams is None
