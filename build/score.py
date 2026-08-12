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
) -> Verdict:
    """모르는 값이 있으면 가능한 범위의 양 끝을 판정해 답이 같을 때만 확정한다.

    fiber_max 는 이 음식의 식이섬유가 최대 얼마까지일 수 있는지다. 모르면
    탄수화물 전부가 식이섬유일 수 있다고 보는데, 그러면 최선의 경우가 항상
    c=0(초록)이 되어 거의 다 unknown 이 된다. 그래서 호출부(bundle.py)가
    같은 카테고리에서 실제로 관찰된 식이섬유/탄수화물 비율의 상한을 넘겨준다.
    score.py 는 순수하게 유지해야 하므로 그 계산을 여기서 하지 않는다.
    """
    if n.sugar is not None and n.fiber is not None and n.fat is not None:
        return _judge(n.carb, n.sugar, n.fiber, n.fat, gi,
                      fat_cut=fat_cut, sugar_cut=sugar_cut, sugar_abs=sugar_abs)

    # 식이섬유: 많을수록 좋다(c 가 작아진다).
    fib_lo = n.fiber if n.fiber is not None else 0.0
    fib_hi = n.fiber if n.fiber is not None else min(
        n.carb, n.carb if fiber_max is None else fiber_max)
    # 당류: 적을수록 좋다. 모르면 소화되는 탄수화물 전부가 당일 수 있다.
    sug_lo = n.sugar if n.sugar is not None else 0.0
    sug_hi = n.sugar if n.sugar is not None else max(0.0, n.carb - fib_lo)
    # 지방: 단 음식 보정의 뒤 조건(지방이 GI 를 눌러놓은 경우)에만 쓰인다.
    fat_lo = n.fat if n.fat is not None else 0.0
    fat_hi = n.fat if n.fat is not None else MAX_FAT_PER_100G

    best = _judge(n.carb, sug_lo, fib_hi, fat_lo, gi,
                  fat_cut=fat_cut, sugar_cut=sugar_cut, sugar_abs=sugar_abs)
    worst = _judge(n.carb, sug_hi, fib_lo, fat_hi, gi,
                   fat_cut=fat_cut, sugar_cut=sugar_cut, sugar_abs=sugar_abs)
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
) -> Verdict:
    """값이 전부 확정된 경우의 판정. 설계 문서 5절 그대로."""
    c = max(0.0, carb - fiber)

    # 규칙 1 — 탄수화물이 거의 없으면 GI 자체가 성립하지 않는다.
    if c <= 5.0:
        return Verdict("green", "low-carb")

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
            return Verdict(_downgrade(level), "gi+sweet")
        return Verdict(level, "gi")

    # 규칙 3 — GI가 없으면 소화되는 탄수화물로 대신 판정한다.
    if c <= 10.0:
        level = "green"
    elif c <= 25.0:
        level = "amber"
    else:
        level = "red"

    if carb > 0 and (sugar / carb) >= 0.5:
        return Verdict(_downgrade(level), "nutrient+sweet")
    return Verdict(level, "nutrient")
