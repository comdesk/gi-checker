"""foods.json 출력. 판정과 검색 인덱스를 여기서 계산한다."""

import gzip
import json
import re
import sys
from pathlib import Path

from gi_match import apply_gi
from group import apply_groups
from normalize import load_records
from score import judge

CHOSUNG = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
HANGUL_BASE, JUNG_JONG = 0xAC00, 588
PUNCT = re.compile(r"[\s,·()\[\]/\-_.]+")

# 1회 분량 기준. 출발점은 WHO 하루 권고 2000mg 의 절반(1000mg)이었으나 실측 데이터로
# 돌려보니 전체의 7.8%(462건)에 붙어 "너무 흔해서 아무도 안 읽는" 상태였다.
# 1400mg 으로 올리면 전체의 4.8%(282건, 5% 상한 이내)로 줄면서, 국물 음식의 대표
# 예시인 알탕_해물(940ml 한 그릇 1,466mg)은 여전히 걸린다 — build/bundle.py 리포트로
# 확인했다(build/tests/test_bundle.py 의 test_나트륨_주의가_5퍼센트를_넘지_않는다 참고).
SODIUM_CAUTION_MG = 1400

# 1인분으로 보기엔 너무 큰 포장. 이 이상이면서 밀키트 이름 표시가 있는 경우에만
# perServing(1회 분량) 계산과 나트륨 주의를 건너뛴다.
#
# 처음엔 grams >= PACKAGE_GRAMS 하나만으로 걸렀는데(59건 제외), 그 59건을 전수로
# 훑어보니 38건만 실제 '간편조리세트'(밀키트)였고 나머지 21건은 해장국_선지·
# 국밥_돼지고기·짬뽕밥·올갱이국수·닭찜_안동찜닭처럼 원래 국물이 많아 1kg 을 넘는
# 정상적인 1인분 요리였다 — 하필 나트륨이 제일 걱정되는 음식들이 제외돼버려서
# 이 기능이 잡으려던 사례를 놓치는 역효과가 났다. 같은 '우동' 그룹 안에서도
# 700~800g 대가 정상군이고 1,000g '우동 중식/삼선' 은 그 분포의 상단일 뿐이다.
#
# 그래서 무게 단독 대신 "무게 + 이름 신호"로 바꿨다. 실측 결과(전체 5,894건 기준):
#   - "간편조리세트" 는 116건 있고, 그중 grams>=1000 인 것이 정확히 38건이다.
#     나머지 78건은 이미 1,000g 미만이라 애초에 제외 대상이 아니다.
#   - "밀키트" 라는 표기는 원본 데이터에 한 건도 없어서(직접 확인) 넣지 않았다 —
#     있지도 않은 패턴을 넣어봐야 아무것도 못 잡는다.
#   - "세트"(간편조리세트에 포함되는 부분 문자열이라 별도로 안 셈)·"인분"·"가족"
#     같은 다른 포장 표기 후보는 전체 데이터에서 0건이라 추가하지 않았다.
#   - grams 상위 30건을 이름과 함께 눈으로 확인한 결과, '간편조리세트' 가 아니면서
#     명백히 포장 전체로 보이는 항목은 없었다(올갱이국수 1,500g·닭찜_안동찜닭 1,500g
#     등은 원래 크게 담아내는 정상 메뉴).
PACKAGE_GRAMS = 1000
PACKAGE_NAME_MARKERS = ("간편조리세트",)


def is_package(name: str, grams: float | None) -> bool:
    """포장 전체인가. 무게만으로는 밀키트와 큰 그릇을 못 가른다.
    해장국·국밥처럼 원래 1kg 넘는 1인분 요리가 있기 때문이다.
    """
    if not grams or grams < PACKAGE_GRAMS:
        return False
    return any(m in name for m in PACKAGE_NAME_MARKERS)


def search_norm(text: str) -> str:
    return PUNCT.sub("", str(text or "")).lower()


def chosung_of(text: str) -> str:
    """'고구마' -> 'ㄱㄱㅁ'. 한글이 아닌 글자는 그대로 둔다.

    web/search.js 의 chosungOf 와 결과가 같아야 한다. 그쪽은 정규화된 질의로
    비교하므로 여기서도 구두점을 뗀 뒤에 뽑는다.
    """
    out = []
    for ch in str(text or ""):
        code = ord(ch)
        if HANGUL_BASE <= code <= 0xD7A3:
            out.append(CHOSUNG[(code - HANGUL_BASE) // JUNG_JONG])
        elif not ch.isspace():
            out.append(ch)
    return "".join(out)


def search_aliases(name: str, display: str, alias: list[str]) -> list[str]:
    """검색 별칭 집합. 화면 이름이 원본 표기와 다르면 그것으로도 찾아져야 한다.

    group.py 가 채운 alias 와 별개로, display 자체를 반드시 포함시킨다.
    """
    out = {search_norm(a) for a in alias}
    out.add(search_norm(display))
    out.discard(search_norm(name))
    out.discard("")
    return sorted(out)


def per_serving(n, grams):
    """1회 분량 기준 환산. 분량을 모르면 None.

    수치는 100g 기준이므로 grams/100 을 곱한다.
    ml 은 밀도를 몰라 1ml=1g 으로 근사한다 (normalize.py 와 같은 가정).
    나트륨이 원본에 없으면(None) 환산해도 여전히 None — 0을 만들어내지 않는다.
    """
    if not grams:
        return None
    k = grams / 100.0
    return {
        "kcal": round(n.kcal * k, 1), "carb": round(n.carb * k, 1),
        "sugar": round(n.sugar * k, 1), "fiber": round(n.fiber * k, 1),
        "fat": round(n.fat * k, 1),
        "sodium": None if n.sodium is None else round(n.sodium * k),
    }


def build(base: Path):
    records, filter_stats = load_records(
        base / "raw", base / "data" / "category_allow.csv")
    group_stats = apply_groups(records, base / "data" / "food_group.csv")
    gi_stats = apply_gi(records, base / "data" / "gi_map.csv")

    foods, groups = [], {}
    level_counts = {"green": 0, "amber": 0, "red": 0}
    kind_counts = {"measured": 0, "estimated": 0, "na": 0, "none": 0}
    sodium_caution_count = 0
    package_count = 0
    sodium_none_count = 0

    for r in records:
        verdict = judge(r.nutrients, r.gi_value)

        # 규칙 1(저탄수)로 초록이 된 항목은 GI 가 성립하지 않는 음식이다.
        # 빈칸이 아니라 'na' 로 표시해 화면에서 이유를 설명할 수 있게 한다.
        gi_kind = "na" if verdict.reason == "low-carb" else r.gi_kind
        gi_value = None if gi_kind == "na" else r.gi_value

        level_counts[verdict.level] += 1
        kind_counts[gi_kind] += 1
        if r.group:
            groups.setdefault(r.group, []).append(r.id)

        display = r.display or r.name
        # 화면에 보이는 이름으로도 검색되어야 한다. 원본 표기와 다를 수 있다.
        aliases = search_aliases(r.name, display, r.alias)

        if r.nutrients.sodium is None:
            sodium_none_count += 1

        # 1인분으로 보기엔 너무 큰 포장(간편조리세트 등)만 1회 분량 환산에서 뺀다.
        # 무게만으로 거르면 해장국·국밥처럼 원래 1kg 넘는 정상 1인분까지 걸린다.
        packaged = is_package(r.name, r.serving_grams)
        if packaged:
            package_count += 1
        ps = None if packaged else per_serving(r.nutrients, r.serving_grams)

        # 나트륨 주의 자동 생성. 손으로 쓴 caution.csv 가 있으면 그것이 우선한다.
        # 포장 전체(packaged)나 나트륨을 모르는 경우(ps["sodium"] is None)는
        # 건너뛴다 — 근거 없는 숫자로 "한 번에 ○○mg" 라고 단정하지 않는다.
        # 한 그릇에 하루 권고량의 절반이 넘는 나트륨이면 알린다.
        # 신호등(혈당)은 건드리지 않고 문구만 붙인다.
        caution = r.caution
        if (not caution and ps and ps["sodium"] is not None
                and ps["sodium"] >= SODIUM_CAUTION_MG):
            caution = f"나트륨이 한 번에 {ps['sodium']:,}mg 입니다. 혈압이 있으시면 주의하세요."
            sodium_caution_count += 1

        foods.append({
            "id": r.id,
            "name": r.name,
            "display": display,
            "group": r.group,
            "method": r.method,
            "category": r.category,
            "serving": {"label": r.serving_label, "grams": r.serving_grams,
                        "isPackage": packaged},
            "nutrients": {
                "kcal": r.nutrients.kcal, "carb": r.nutrients.carb,
                "sugar": r.nutrients.sugar, "fiber": r.nutrients.fiber,
                "fat": r.nutrients.fat, "sodium": r.nutrients.sodium,
            },
            "perServing": ps,
            "gi": {
                "value": gi_value,
                "kind": gi_kind,
                "basis": r.gi_basis if gi_kind == "estimated" else None,
            },
            "verdict": {"level": verdict.level, "reason": verdict.reason},
            "source": r.source,
            "caution": caution,
            "search": {
                "norm": search_norm(r.name),
                "chosung": chosung_of(search_norm(r.name)),
                "alias": aliases,
            },
        })

    # 조리법 비교는 GI 오름차순. GI 없는 항목은 뒤로.
    order = {f["id"]: (f["gi"]["value"] is None, f["gi"]["value"] or 0) for f in foods}
    for name in groups:
        groups[name].sort(key=lambda fid: order[fid])

    bundle = {
        "version": "2026-08-11",
        "groups": {k: v for k, v in groups.items() if len(v) >= 2},
        "foods": foods,
    }
    stats = {
        "filter": filter_stats, "group": group_stats, "gi": gi_stats,
        "level": level_counts, "kind": kind_counts,
        "sodium_caution": sodium_caution_count,
        "package": package_count, "sodium_none": sodium_none_count,
    }
    return bundle, stats


def main() -> int:
    base = Path(__file__).resolve().parent
    bundle, stats = build(base)

    out = base.parent / "web" / "foods.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(bundle, ensure_ascii=False, separators=(",", ":"))
    out.write_text(text, encoding="utf-8")

    raw_mb = len(text.encode("utf-8")) / 1_048_576
    gz_mb = len(gzip.compress(text.encode("utf-8"))) / 1_048_576
    total = len(bundle["foods"])

    print("=" * 60)
    print("빌드 리포트")
    print("=" * 60)
    for title, block in (("[품목 필터]", stats["filter"]),
                         ("[조리법 묶기]", stats["group"]),
                         ("[GI 커버리지]", stats["gi"])):
        print(title)
        for k, v in block.items():
            print(f"  {k:>12}: {v:,}")
    print(f"  {'그룹 수':>12}: {len(bundle['groups']):,}")

    print("[GI 표시 상태]")
    for k, v in stats["kind"].items():
        print(f"  {k:>12}: {v:,} ({v / total * 100:.1f}%)")
    print("[신호등 분포]")
    for k, v in stats["level"].items():
        print(f"  {k:>12}: {v:,} ({v / total * 100:.1f}%)")

    cautions = sum(1 for f in bundle["foods"] if f["caution"])
    extras = sum(1 for f in bundle["foods"] if f["source"])
    sodium_pct = stats["sodium_caution"] / total * 100
    print(f"[보충 레코드] {extras:,}건   [주의 문구] {cautions:,}건 "
          f"(그중 나트륨 자동 생성 {stats['sodium_caution']:,}건, 전체의 {sodium_pct:.1f}%)")
    if sodium_pct > 5.0:
        print(f"경고: 나트륨 주의가 전체의 {sodium_pct:.1f}% — SODIUM_CAUTION_MG 를 올리는 것을 검토하세요.")
    markers = "/".join(PACKAGE_NAME_MARKERS)
    print(f"[포장 전체 제외(grams>={PACKAGE_GRAMS} 이고 이름에 '{markers}')] "
          f"{stats['package']:,}건 — perServing·나트륨 주의 대상에서 제외")
    print(f"[나트륨 모름(None)] {stats['sodium_none']:,}건 "
          f"({stats['sodium_none'] / total * 100:.1f}%) — 원본 공란, 0으로 채우지 않음")
    print(f"\n파일 크기: {raw_mb:.1f}MB (gzip {gz_mb:.1f}MB) → {out}")

    if gz_mb > 3.0:
        print("\n경고: gzip 3MB 초과. 설계 문서 4.5대로 카테고리 분할을 검토하세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
