import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from score import Nutrients, judge


def test_low_carb_is_green_regardless_of_gi():
    """탄수화물이 5g 이하면 GI가 무엇이든 초록. 규칙 1이 최우선."""
    spinach = Nutrients(kcal=16, carb=2.5, sugar=0.3, fiber=1.6, fat=0.3)
    v = judge(spinach, gi=None)
    assert v.level == "green"
    assert v.reason == "low-carb"


def test_low_carb_wins_over_high_gi():
    almond = Nutrients(kcal=180, carb=6.5, sugar=1.2, fiber=3.8, fat=15.0)
    v = judge(almond, gi=99)
    assert v.level == "green"
    assert v.reason == "low-carb"


def test_gi_thresholds():
    """GI 55/56/69/70 경계값."""
    n = Nutrients(kcal=200, carb=40, sugar=2, fiber=2, fat=0.5)
    assert judge(n, gi=55).level == "green"
    assert judge(n, gi=56).level == "amber"
    assert judge(n, gi=69).level == "amber"
    assert judge(n, gi=70).level == "red"


def test_sweet_correction_downgrades_chocolate():
    """지방과 당류가 둘 다 많으면 GI가 낮아도 한 단계 내림."""
    chocolate = Nutrients(kcal=270, carb=30, sugar=25, fiber=1.5, fat=15.0)
    v = judge(chocolate, gi=40)
    assert v.level == "amber"
    assert v.reason == "gi+sweet"


def test_sweet_correction_spares_apple():
    """지방·당류 동시조건(구 규칙) 단독으로는 지방 없는 과일을 건드리지 않는다.

    Task 7 에서 sugar_abs 절대조건이 추가되며 기본값으로는 sugar=15.6 이 새
    조건에 걸리게 됐다 — 이 테스트는 인자를 명시해 옛 fat+sugar 동시조건만
    떼어 검증한다. 기본값 아래 실제 생과일이 초록으로 남는지는
    test_생과일은_보정에_걸리지_않는다 가 실측치로 검증한다.
    """
    apple = Nutrients(kcal=82, carb=21.0, sugar=15.6, fiber=2.4, fat=0.2)
    v = judge(apple, gi=38, sugar_abs=20)
    assert v.level == "green"
    assert v.reason == "gi"


def test_sweet_correction_spares_nuts_via_low_carb():
    """지방은 많지만 당류가 적은 견과류는 애초에 규칙 1로 빠진다."""
    v = judge(Nutrients(kcal=180, carb=6.5, sugar=1.2, fiber=3.8, fat=15.0), gi=15)
    assert v.reason == "low-carb"


def test_red_cannot_be_downgraded_further():
    donut = Nutrients(kcal=400, carb=50, sugar=25, fiber=1, fat=20)
    v = judge(donut, gi=76)
    assert v.level == "red"
    assert v.reason == "gi+sweet"


def test_nutrient_fallback_when_no_gi():
    """GI가 없으면 소화되는 탄수화물로 판정."""
    n = Nutrients(kcal=100, carb=12.0, sugar=1.0, fiber=1.0, fat=0.5)
    v = judge(n, gi=None)          # c = 11.0
    assert v.level == "amber"
    assert v.reason == "nutrient"


def test_nutrient_fallback_thresholds():
    def c_of(c):
        return Nutrients(kcal=0, carb=c, sugar=0, fiber=0, fat=0)
    assert judge(c_of(10), gi=None).level == "green"
    assert judge(c_of(11), gi=None).level == "amber"
    assert judge(c_of(25), gi=None).level == "amber"
    assert judge(c_of(26), gi=None).level == "red"


def test_nutrient_sweet_correction():
    """당류가 탄수화물의 절반 이상이면 한 단계 내림."""
    dried = Nutrients(kcal=140, carb=30.0, sugar=22.0, fiber=2.4, fat=0.3)
    v = judge(dried, gi=None)      # c = 27.6 -> red, 당류비 0.73 -> red 유지
    assert v.level == "red"
    assert v.reason == "nutrient+sweet"


def test_nutrient_sweet_correction_actually_downgrades():
    n = Nutrients(kcal=90, carb=20.0, sugar=14.0, fiber=2.0, fat=0.1)
    v = judge(n, gi=None)          # c = 18 -> amber, 당류비 0.7 -> red
    assert v.level == "red"
    assert v.reason == "nutrient+sweet"


def test_zero_carb_does_not_divide_by_zero():
    """실제로는 규칙 1 우선순위를 검증한다 — carb=0, fiber=0 이면 c=0<=5 라서
    규칙 1에서 바로 반환되고 규칙 3의 나눗셈 코드에는 도달하지 않는다."""
    pork = Nutrients(kcal=330, carb=0.0, sugar=0.0, fiber=0.0, fat=28.0)
    assert judge(pork, gi=None).reason == "low-carb"


def test_nutrient_sweet_zero_carb_guard_is_actually_reached():
    """손상 데이터(fiber < 0)로 c > 5 를 만들어 규칙 3까지 내려가면서 carb=0 을
    유지해야 0-나누기 가드(`n.carb > 0 and ...`)가 실제로 실행된다."""
    corrupted = Nutrients(kcal=50, carb=0.0, sugar=0.0, fiber=-10.0, fat=0.0)
    v = judge(corrupted, gi=None)  # c = max(0, 0-(-10)) = 10 -> green, carb=0 이라 나눗셈 스킵
    assert v.level == "green"
    assert v.reason == "nutrient"


def test_fiber_exceeding_carb_is_clamped():
    """식이섬유가 탄수화물보다 큰 이상 데이터에서도 죽지 않는다."""
    weird = Nutrients(kcal=20, carb=2.0, sugar=0.0, fiber=5.0, fat=0.1)
    assert judge(weird, gi=None).level == "green"


def test_rule1_boundary_c_5_0_is_low_carb():
    """c = 5.0 은 규칙 1 경계값 — 아직 low-carb (초록)."""
    n = Nutrients(kcal=50, carb=5.0, sugar=0.0, fiber=0.0, fat=0.0)
    v = judge(n, gi=None)
    assert v.level == "green"
    assert v.reason == "low-carb"


def test_rule1_boundary_c_5_1_falls_through_to_rule3():
    """c = 5.1 은 규칙 1을 벗어나 규칙 3(nutrient)으로 넘어간다."""
    n = Nutrients(kcal=50, carb=5.1, sugar=0.0, fiber=0.0, fat=0.0)
    v = judge(n, gi=None)
    assert v.reason == "nutrient"


def test_cut_values_are_adjustable():
    """5.1의 F, S 는 인자로 바꿀 수 있어야 한다."""
    n = Nutrients(kcal=200, carb=30, sugar=12, fiber=1, fat=12)
    assert judge(n, gi=40, fat_cut=10, sugar_cut=10, sugar_abs=15).level == "amber"
    assert judge(n, gi=40, fat_cut=20, sugar_cut=20, sugar_abs=15).level == "green"


def test_지방이_없어도_당류가_많으면_내려간다():
    """이번 수정의 핵심. 지방 0g 초콜릿·건포도가 초록으로 새던 구멍."""
    raisin = Nutrients(kcal=300, carb=79.0, sugar=66.7, fiber=4.5, fat=0.5)
    v = judge(raisin, gi=55)          # GI 55 는 원래 초록
    assert v.level == "amber"
    assert v.reason == "gi+sweet"


def test_지방_없는_초콜릿도_걸린다():
    choco = Nutrients(kcal=520, carb=45.0, sugar=36.4, fiber=5.0, fat=0.0)
    assert judge(choco, gi=49).level == "amber"


def test_생과일은_보정에_걸리지_않는다():
    """당류가 있어도 생과일은 초록이어야 한다. 컷이 너무 낮으면 여기서 깨진다."""
    for name, n, gi in (
        ("사과", Nutrients(kcal=53, carb=13.1, sugar=10.4, fiber=2.7, fat=0.1), 38),
        ("바나나", Nutrients(kcal=84, carb=21.9, sugar=12.0, fiber=1.9, fat=0.2), 51),
        ("딸기", Nutrients(kcal=34, carb=8.4, sugar=5.0, fiber=1.4, fat=0.2), 40),
    ):
        v = judge(n, gi=gi)
        assert v.level == "green", f"{name}: {v}"
        assert v.reason == "gi", f"{name}: 보정에 걸렸습니다 — 컷이 너무 낮습니다"


def test_기존_지방_당류_동시조건도_계속_작동한다():
    """당류가 절대 기준 아래여도 지방과 함께면 걸려야 한다."""
    n = Nutrients(kcal=270, carb=30.0, sugar=12.0, fiber=1.5, fat=15.0)
    v = judge(n, gi=40)               # 당류 12 < 15 지만 지방 15 와 함께
    assert v.level == "amber"
    assert v.reason == "gi+sweet"


def test_세_컷이_모두_인자로_조정_가능하다():
    n = Nutrients(kcal=200, carb=30, sugar=16, fiber=1, fat=2)
    assert judge(n, gi=40, sugar_abs=15).level == "amber"
    assert judge(n, gi=40, sugar_abs=20).level == "green"


def test_나트륨은_판정을_바꾸지_않는다():
    base = Nutrients(kcal=50, carb=3.0, sugar=1.0, fiber=0.5, fat=1.0)
    salty = Nutrients(kcal=50, carb=3.0, sugar=1.0, fiber=0.5, fat=1.0, sodium=5000)
    assert judge(base, gi=None) == judge(salty, gi=None)
