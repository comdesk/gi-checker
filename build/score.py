"""신호등 판정. 순수 함수만 둔다 — 프로젝트 내 다른 모듈을 import 하지 않는다.

설계 문서 5절의 규칙을 그대로 옮긴 것이다. 규칙을 바꿀 일이 생기면
이 파일과 tests/test_score.py 만 고치면 된다.
"""

from dataclasses import dataclass

LEVELS = ("green", "amber", "red")

# 5.1의 F, S. 실제 데이터로 검증하며 조정한다 (Task 7).
DEFAULT_FAT_CUT = 10.0
DEFAULT_SUGAR_CUT = 10.0
DEFAULT_SUGAR_ABS = 18.0   # 지방과 무관하게 이 이상이면 단 음식으로 본다
# 15.0 은 출발점이었다. 실측 확인 결과 포도 일부 품종(생것, 당류 15.3~17.1g)이
# 15.0 컷에 걸려 초록에서 내려갔다 — 생과일은 절대 걸리면 안 된다는 원칙 위반.
# 문제 음식(카스텔라 23.3g 이상)과 생과일 최댓값(포도 17.1g) 사이 여유를 두고 18.0 으로 올렸다.


@dataclass(frozen=True)
class Nutrients:
    """모두 1회 섭취량 기준, 단위 g (kcal 제외)."""
    kcal: float
    carb: float
    sugar: float
    fiber: float
    fat: float
    sodium: float | None = None   # 표시 전용. 판정에 쓰지 않는다. 원본이 공란이면 None(모름) — 0과 다르다


@dataclass(frozen=True)
class Verdict:
    level: str   # "green" | "amber" | "red"
    reason: str  # "low-carb" | "gi" | "gi+sweet" | "nutrient" | "nutrient+sweet"


def _downgrade(level: str) -> str:
    """한 단계 내림. 빨강에서 더 내려갈 곳은 없다."""
    return {"green": "amber", "amber": "red", "red": "red"}[level]


def digestible_carb(n: Nutrients) -> float:
    """소화되는 탄수화물 c = 탄수화물 - 식이섬유. 음수는 0으로 자른다."""
    return max(0.0, n.carb - n.fiber)


def judge(
    n: Nutrients,
    gi: float | None,
    *,
    fat_cut: float = DEFAULT_FAT_CUT,
    sugar_cut: float = DEFAULT_SUGAR_CUT,
    sugar_abs: float = DEFAULT_SUGAR_ABS,
) -> Verdict:
    c = digestible_carb(n)

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
        sweet = n.sugar >= sugar_abs or (n.fat >= fat_cut and n.sugar >= sugar_cut)
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

    if n.carb > 0 and (n.sugar / n.carb) >= 0.5:
        return Verdict(_downgrade(level), "nutrient+sweet")
    return Verdict(level, "nutrient")
