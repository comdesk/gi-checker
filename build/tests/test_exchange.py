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
    ADVICE, CARB_BAND, apply_exchange, dead_keys, load_exchange,
    load_fiber_rich, unused_keys)
from gi_match import apply_gi   # noqa: E402
from group import apply_groups  # noqa: E402
from normalize import apply_nutrient_fixes, fill_missing, load_records  # noqa: E402
from score import judge  # noqa: E402

EXCHANGE = BUILD / "data" / "exchange.csv"
FIBER_RICH = BUILD / "data" / "fiber_rich.csv"


@pytest.fixture(scope="module")
def table():
    return load_exchange(EXCHANGE)


@pytest.fixture(scope="module")
def records():
    """bundle.build() 와 같은 순서로 돌린다.

    빈 칸 메우기를 빼먹으면 r.inherited 가 비어 있어서, 식이섬유 표를
    추정치에 붙이지 않는다는 규칙이 테스트에서 아예 안 걸린다.
    """
    recs, _ = load_records(BUILD / "raw", BUILD / "data" / "category_allow.csv")
    apply_groups(recs, BUILD / "data" / "food_group.csv")
    apply_nutrient_fixes(recs, BUILD / "data" / "nutrient_fix.csv")
    fill_missing(recs)
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


def test_한_줄_조언은_곡류군만_없다(table):
    """곡류군은 열량별 식단안마다 5~11 단위로 달라 하루 횟수를 말할 수 없고,
    채소처럼 '충분히 드시라'고 할 수 있는 군도 아니다."""
    for key, entry in table.items():
        has_advice = "advice" in entry
        assert has_advice == (entry["foodGroup"] != "곡류군"), key


CARB_ADVICE = "탄수화물이 있는 편이라 과하지 않게"
SODIUM_ADVICE = "나트륨이 많은 편이라 양은 조절하세요"


def test_채소_조언은_세_가지로_갈린다(table):
    """4판이 세 가지를 갈라 말한다 — 대부분은 충분히, 탄수화물 5g 이상은
    과잉섭취 주의, 나트륨 100mg 이상은 나트륨 제한 시 고려."""
    veg = {k: v for k, v in table.items() if v["foodGroup"] == "채소군"}
    assert {v["advice"] for v in veg.values()} == {
        ADVICE["채소군"], CARB_ADVICE, SODIUM_ADVICE}

    for key in ("연근", "우엉", "더덕 뿌리", "도라지 뿌리", "호박 단호박", "마늘종"):
        assert veg[key]["advice"] == CARB_ADVICE, key
    for key in ("상추", "오이", "배추", "시금치"):
        assert veg[key]["advice"] == ADVICE["채소군"], key
    # 김치·장아찌·미역에 '충분히 드셔도 좋습니다' 를 붙이면 안 된다.
    # 당뇨와 고혈압은 같이 오는 일이 많고, 그때는 정반대 말이 된다.
    for key in ("배추김치", "깍두기", "동치미", "단무지", "미역류 전체"):
        assert veg[key]["advice"] == SODIUM_ADVICE, key


def test_한_건도_못_붙은_키가_없다(records):
    """두 가지를 다 본다 — 이름이 안 맞아 매칭조차 안 되는 키와, 매칭은
    되는데 안전장치가 전부 걸러낸 키. 뒤엣것은 조용히 사라져서, 처음에
    '무순' 이 부위 안전장치에 걸린 것을 한동안 못 찾았다."""
    assert unused_keys(records, EXCHANGE) == []
    assert dead_keys(records, EXCHANGE) == {"이름이 안 맞음": [], "전부 걸러짐": []}


# ── 실제로 붙은 값 ──

# 과일군은 2023 제4판, 나머지는 2010 제3판 기준이다.
@pytest.mark.parametrize("name,grams", [
    ("사과_생것", 100),              # 4판: 사과(부사·아오리) 100g (3판 80g)
    ("감_단감+부유_생것", 80),         # 4판: 단감 80g (3판 50g)
    ("감_연시+월하시_생것", 80),        # 4판: 연시 80g
    ("수박_적육질_생것", 150),         # 4판: 수박 150g
    ("바나나_생것", 80),             # 4판: 바나나 80g (3판 50g)
    ("배_생것", 100),               # 4판: 배 100g (3판 110g)
    ("앵두_생것", 80),              # 4판: 앵두 80g (3판 150g) — 절반으로 줄었다
    ("참외_씨 제거_생것", 100),        # 4판: 참외 100g (3판 150g)
    ("포도_말린것", 15),             # 4판: 건과일 15g — 생포도(80g)의 1/5
    ("바나나_말린것", 15),            # 4판: 건과일 15g (3판은 바나나만 10g)
    ("포도즙_천연과즙", 100),          # 4판: 주스류 100g (3판 포도주스 80g)
    ("멥쌀밥_백미", 70),             # 3판 Table 4: 밥 70g (1/3공기)
    ("식빵", 35),                  # 3판 Table 4: 빵류 35g (1쪽)
    ("우유", 200),                 # 3판 Table 8: 우유 200mL
    ("마늘_구근_생것", 15),           # 4판: 마늘 15g (3판 7g)
    ("상추_완전결구상추(양상추)_청상추_생것", 70),   # 4판: 채소류 70g
    ("배추김치", 50),                # 4판: 김치류 50g
    ("동치미", 70),                  # 4판: 나박김치·동치미만 70g
    ("단무지", 20),                  # 4판에서 새로 들어온 피클·장아찌류 20g
])
def test_알려진_분량이_맞다(records, name, grams):
    assert find(records, name).exchange["grams"] == grams


@pytest.mark.parametrize("name,grams", [
    ("복숭아_천도_생것", 150),
    ("복숭아_백도_생것", 100),
    ("복숭아_황도_생것", 100),
    ("복숭아_천중도_생것", 100),
])
def test_복숭아는_품종마다_분량이_다르다(records, name, grams):
    """4판에서 백도·황도만 150g -> 100g 으로 내려가고 천도는 150g 그대로다.
    품종을 뭉뚱그리면 백도를 1.5배로 드시게 된다."""
    assert find(records, name).exchange["grams"] == grams


# 목측량은 그 분량일 때의 개수다. 분량이 바뀌면 개수도 반드시 바뀌어야 한다.
# 4판으로 올리면서 '바나나 80g (중 1/2개)' 를 낼 뻔했다 — 중 1/2개는 50g 일
# 때의 개수다. 여기에 (분량, 목측량) 을 못 박아두면 g 만 고치고 개수를
# 안 고쳤을 때 걸린다. 새 목측량을 추가할 때도 여기를 거쳐야 한다.
EYEBALL_GROUPS = {
    (70, "1/3공기"): ["멥쌀밥", "보리밥", "잡곡밥", "찹쌀밥", "흑미밥",
                     "귀리밥", "기장밥", "콩밥"],
    (140, "2/3공기"): ["쌀죽(흰죽)", "찹쌀죽"],
    (30, "3큰술"): ["멥쌀 백미 생것", "멥쌀 현미 생것", "멥쌀 칠분도미 생것",
                   "보리 생것", "찹쌀 생것", "메밀 생것", "밀 생것",
                   "귀리", "율무 생것", "기장", "조", "수수",
                   "팥 말리기", "녹두 말리기", "렌즈콩(렌틸콩) 말리기",
                   "병아리콩 말리기", "퀴노아 말리기"],
    (30, "5큰술"): ["밀 가루", "전분"],
    (70, "1/2컵"): ["완두"],
    (90, "1/2공기"): ["국수 삶기", "메밀 국수 삶기", "메밀 냉면 삶기",
                     "국수 칼국수 삶기", "국수 우동 삶기", "국수 중국국수 삶기",
                     "파스타 삶기"],
    (30, "지름 11.5cm"): ["멥쌀밥_누룽지"],
    (70, "중 1/2개"): ["고구마"],
    (140, "중 1개"): ["감자"],
    (50, "썰은것 11~12개"): ["가래떡"],
    (50, "2개"): ["송편", "모싯잎송편"],
    (50, "3개"): ["인절미"],
    (50, "1개"): ["절편"],
    (35, "1쪽"): ["식빵"],
    (200, "1/2모"): ["도토리묵"],
    (60, "대 3개"): ["밤"],
    (15, "소 1/2개"): ["곶감 말리기"],
    (150, "중 7개"): ["딸기 생것"],
    (150, "중 1쪽"): ["수박 생것"],
    (100, "대 1/2개"): ["오렌지 생것"],
    (40, "1/10개"): ["호박 단호박"],
    (2, "1장"): ["김류 전체 말리기"],
    (200, "1컵"): ["우유", "두유", "산양유"],
}
EYEBALL = {key: (grams, eyeball)
           for (grams, eyeball), keys in EYEBALL_GROUPS.items()
           for key in keys}


def test_목측량은_그_분량에_맞는_것만_남아_있다(table):
    for key, entry in table.items():
        if "eyeball" not in entry:
            continue
        assert key in EYEBALL, f"{key!r} 에 목측량이 새로 생겼다 — 분량과 맞는지 확인하라"
        grams, eyeball = EYEBALL[key]
        assert entry["grams"] == grams, (
            f"{key!r} 의 분량이 {grams}g 에서 {entry['grams']:g}g 으로 바뀌었다. "
            f"목측량 '{eyeball}' 도 다시 확인해야 한다")
        assert entry["eyeball"] == eyeball


def test_못_박아둔_목측량이_전부_실제로_쓰인다(table):
    """표에서 지운 키가 여기 남아 있으면 이 테스트가 의미를 잃는다."""
    for key in EYEBALL:
        assert key in table, f"{key!r} 가 exchange.csv 에 없다"
        assert "eyeball" in table[key], f"{key!r} 의 목측량이 표에서 사라졌다"


def test_액체는_mL_로_적는다(records):
    """'우유 200g' 이라고 쓰면 저울을 찾게 된다."""
    assert find(records, "우유").exchange["unit"] == "mL"
    # 고체는 단위를 싣지 않는다 — 화면 기본값이 g 다
    assert "unit" not in find(records, "사과_생것").exchange
    assert "unit" not in find(records, "분유").exchange


def test_가당우유는_교환표_식품이_아니다(records):
    """4판이 '가당우유는 당류가 높고 칼슘이 낮으므로 피하고 흰우유를 선택한다'
    고 한다. 딸기우유에 흰우유 분량을 붙이면 교환표 식품인 것처럼 읽힌다."""
    assert find(records, "우유").exchange["grams"] == 200
    assert find(records, "우유_딸기").exchange is None


def test_가당_요구르트에_그릭요거트_분량이_안_붙는다(records):
    """둘 다 '요구르트(액상)' 그룹에 있다. 그룹 키로 두면 가당 제품까지
    교환표 식품이 된다 — 그릭요거트만 식품명으로 지목했다."""
    assert find(records, "요구르트(액상)_그릭요거트").exchange["grams"] == 100
    assert find(records, "요구르트(액상)_딸기요거트").exchange is None


def test_말린_것과_생것의_분량이_다르다(records):
    """수분이 빠지면 같은 무게에 든 탄수화물이 몇 배가 된다."""
    fresh = find(records, "포도_거봉_생것").exchange["grams"]
    dried = find(records, "포도_말린것").exchange["grams"]
    assert dried < fresh / 3


def test_과일에는_하루_횟수가_붙는다(records):
    assert find(records, "사과_생것").exchange["advice"] == "하루 1~2번"


def test_곡류에는_하루_횟수를_말하지_않는다(records):
    """열량별 식단안마다 5~11 단위로 크게 달라 하나로 말할 수 없다."""
    assert "advice" not in find(records, "멥쌀밥_백미").exchange


def test_채소는_충분히_드시라는_말이_같이_나간다(records):
    """분량만 띄우면 있지도 않은 제한이 생긴다. 4판 고려사항이
    '대부분의 채소류는 충분히 섭취하도록' 이라고 한다."""
    lettuce = find(records, "상추_완전결구상추(양상추)_청상추_생것").exchange
    assert lettuce["advice"] == "채소는 충분히 드셔도 좋습니다"
    # 반면 지침이 따로 짚은 고당질 채소는 반대로 말한다
    assert find(records, "연근_생것").exchange["advice"] == "탄수화물이 있는 편이라 과하지 않게"


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
    """말린 옥수수(탄수화물 74.1g)에 생옥수수 70g 을 붙이면 51.9g —
    곡류 1교환단위(23g)의 2.3배다. 쪄서 말린 밥도 마찬가지다."""
    assert find(records, "옥수수_메옥수수_말린것").exchange is None
    assert find(records, "멥쌀밥_쪄서 말린것").exchange is None
    assert find(records, "도토리묵_분말화한것").exchange is None


def test_식품명_키가_그룹_키를_이긴다(records):
    """누룽지는 '멥쌀밥' 그룹에 있지만 밥이 아니다. 4판이 따로 30g 이라고
    적어둔 것을, 그룹 키(밥 70g)가 가로채면 두 배 넘게 드시게 된다."""
    nurungji = find(records, "멥쌀밥_누룽지").exchange
    assert nurungji["grams"] == 30
    assert find(records, "멥쌀밥_백미").exchange["grams"] == 70


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


def test_식이섬유_목록의_키가_전부_교환표에_있다():
    """오타나 이름이 바뀐 키가 있으면 조용히 아무 데도 안 붙는다.
    load_exchange 가 그때 죽도록 해뒀고, 여기서 그것을 확인한다."""
    for key in load_fiber_rich(FIBER_RICH):
        assert key in load_exchange(EXCHANGE), key


def test_식이섬유_목록이_세_군에_걸쳐_있다():
    """한 군만 옮기다 만 상태를 잡는다."""
    table = load_exchange(EXCHANGE)
    groups = {table[k]["foodGroup"] for k in load_fiber_rich(FIBER_RICH)}
    assert groups == {"과일군", "곡류군", "채소군"}


def test_통곡물이_흰것보다_식이섬유_표시를_받는다(records):
    """지침이 곡류군에서 '식이섬유가 높은 통곡물을 우선하여 선택한다'고 한다.
    이 표시의 쓸모가 바로 그 비교다."""
    assert find(records, "보리_겉보리_도정_생것").exchange["fiberRich"] is True
    assert "fiberRich" not in find(records, "멥쌀_백미_생것").exchange


def test_식이섬유_표시는_화면의_영양성분과_어긋나지_않는다(records):
    """표 바로 아래에 영양성분표가 나온다. 표에 '식이섬유 1.3g' 이라고
    적혀 있는데 위에서 '많은 편입니다' 라고 하면 앱을 못 믿게 된다.
    지침 목록에 있어도 그 레코드의 실측값이 못 미치면 붙이지 않는다."""
    for r in records:
        if not (r.exchange or {}).get("fiberRich"):
            continue
        assert r.nutrients.fiber is not None, r.name
        assert "fiber" not in r.inherited, f"{r.name}: 추정치로 표를 붙였다"
        per_unit = r.nutrients.fiber * r.exchange["grams"] / 100.0
        assert per_unit >= 2.5, f"{r.name}: 1교환단위 식이섬유 {per_unit:.1f}g"


def test_지침_목록에_있어도_실측이_못_미치면_보류한다(records):
    """지침은 다른 데이터베이스를 쓰고 품종도 하나로 정해 싣는다(사과는 부사).
    우리 품종별 값과 갈리는 것이 실제로 있다."""
    # 참외는 지침의 식이섬유 목록에 있지만 우리 값으로는 1교환단위 1.1g 이다
    chamoe = find(records, "참외_씨 제거_생것")
    assert chamoe.exchange["grams"] == 100
    assert "fiberRich" not in chamoe.exchange


def test_실린_교환단위의_모양이_일정하다(records):
    """화면이 읽는 필드다. 없는 키를 읽으면 조용히 undefined 가 되어
    '한 번에 undefined g' 같은 것이 나간다."""
    allowed = {"grams", "foodGroup", "eyeball", "advice", "unit", "fiberRich"}
    for r in records:
        if not r.exchange:
            continue
        assert set(r.exchange) <= allowed, (r.name, set(r.exchange) - allowed)
        assert isinstance(r.exchange["grams"], float)
        assert r.exchange["foodGroup"] in CARB_BAND
