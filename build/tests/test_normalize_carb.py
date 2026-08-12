"""차감법 탄수화물 오류 검출.

원본의 탄수화물은 측정값이 아니라 차감값(100 - 수분 - 단백질 - 지방 - 회분)이라,
다른 성분의 측정이 실패하면 그 오차가 통째로 탄수화물로 넘어온다.
"""

import sys
from pathlib import Path

import pytest

BUILD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BUILD))

from bundle import build
from normalize import drop_broken_carb
from score import Nutrients


class Rec:
    """drop_broken_carb 가 보는 최소 레코드."""
    def __init__(self, name, carb, protein, is_prepared=False):
        self.name, self.protein, self.is_prepared = name, protein, is_prepared
        self.nutrients = Nutrients(kcal=100, carb=carb, sugar=0, fiber=0, fat=1)
        self.group, self.method, self.seasoning, self.rep_name = "갈치", "생것", None, "갈치"


def test_단백질이_무너진_만큼_탄수화물이_는_시료를_버린다():
    """갈치 5월: 단백질 6.76g(다른 달 17~20g), 탄수화물 12.1g(다른 달 0).
    생선에 탄수화물 12g 은 없다 — 단백질 측정이 틀린 것이다."""
    recs = [Rec("갈치_1월", 0.0, 18.9), Rec("갈치_2월", 0.2, 18.5),
            Rec("갈치_3월", 0.0, 19.2), Rec("갈치_5월", 12.1, 6.76)]
    kept, dropped = drop_broken_carb(recs)
    assert [n for n, _ in dropped] == ["갈치_5월"]
    assert len(kept) == 3


def test_성한_시료가_없으면_버리지_않는다():
    """하나뿐인 음식을 지우면 검색이 안 되는 것이 오히려 손해다."""
    recs = [Rec("갈치_5월", 12.1, 6.76)]
    kept, dropped = drop_broken_carb(recs)
    assert dropped == [] and len(kept) == 1


def test_조리식품에는_적용하지_않는다():
    """같은 '닭튀김' 이라도 레시피에 따라 튀김옷과 소스가 달라
    단백질이 낮고 탄수화물이 높은 것이 정상이다."""
    recs = [Rec("닭튀김_a", 0.0, 18.9, is_prepared=True),
            Rec("닭튀김_b", 0.2, 18.5, is_prepared=True),
            Rec("닭튀김_c", 0.0, 19.2, is_prepared=True),
            Rec("닭튀김_꿔바로우", 12.1, 6.76, is_prepared=True)]
    kept, dropped = drop_broken_carb(recs)
    assert dropped == [] and len(kept) == 4


def test_탄수화물만_높은_것은_버리지_않는다():
    """단백질이 멀쩡한데 탄수화물만 높으면 진짜로 탄수화물이 많은 음식이다
    (마카롱·프레즐·떡볶이). 합계 보존 조건이 그것을 걸러낸다."""
    recs = [Rec("a", 0.0, 18.9), Rec("b", 0.2, 18.5),
            Rec("c", 0.0, 19.2), Rec("진짜단음식", 40.0, 18.7)]
    kept, dropped = drop_broken_carb(recs)
    assert dropped == [] and len(kept) == 4


@pytest.fixture(scope="module")
def bundle():
    if not (BUILD / "raw" / "원재료성_수과원.csv").exists():
        pytest.skip("원본 CSV 가 없습니다")
    return build(BUILD)[0]


def test_생선에_탄수화물_덩어리가_남아_있지_않다(bundle):
    """실제 산출물 확인. 갈치·피조개·멸치가 탄수화물 때문에 빨강이 되면 안 된다."""
    for name in ("갈치류_갈치_육_생것_대표_5월",
                 "꼬막류_피조개_전체_생것_대표_평균",
                 "멸치_전체_말린것_대표_7월"):
        assert not [f for f in bundle["foods"] if f["name"] == name], \
            f"{name} 이 아직 남아 있다"
