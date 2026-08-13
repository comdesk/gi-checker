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


# ── 모르는 값은 0이 아니다 (구간 판정) ──────────────────────────────────

def test_당류를_모르면_단_음식_보정을_건너뛰지_않는다():
    """당밀 사건. 원본에 당류 칸이 비어 있다고 0으로 찍으면
    탄수화물 68.2g 짜리 시럽이 GI 55(초록 경계)로 통과해 '드셔도 좋아요'가 된다.
    모르면 '단 음식일 수도 있다'고 봐야 한다."""
    molasses = Nutrients(kcal=274, carb=68.2, sugar=None, fiber=None, fat=None)
    assert judge(molasses, gi=55).level != "green"


def test_식이섬유를_모르면_거짓_빨강도_안_된다():
    """반대 방향. 콩(대두) 갈색콩은 식이섬유가 비어 있어 c=30.6 으로 계산돼
    빨강이었지만, 같은 대두인 서리태는 식이섬유 20.8 로 초록이었다.
    모르면 빨강으로 단정해서도 안 된다."""
    bean = Nutrients(kcal=409, carb=30.6, sugar=None, fiber=None, fat=17.2)
    assert judge(bean, gi=None, fiber_max=25.0).level != "red"


def test_값이_다_있으면_구간_판정이_끼어들지_않는다():
    """결측 처리가 기존 판정을 흔들면 안 된다."""
    known = Nutrients(kcal=130, carb=28.0, sugar=0.1, fiber=0.4, fat=0.3)
    assert judge(known, gi=73) == judge(known, gi=73, fiber_max=5.0)


def test_모르는_값의_범위_양_끝이_같으면_확정한다():
    """모른다고 전부 unknown 이 되면 앱이 쓸모없어진다.
    탄수화물이 2g 이면 식이섬유가 얼마든 규칙 1로 초록이다."""
    lettuce = Nutrients(kcal=12, carb=2.0, sugar=None, fiber=None, fat=None)
    v = judge(lettuce, gi=None)
    assert v.level == "green"
    assert v.reason == "low-carb"


def test_답이_갈리면_unknown():
    """최선과 최악이 다르면 모른다고 말한다. 찍지 않는다."""
    dried_herb = Nutrients(kcal=300, carb=77.0, sugar=None, fiber=None, fat=None)
    v = judge(dried_herb, gi=None, fiber_max=60.0)
    assert v.level == "unknown"
    assert v.reason == "insufficient"


def test_fiber_max가_없으면_탄수화물_전부를_식이섬유로_볼_수_있다():
    """근거가 없으면 최선의 경우를 넉넉히 잡는다 — 함부로 나쁘게 단정하지 않는다."""
    unknown_food = Nutrients(kcal=300, carb=70.0, sugar=None, fiber=None, fat=None)
    assert judge(unknown_food, gi=None).level == "unknown"


# ── 규칙 4: 한 번에 먹는 양 ──────────────────────────────────
# GI 는 '얼마나 빨리 오르나'지 '얼마나 오르나'가 아니다. 양까지 반영한 것이
# 혈당부하(GL) = GI × 소화되는 탄수화물 ÷ 100 이다.
#
# 이 규칙이 없을 때 실제로 나온 답: 자장면 GI 46 → 초록. 한 그릇(600g)에
# 탄수화물 175g 으로 쌀밥 세 공기인데 '드셔도 좋아요' 라고 했다.


def test_한_그릇_양이_많으면_gi_가_낮아도_빨강():
    """자장면. GI 46(낮음)이지만 한 그릇 600g 에 탄수화물 175g → GL 75."""
    jajang = Nutrients(kcal=350, carb=29.1, sugar=2.9, fiber=1.8, fat=2.5)
    assert judge(jajang, gi=46).level == "green"          # 분량을 모르면 지금과 같다
    v = judge(jajang, gi=46, serving_grams=600)
    assert v.level == "red"
    assert v.reason == "serving"


def test_아이스크림은_지방이_gi_를_눌러도_양에서_걸린다():
    """GI 36 은 지방이 흡수를 늦춰서 낮은 것이다. 한 통 311g 에 당류 48g."""
    ice = Nutrients(kcal=300, carb=51.7, sugar=15.6, fiber=1.5, fat=7.6)
    v = judge(ice, gi=36, serving_grams=311)
    assert v.level == "red"


def test_양이_적어도_등급을_올리지는_않는다():
    """내리기만 한다. 분량 자료가 틀렸을 때 거짓 초록이 나오면 안 된다."""
    bread = Nutrients(kcal=280, carb=50.9, sugar=1.6, fiber=3.5, fat=4.0)
    assert judge(bread, gi=73).level == "red"
    assert judge(bread, gi=73, serving_grams=20).level == "red"


def test_gl_경계값():
    """GL 10 이하 낮음, 20 이상 높음 (국제 기준)."""
    n = Nutrients(kcal=100, carb=20.0, sugar=1.0, fiber=0.0, fat=0.5)
    # GI 50, 100g → GL 10 → 그대로 초록
    assert judge(n, gi=50, serving_grams=100).level == "green"
    # GI 50, 110g → GL 11 → 노랑
    assert judge(n, gi=50, serving_grams=110).level == "amber"
    # GI 50, 200g → GL 20 → 빨강
    assert judge(n, gi=50, serving_grams=200).level == "red"


def test_gi_가_없으면_한_번_먹는_탄수화물로_본다():
    """떡국. GI 자료가 없고 100g 당 16.4g 이라 노랑이었지만
    한 그릇 700g 이면 탄수화물 109g 이다."""
    tteokguk = Nutrients(kcal=120, carb=16.4, sugar=0.1, fiber=0.8, fat=1.0)
    assert judge(tteokguk, gi=None).level == "amber"
    v = judge(tteokguk, gi=None, serving_grams=700)
    assert v.level == "red"
    assert v.reason == "serving"


def test_한_번_먹는_탄수화물_경계값():
    """15g = 탄수화물 1교환단위, 45g = 당뇨 식사요법의 한 끼 하한."""
    n = Nutrients(kcal=100, carb=10.0, sugar=0.5, fiber=0.0, fat=0.2)
    assert judge(n, gi=None, serving_grams=100).level == "green"   # 10g
    assert judge(n, gi=None, serving_grams=160).level == "amber"   # 16g
    assert judge(n, gi=None, serving_grams=460).level == "red"     # 46g


def test_탄수화물이_거의_없으면_분량이_커도_초록():
    """규칙 1이 먼저다. 설렁탕 한 그릇 500g 을 먹어도 탄수화물이 없다."""
    seolleongtang = Nutrients(kcal=50, carb=0.4, sugar=0.0, fiber=0.0, fat=2.0)
    assert judge(seolleongtang, gi=None, serving_grams=500).level == "green"


def test_분량을_모르면_지금_규칙_그대로():
    """원재료(생 고구마 100g 등)는 한 번에 얼마를 먹는지 모른다."""
    n = Nutrients(kcal=130, carb=31.0, sugar=5.0, fiber=2.0, fat=0.2)
    assert judge(n, gi=55) == judge(n, gi=55, serving_grams=None)


def test_결측값이_있어도_분량_규칙이_적용된다():
    """당류를 모르는 경우에도 구간의 양 끝 모두에 적용돼야 한다.
    양 끝이 다 빨강이면 unknown 이 아니라 빨강이다."""
    n = Nutrients(kcal=350, carb=29.1, sugar=None, fiber=1.8, fat=2.5)
    v = judge(n, gi=46, serving_grams=600)
    assert v.level == "red"


def test_식이섬유_상한은_당류가_차지한_몫을_넘을_수_없다():
    """당류도 식이섬유도 탄수화물의 일부다. 둘의 합이 탄수화물을 넘을 수 없다.

    망고스무디(탄수화물 20.1g, 당류 16.6g, 식이섬유 모름)를 이 상한 없이 보면
    '식이섬유가 15g 일 수도 있다'는 최선의 경우가 만들어져 초록이 되고,
    최악의 경우와 갈려 '알 수 없음' 이 된다. 당류가 16.6g 인 이상 식이섬유는
    아무리 많아도 3.5g 이다.
    """
    smoothie = Nutrients(kcal=100, carb=20.1, sugar=16.6, fiber=None, fat=0.9)
    v = judge(smoothie, gi=34, serving_grams=591, fiber_max=18.0)
    assert v.level == "red", v


def test_저탄수라도_한_그릇이_크면_양을_본다():
    """규칙 1은 100g 기준이라 그릇 크기를 못 본다. 국밥은 100g 당 5g 이지만
    한 그릇 700g 이면 35g 이다 — '혈당에 거의 영향 없어요' 는 틀린 말이 된다."""
    gukbap = Nutrients(kcal=60, carb=5.0, sugar=0.3, fiber=0.0, fat=1.5)
    assert judge(gukbap, gi=None).level == "green"
    v = judge(gukbap, gi=None, serving_grams=700)
    assert v.level == "amber"
    assert v.reason == "serving"
