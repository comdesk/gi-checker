"""화면 이름 정리. 원본 표기를 그대로 내보내면 읽을 수 없다."""

import sys
from pathlib import Path

import pytest

BUILD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BUILD))

from bundle import build
from normalize import drop_meal_kits


class Rec:
    def __init__(self, name, rep_name):
        self.name, self.rep_name = name, rep_name


def test_기본_자료가_있으면_밀키트를_뺀다():
    recs = [Rec("칼국수_해물", "칼국수"),
            Rec("칼국수_간편조리세트_세숫대야 바지락칼국수", "칼국수")]
    kept, dropped = drop_meal_kits(recs)
    assert [r.name for r in kept] == ["칼국수_해물"]
    assert len(dropped) == 1


def test_기본_자료가_없으면_밀키트를_남긴다():
    """'감바스' 는 밀키트 자료뿐이다. 빼면 감바스가 아예 검색되지 않는다 —
    잡음보다 없는 것이 나쁘다."""
    recs = [Rec("감바스_간편조리세트_감바스 알 아히요", "감바스")]
    kept, dropped = drop_meal_kits(recs)
    assert len(kept) == 1 and dropped == []


@pytest.fixture(scope="module")
def bundle():
    if not (BUILD / "raw" / "원재료성_수과원.csv").exists():
        pytest.skip("원본 CSV 가 없습니다")
    return build(BUILD)[0]


def test_쉼표_표기가_없다(bundle):
    """'수컷,다리'·'양식,육' 은 원본의 표기 습관이다. 사람은 그렇게 안 읽는다."""
    bad = [f["display"] for f in bundle["foods"] if "," in f["display"]]
    assert bad == [], bad[:5]


def test_시료_표기가_이름에_남지_않는다(bundle):
    """'대표 평균'·'부산 5월' 은 음식 이름이 아니다. 답이 갈려 어쩔 수 없이
    되살린 경우만 괄호로 남는다 — 괄호 밖에 그대로 붙어 있으면 안 된다."""
    import re
    bad = [f["display"] for f in bundle["foods"]
           if re.search(r"(?<!\()\b(대표|수입)\s+(평균|\d{1,2}월)\s*$", f["display"])]
    assert bad == [], bad[:5]


def test_밀키트_상품명이_거의_남지_않는다(bundle):
    """남는 것은 기본 자료가 없어 어쩔 수 없는 것뿐이다."""
    kits = [f for f in bundle["foods"] if "간편조리세트" in f["display"]]
    assert len(kits) <= 20, f"{len(kits)}건: {[f['display'] for f in kits[:5]]}"
    reps = {f["name"].split("_")[0] for f in kits}
    plain = {f["name"].split("_")[0] for f in bundle["foods"]
             if "간편조리세트" not in f["name"]}
    assert not (reps & plain), f"기본 자료가 있는데 남은 밀키트: {sorted(reps & plain)}"


def test_분류군_이름이_종_이름과_겹쳐_나오지_않는다(bundle):
    """'오징어류 오징어 육 구운것' 처럼 분류군과 종을 나란히 적지 않는다."""
    bad = []
    for f in bundle["foods"]:
        words = f["display"].split()
        for i, w in enumerate(words[:-1]):
            if w.endswith("류") and len(w) > 2 and w[:-1] in words[i + 1]:
                bad.append(f["display"])
    assert bad == [], bad[:5]


def test_영문_품종명을_뺀다():
    """상품 품종명·연구 계통 번호는 이 앱에서 잡음이다."""
    from group import _strip_latin
    assert _strip_latin("IEC525(NO.5)") == ""              # 계통 번호 — 통째로 뺀다
    assert _strip_latin("Raon yellow(미니파프리카)") == "미니파프리카"
    assert _strip_latin("NEW복숭아아이스티") == "복숭아아이스티"
    assert _strip_latin("PB정통소보루") == "정통소보루"
    assert _strip_latin("천연효모빵 (H)") == "천연효모빵"


def test_괄호_안_단위는_지우지_않는다():
    """'(중량1g)' 의 g 까지 지우면 '(중량1)' 이 되어 뜻이 망가진다.
    괄호 안에 한글이 있으면 설명이므로 통째로 살린다."""
    from group import _strip_latin
    assert _strip_latin("커피가루(중량1g)") == "커피가루(중량1g)"
    assert _strip_latin("설탕(중량2.7g)") == "설탕(중량2.7g)"
    assert _strip_latin("큰느타리버섯(새송이버섯)") == "큰느타리버섯(새송이버섯)"


def test_화면_이름에_영문_품종명이_없다(bundle):
    """단위가 든 괄호 설명만 남아야 한다."""
    import re
    bad = [f["display"] for f in bundle["foods"]
           if re.search(r"[A-Za-z]", f["display"])
           and not re.search(r"\([^)]*[가-힣][^)]*\)", f["display"])]
    assert bad == [], bad[:5]


def test_채집지_목록에_빠진_것이_없다():
    """'평균|N월' 앞에 오는 조각은 전부 채집지다. 목록에서 빠지면 그 이름에
    시료 표기가 그대로 남는다 — 처음에 상위 40개만 보고 34건을 놓쳤다."""
    import csv
    import re as _re
    from normalize import _clean
    from group import _SAMPLE_PLACE
    raw = BUILD / "raw"
    if not (raw / "원재료성_수과원.csv").exists():
        pytest.skip("원본 CSV 가 없습니다")
    time_tag = _re.compile(r"^(평균|\d{1,2}월)$")
    missing = set()
    for filename in ("원재료성_농진청.csv", "원재료성_수과원.csv", "음식.csv"):
        with (raw / filename).open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                parts = [p.strip() for p in _clean(row["식품명"]).split("_") if p.strip()]
                if len(parts) >= 3 and time_tag.match(parts[-1]):
                    place = parts[-2]
                    if place not in _SAMPLE_PLACE and not _re.match(r"^수입\(.+\)$", place):
                        missing.add(place)
    assert missing == set(), f"채집지 목록에 없는 것: {sorted(missing)}"
