"""신호등 판정. 순수 함수만 둔다 — 프로젝트 내 다른 모듈을 import 하지 않는다.

설계 문서 5절의 규칙을 그대로 옮긴 것이다. 규칙을 바꿀 일이 생기면
이 파일과 tests/test_score.py 만 고치면 된다.
"""

from dataclasses import dataclass

LEVELS = ("green", "amber", "red", "unknown")

# 원본에 값이 없는 칸이 많다 — 식이섬유 39.5%, 당류 18.0%.
# 이것을 0 으로 채우면 두 방향 모두로 답이 틀어진다.
#   식이섬유를 0 으로 → c 가 실제보다 커져 거짓 빨강 (콩(대두) 갈색콩)
#   당류를 0 으로   → 단 음식 보정이 영원히 안 걸려 거짓 초록 (당밀)
# 뒤쪽이 특히 위험하다. 당뇨 앱에서 설탕 덩어리를 '드셔도 좋아요' 라고 하는 것이다.
#
# 그래서 모르는 값은 0 으로 찍지 않고 '가능한 범위' 로 다룬다. 범위의 양 끝을
# 각각 판정해서 답이 같으면 확정하고, 갈리면 unknown 이다. 모르면 모른다고 한다.
#
# 열량으로 식이섬유를 역산하는 방법도 검토했으나 쓸 수 없었다. 값이 다 있는
# 1,908 행으로 확인한 결과, 식이섬유를 아예 무시한 4P+9F+4C(중앙 오차 4.9%)와
# 반영한 4P+9F+4(C-fib)+2fib(4.8%)의 정확도가 사실상 같다 — 이 데이터의 열량에는
# 식이섬유 정보가 실려 있지 않다.
MAX_FAT_PER_100G = 100.0

# 5.1의 F, S. 실제 데이터로 검증하며 조정한다 (Task 7).
DEFAULT_FAT_CUT = 10.0
DEFAULT_SUGAR_CUT = 10.0
DEFAULT_SUGAR_ABS = 18.0   # 지방과 무관하게 이 이상이면 단 음식으로 본다
# 15.0 은 출발점이었다. 실측 확인 결과 포도 일부 품종(생것, 당류 15.3~17.1g)이
# 15.0 컷에 걸려 초록에서 내려갔다 — 생과일은 절대 걸리면 안 된다는 원칙 위반.
# 문제 음식(카스텔라 23.3g 이상)과 생과일 최댓값(포도 17.1g) 사이 여유를 두고 18.0 으로 올렸다.

# ── 규칙 4의 기준값 (한 번에 먹는 양) ──
#
# GI 는 '얼마나 빨리 오르나'지 '얼마나 오르나'가 아니다. 같은 탄수화물 50g 을
# 먹었을 때의 상승 속도라서, 한 번에 얼마나 먹는지는 아예 안 들어 있다.
# 양까지 반영한 것이 혈당부하 GL = GI × 소화되는 탄수화물(g) ÷ 100 이다.
#
# 이 규칙이 없을 때 실제로 나온 답:
#   자장면    GI 46 → 초록.  한 그릇 600g 에 탄수화물 175g (쌀밥 세 공기)
#   아이스크림 GI 36 → 초록.  한 통 311g 에 당류 48g
#   망고스무디 GI 34 → 초록.  한 잔 591ml 에 당류 98g
# 아이스크림의 GI 가 낮은 이유가 바로 지방이 흡수를 늦춰서인데, 그것을
# '좋음' 으로 읽고 있었다.
GL_AMBER = 10.0   # 국제 기준: 1회 섭취 GL 10 이하가 낮음
GL_RED = 20.0     #            20 이상이 높음

# GI 자료가 없으면 GL 을 못 구한다. 그때는 한 번에 먹는 탄수화물 양으로 본다.
SERVING_CARB_AMBER = 15.0   # 탄수화물 1교환단위
SERVING_CARB_RED = 45.0     # 당뇨 식사요법에서 한 끼 탄수화물의 하한(45~60g)


@dataclass(frozen=True)
class Nutrients:
    """모두 1회 섭취량 기준, 단위 g (kcal 제외).

    열량·탄수화물은 없으면 판정 자체가 불가능하므로 적재 단계에서 걸러진다.
    나머지는 None 이 올 수 있고, 그것은 '0' 이 아니라 '모름' 이다.
    """
    kcal: float
    carb: float
    sugar: float | None
    fiber: float | None
    fat: float | None
    sodium: float | None = None   # 표시 전용. 판정에 쓰지 않는다


@dataclass(frozen=True)
class Verdict:
    level: str   # "green" | "amber" | "red" | "unknown"
    reason: str  # "low-carb" | "gi" | "gi+sweet" | "nutrient" | "nutrient+sweet" | "insufficient"


def _downgrade(level: str) -> str:
    """한 단계 내림. 빨강에서 더 내려갈 곳은 없다."""
    return {"green": "amber", "amber": "red", "red": "red"}[level]


def digestible_carb(n: Nutrients) -> float:
    """소화되는 탄수화물 c = 탄수화물 - 식이섬유. 음수는 0으로 자른다.

    식이섬유를 모르면 뺄 수 없으므로 탄수화물 전부로 본다 — 가장 나쁜 경우다.
    표시용이므로 이 값으로 판정하지 마라. 판정은 judge() 가 구간으로 한다.
    """
    return max(0.0, n.carb - (n.fiber or 0.0))


def judge(
    n: Nutrients,
    gi: float | None,
    *,
    fat_cut: float = DEFAULT_FAT_CUT,
    sugar_cut: float = DEFAULT_SUGAR_CUT,
    sugar_abs: float = DEFAULT_SUGAR_ABS,
    fiber_max: float | None = None,
    serving_grams: float | None = None,
) -> Verdict:
    """모르는 값이 있으면 가능한 범위의 양 끝을 판정해 답이 같을 때만 확정한다.

    serving_grams 는 한 번에 먹는 양이다. 알면 규칙 4(양)까지 본다. 원재료는
    한 번에 얼마를 먹는지 모르므로 None 이 오고, 그때는 100g 기준 판정만 한다.

    fiber_max 는 이 음식의 식이섬유가 최대 얼마까지일 수 있는지다. 모르면
    탄수화물 전부가 식이섬유일 수 있다고 보는데, 그러면 최선의 경우가 항상
    c=0(초록)이 되어 거의 다 unknown 이 된다. 그래서 호출부(bundle.py)가
    같은 카테고리에서 실제로 관찰된 식이섬유/탄수화물 비율의 상한을 넘겨준다.
    score.py 는 순수하게 유지해야 하므로 그 계산을 여기서 하지 않는다.
    """
    if n.sugar is not None and n.fiber is not None and n.fat is not None:
        return _judge(n.carb, n.sugar, n.fiber, n.fat, gi,
                      fat_cut=fat_cut, sugar_cut=sugar_cut, sugar_abs=sugar_abs,
                      serving_grams=serving_grams)

    # 식이섬유: 많을수록 좋다(c 가 작아진다).
    fib_lo = n.fiber if n.fiber is not None else 0.0
    fib_hi = n.fiber if n.fiber is not None else min(
        n.carb, n.carb if fiber_max is None else fiber_max)
    # 당류도 식이섬유도 탄수화물의 일부다. 당류를 아는데 식이섬유 상한을
    # 그대로 두면 '탄수화물 20g 중 당류 16.6g 인데 식이섬유가 15g' 이라는
    # 있을 수 없는 최선의 경우가 만들어져, 단 음료가 초록으로 뜨거나
    # 최악의 경우와 갈려 '알 수 없음' 이 된다.
    if n.sugar is not None:
        fib_hi = min(fib_hi, max(0.0, n.carb - n.sugar))
    # 당류: 적을수록 좋다. 모르면 소화되는 탄수화물 전부가 당일 수 있다.
    sug_lo = n.sugar if n.sugar is not None else 0.0
    sug_hi = n.sugar if n.sugar is not None else max(0.0, n.carb - fib_lo)
    # 지방: 단 음식 보정의 뒤 조건(지방이 GI 를 눌러놓은 경우)에만 쓰인다.
    fat_lo = n.fat if n.fat is not None else 0.0
    fat_hi = n.fat if n.fat is not None else MAX_FAT_PER_100G

    best = _judge(n.carb, sug_lo, fib_hi, fat_lo, gi,
                  fat_cut=fat_cut, sugar_cut=sugar_cut, sugar_abs=sugar_abs,
                  serving_grams=serving_grams)
    worst = _judge(n.carb, sug_hi, fib_lo, fat_hi, gi,
                   fat_cut=fat_cut, sugar_cut=sugar_cut, sugar_abs=sugar_abs,
                   serving_grams=serving_grams)
    if best.level == worst.level:
        # 등급이 같으면 확정한다. 이유는 나쁜 쪽 기준으로 말한다.
        return Verdict(best.level, worst.reason)
    return Verdict("unknown", "insufficient")


def _judge(
    carb: float,
    sugar: float,
    fiber: float,
    fat: float,
    gi: float | None,
    *,
    fat_cut: float,
    sugar_cut: float,
    sugar_abs: float,
    serving_grams: float | None = None,
) -> Verdict:
    """값이 전부 확정된 경우의 판정. 설계 문서 5절 그대로."""
    c = max(0.0, carb - fiber)

    # 규칙 1 — 탄수화물이 거의 없으면 GI 자체가 성립하지 않는다.
    # 이 규칙도 100g 기준이라 그릇 크기를 못 본다. 설렁탕은 한 그릇 500g 을
    # 먹어도 탄수화물이 2g 이지만, 국밥은 100g 당 5g 이어도 한 그릇 700g 이면
    # 35g 이다 — 그때까지 '혈당에 거의 영향 없어요' 라고 하면 틀린 말이다.
    if c <= 5.0:
        return _by_serving("green", "low-carb", c, gi, serving_grams)

    # 규칙 2 — GI 값이 있으면 그것이 판정의 주인공이다.
    if gi is not None:
        if gi <= 55:
            level = "green"
        elif gi <= 69:
            level = "amber"
        else:
            level = "red"

        # 단 음식 보정.
        #   앞 조건: 당분이 그냥 많은 경우. 지방 없는 초콜릿·건포도·카스텔라를 잡는다
        #   뒤 조건: 지방이 GI 를 눌러놓은 경우. 일반 초콜릿·아이스크림을 잡는다
        sweet = sugar >= sugar_abs or (fat >= fat_cut and sugar >= sugar_cut)
        if sweet:
            return _by_serving(_downgrade(level), "gi+sweet", c, gi, serving_grams)
        return _by_serving(level, "gi", c, gi, serving_grams)

    # 규칙 3 — GI가 없으면 소화되는 탄수화물로 대신 판정한다.
    if c <= 10.0:
        level = "green"
    elif c <= 25.0:
        level = "amber"
    else:
        level = "red"

    if carb > 0 and (sugar / carb) >= 0.5:
        return _by_serving(_downgrade(level), "nutrient+sweet", c, gi, serving_grams)
    return _by_serving(level, "nutrient", c, gi, serving_grams)


_ORDER = {"green": 0, "amber": 1, "red": 2}


def _by_serving(level: str, reason: str, c: float, gi: float | None,
                serving_grams: float | None) -> Verdict:
    """규칙 4 — 한 번에 먹는 양을 반영해 등급을 내린다.

    올리지는 않는다. 분량 자료가 틀렸을 때(여럿이 나눠 먹는 1,500g 한 상이
    1인분으로 적혀 있는 경우가 실제로 있다) 거짓 초록이 나오면 안 되기 때문이다.
    내리는 방향으로만 틀리게 해 둔다.
    """
    if not serving_grams:
        return Verdict(level, reason)

    serving_carb = c * serving_grams / 100.0
    if gi is not None:
        load = gi * serving_carb / 100.0            # 혈당부하(GL)
        by_amount = ("green" if load <= GL_AMBER
                     else "amber" if load < GL_RED else "red")
    else:
        by_amount = ("green" if serving_carb <= SERVING_CARB_AMBER
                     else "amber" if serving_carb <= SERVING_CARB_RED else "red")

    if _ORDER[by_amount] <= _ORDER[level]:
        return Verdict(level, reason)
    return Verdict(by_amount, "serving")
