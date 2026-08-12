"""foods.json 출력. 판정과 검색 인덱스를 여기서 계산한다."""

import gzip
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from statistics import quantiles

from gi_match import apply_gi
from group import METHOD_PREFIX, METHOD_TOKENS, apply_groups
from normalize import apply_nutrient_fixes, fill_missing, load_records
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
    모르는 값(None)은 환산해도 여전히 None — 0을 만들어내지 않는다.
    """
    if not grams:
        return None
    k = grams / 100.0

    def scale(value, digits=1):
        return None if value is None else round(value * k, digits)

    return {
        "kcal": scale(n.kcal), "carb": scale(n.carb),
        "sugar": scale(n.sugar), "fiber": scale(n.fiber),
        "fat": scale(n.fat),
        "sodium": None if n.sodium is None else round(n.sodium * k),
    }


# 식이섬유를 끝내 모를 때 '최선의 경우' 를 어디까지 인정할지.
# 상한 없이 두면 최선의 경우가 늘 c=0(초록)이 되어 거의 다 unknown 이 된다.
# 같은 카테고리에서 실제로 관찰된 식이섬유/탄수화물 비율의 90퍼센타일을 쓴다 —
# '이 부류 음식 중 식이섬유가 아주 많은 축' 까지는 봐주되 그 이상은 상상하지 않는다.
FIBER_RATIO_PERCENTILE = 90
FIBER_RATIO_MIN_SAMPLES = 10


def fiber_ratio_caps(records) -> dict[str, float]:
    ratios: dict[str, list[float]] = defaultdict(list)
    for r in records:
        n = r.nutrients
        if n.fiber is not None and n.carb > 0:
            ratios[r.category].append(min(n.fiber / n.carb, 1.0))
    caps = {}
    for category, values in ratios.items():
        if len(values) >= FIBER_RATIO_MIN_SAMPLES:
            caps[category] = quantiles(values, n=10)[FIBER_RATIO_PERCENTILE // 10 - 1]
    return caps


def fiber_ceiling(r, caps: dict[str, float]) -> float | None:
    """이 음식의 식이섬유가 최대 얼마까지일 수 있는가(g). 근거가 없으면 None."""
    cap = caps.get(r.category)
    return None if cap is None else r.nutrients.carb * cap


def _variant_part(name: str, group: str) -> str:
    """원본 name 에서 group 을 이루는 낱말과 조리법 표기를 뺀 나머지.

    '감자_대지_찐것' + group='감자' -> '대지' (변종/맛 표기 등, 사실상 '품종').
    뺄 게 없으면(빈 문자열) 그 항목은 목록에 안 넣는다(호출부가 판단).
    """
    parts = [p.strip() for p in name.split("_") if p.strip()]
    group_words = set(group.split())
    kept = [p for p in parts if p not in group_words and p not in METHOD_TOKENS]
    return " ".join(kept).strip()


# 답(gi.value·verdict.level)이 같아도 영양성분이 크게 벌어지면 합치지 않는다.
# 답이 우연히 같더라도('오늘의 판정'이 같을 뿐) 실제로는 다른 음식일 수 있다
# (예: 백미와 현미, 마른 콩과 삶아 불린 콩, 국수 종류별). 두 조건을 모두
# 만족해야 제외한다:
#   - carb_max 가 CARB_RATIO_FLOOR(g) 이상이다 — 절대량이 작으면(예: 게살류
#     0~9.9g) 몇 배 차이라도 실질적 영향이 없다
#   - carb_max 가 carb_min 의 CARB_RATIO_LIMIT 배 이상이다(0으로 나누는 것을
#     피하기 위해 carb_min==0 이면 절대량 조건만으로 판단한다)
CARB_RATIO_LIMIT = 2.0
CARB_RATIO_FLOOR = 10.0


def _too_spread_to_merge(carbs: list[float]) -> bool:
    carb_min, carb_max = min(carbs), max(carbs)
    if carb_max < CARB_RATIO_FLOOR:
        return False
    if carb_min <= 0:
        return True
    return carb_max / carb_min >= CARB_RATIO_LIMIT


def merge_variants(foods: list[dict], groups: dict[str, list[str]],
                   labels: dict[str, str] | None = None):
    """답(gi.value·verdict.level)이 완전히 같은 (group, method) 묶음을 한 줄로 합친다.

    사용자가 실제로 겪은 문제: '감자 대지 찐것' 같은 품종명이 그대로 화면에
    나오고, 답이 똑같은 품종이 여러 줄로 반복됐다. 품종은 답에 영향이
    없으면 잡음이다.

    합치는 조건 (전부 만족해야 한다 — 하나라도 다르면 답이 다른 것이므로
    그대로 둔다):
      1. gi.value 가 모두 같다 (None 끼리도 같은 것으로 본다)
      2. verdict.level 이 모두 같다
      3. 묶음에 2건 이상 있다

    합칠 때 영양성분은 평균 내지 않는다 — 대표 하나(이름이 가장 단순한 것)의
    값을 그대로 쓴다. 평균을 내면 실제로 존재하지 않는 음식이 만들어진다.

    groups 딕셔너리(조리법 비교용 id 목록)에서도 사라진 id 를 지운다 —
    안 그러면 조리법 비교가 존재하지 않는 레코드를 가리키게 된다.

    반환: (합쳐진 foods 리스트, 리포트 목록 — 편차 검증용).
    """
    # 양념 여부까지 키에 넣는다. 안 그러면 '조미하여 말린것'(0.4g)이 답이 같다는
    # 이유로 '말린것'(0.2g) 안에 숨어 사라진다 — 양념이 붙었다는 사실이 지워진다.
    buckets: dict[tuple, list[dict]] = {}
    for f in foods:
        if f["group"] and f["method"]:
            buckets.setdefault(
                (f["group"], f["method"], f.get("seasoning")), []).append(f)

    removed_ids: set[str] = set()
    reports = []
    skipped = []

    for (group, method, seasoning), items in buckets.items():
        if len(items) < 2:
            continue
        answers = {(f["gi"]["value"], f["verdict"]["level"]) for f in items}
        if len(answers) != 1:
            continue   # 답이 다르면 합치지 않는다 — 정보를 숨기면 안 된다

        carbs = [f["nutrients"]["carb"] for f in items]
        carb_min, carb_max = min(carbs), max(carbs)
        spread = round(carb_max - carb_min, 1)

        if _too_spread_to_merge(carbs):
            # 답은 같지만 영양성분이 실제로 다른 음식일 만큼 벌어져 있다.
            # 답이 같다고 다 합치면 존재하지 않는 대표성을 만든다 — 그대로 둔다.
            skipped.append({
                "group": group, "method": method, "count": len(items),
                "carb_min": carb_min, "carb_max": carb_max, "carb_spread": spread,
                "members": [f["name"] for f in items],
            })
            continue

        # 대표: 이름이 가장 단순한 것('_' 로 나눈 토막이 가장 적은 것). 동점이면 짧은 것.
        rep = min(items, key=lambda f: (f["name"].count("_"), len(f["name"])))

        # 그룹 키가 아니라 사람이 부르는 이름을 쓴다 — '데친 호박 애호박' 이 아니라
        # '데친 애호박'. labels 가 없으면(단위 테스트) 키를 그대로 쓴다.
        label = (labels or {}).get(rep["id"], group)
        prefix = METHOD_PREFIX.get(method)
        base = f"{prefix} {label}" if prefix else label
        # 양념 표기를 지우면 안 된다 — '조미하여 구운 오징어' 가 '구운 오징어' 로
        # 둔갑해 탄수화물 26.6g 이 조리법 탓처럼 보인다.
        # 단 조리법 자체가 절이기면 '절인 배추 (소금 절임)' 처럼 겹쳐 읽힌다.
        show_season = seasoning and method != "절이기"
        rep["display"] = f"{base} ({seasoning})" if show_season else base
        # 이름을 바꿨으면 그 이름으로도 검색돼야 한다.
        # (단위 테스트의 최소 dict 에는 search 가 없다 — 있을 때만 손댄다)
        search = rep.get("search")
        norm = search_norm(rep["display"])
        if search and norm and norm != search["norm"] and norm not in search["alias"]:
            search["alias"] = sorted(search["alias"] + [norm])

        variants = []
        for f in items:
            v = _variant_part(f["name"], group)
            if v and v not in variants:
                variants.append(v)
        # 뽑아낸 품종이 1개 이하면(예: 이름 없는 대표 하나 + 품종 있는 것 하나가
        # 합쳐진 경우) '품종 N종' 표시가 의미 없다 — render.js 도 2개 미만이면
        # 표시하지 않는다. 그래도 합치기 자체(레코드 축소)는 그대로 한다.
        if len(variants) >= 2:
            rep["variants"] = variants

        reports.append({
            "group": group, "method": method, "count": len(items),
            "display": rep["display"], "variants": variants,
            "carb_min": carb_min, "carb_max": carb_max, "carb_spread": spread,
            "members": [f["name"] for f in items],
        })

        for f in items:
            if f is not rep:
                removed_ids.add(f["id"])

    merged_foods = [f for f in foods if f["id"] not in removed_ids]
    for ids in groups.values():
        ids[:] = [i for i in ids if i not in removed_ids]

    reports.sort(key=lambda r: -r["carb_spread"])
    skipped.sort(key=lambda r: -r["carb_spread"])
    return merged_foods, reports, skipped


def build(base: Path):
    records, filter_stats = load_records(
        base / "raw", base / "data" / "category_allow.csv")
    group_stats = apply_groups(records, base / "data" / "food_group.csv")
    # 손으로 채운 값이 먼저다 — 사람이 이미 답을 아는 것을 기계가 추정하면 안 된다.
    fixed_count = apply_nutrient_fixes(records, base / "data" / "nutrient_fix.csv")
    # 상속은 조리법을 보므로 apply_groups 다음이어야 한다 — 말린 것과 생것은
    # 수분이 빠져 농도가 몇 배 다르니 같은 조리법끼리 물려받아야 한다.
    fill_stats = fill_missing(records)
    fiber_caps = fiber_ratio_caps(records)
    gi_stats = apply_gi(records, base / "data" / "gi_map.csv")

    foods, groups = [], {}
    level_counts = {"green": 0, "amber": 0, "red": 0, "unknown": 0}
    kind_counts = {"measured": 0, "estimated": 0, "na": 0, "none": 0}
    sodium_caution_count = 0
    package_count = 0
    sodium_none_count = 0

    for r in records:
        verdict = judge(r.nutrients, r.gi_value,
                        fiber_max=fiber_ceiling(r, fiber_caps))

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
            # 그룹 키와 사람이 부르는 이름이 다를 때만 싣는다 (4천 건에 매번
            # 같은 문자열을 넣을 이유가 없다). 키 '호박 단호박' → 이름 '단호박'.
            **({"groupLabel": r.group_label}
               if r.group and r.group_label and r.group_label != r.group else {}),
            "method": r.method,
            # 양념·절임 표기. 있으면 화면에 반드시 밝힌다 — 탄수화물이 조리법
            # 탓인지 양념 탓인지 사용자가 알아야 한다.
            **({"seasoning": r.seasoning} if r.seasoning else {}),
            "category": r.category,
            "serving": {"label": r.serving_label, "grams": r.serving_grams,
                        "isPackage": packaged},
            "nutrients": {
                "kcal": r.nutrients.kcal, "carb": r.nutrients.carb,
                "sugar": r.nutrients.sugar, "fiber": r.nutrients.fiber,
                "fat": r.nutrients.fat, "sodium": r.nutrients.sodium,
            },
            # 원본에 없어 같은 대표식품명에서 추정한 항목. 측정값인 척하면 안 되므로
            # 화면에서 '추정' 이라고 밝힌다. null 은 끝내 모른다는 뜻이다.
            "estimated": list(r.inherited),
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

    # 답(gi.value·verdict.level)이 완전히 같은 (group, method) 묶음을 한 줄로
    # 합친다. 사라진 레코드의 id 는 groups 목록에서도 지운다(merge_variants 가
    # groups 를 제자리에서 갱신한다) — 안 그러면 조리법 비교가 사라진 id 를 가리킨다.
    before_total = len(foods)
    group_labels = {r.id: r.group_label for r in records if r.group_label}
    foods, merge_reports, merge_skipped = merge_variants(foods, groups, group_labels)
    merged_records = before_total - len(foods)

    # 신호등·GI 표시 상태 분포는 합치기 이후(실제로 화면에 보이는 레코드) 기준으로
    # 다시 센다. 합쳐서 사라진 레코드는 대표와 답이 완전히 같았으므로, 그 답의
    # 비중만 줄어드는 것이지 다른 답의 비중이 늘어나는 것은 아니다.
    level_counts_before = dict(level_counts)
    kind_counts_before = dict(kind_counts)
    level_counts = {"green": 0, "amber": 0, "red": 0, "unknown": 0}
    kind_counts = {"measured": 0, "estimated": 0, "na": 0, "none": 0}
    for f in foods:
        level_counts[f["verdict"]["level"]] += 1
        kind_counts[f["gi"]["kind"]] += 1

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
        "fill": fill_stats, "nutrient_fix": fixed_count,
        "merge": {
            "before_total": before_total, "after_total": len(foods),
            "merged_records": merged_records, "bundles": len(merge_reports),
            "reports": merge_reports, "skipped": merge_skipped,
            "level_before": level_counts_before, "kind_before": kind_counts_before,
        },
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

    print("[빈 칸 메우기] 원본 공란을 0으로 찍지 않고 같은 대표식품명에서 비율로 물려받는다")
    for key in sorted(stats["fill"]):
        print(f"  {key:>14}: {stats['fill'][key]:,}")
    print(f"  {'손으로 채움':>14}: {stats['nutrient_fix']:,} (nutrient_fix.csv)")
    est = sum(1 for f in bundle["foods"] if f["estimated"])
    unknown = stats["level"]["unknown"]
    print(f"  화면 기준 추정치 포함 {est:,}건 ({est / total * 100:.1f}%), "
          f"끝내 판정 불가 {unknown:,}건 ({unknown / total * 100:.1f}%)")

    merge = stats["merge"]
    print("[답이 같은 품종 합치기]")
    print(f"  합치기 전: {merge['before_total']:,}건 → 합치기 후: {merge['after_total']:,}건 "
          f"(-{merge['merged_records']:,}건, {merge['bundles']:,}묶음)")
    print("  [신호등 분포 전/후]")
    for k in ("green", "amber", "red"):
        b, a = merge["level_before"][k], stats["level"][k]
        print(f"    {k:>6}: {b:,} ({b / merge['before_total'] * 100:.1f}%)"
              f"  ->  {a:,} ({a / total * 100:.1f}%)")
    print("  [영양성분(탄수화물) 편차 상위 20건 — 실제로 합쳐진 묶음 중]")
    for r in merge["reports"][:20]:
        print(f"    {r['group']}/{r['method']} ({r['count']}건, {r['display']}): "
              f"탄수화물 {r['carb_min']:g}~{r['carb_max']:g}g (편차 {r['carb_spread']:g}g) "
              f"품종 {', '.join(r['variants']) or '(없음)'}")
    if merge["skipped"]:
        print(f"  [답은 같지만 편차가 커서 합치지 않은 묶음: {len(merge['skipped'])}건 "
              f"(탄수화물 {CARB_RATIO_LIMIT:g}배 이상 & {CARB_RATIO_FLOOR:g}g 이상)]")
        for r in merge["skipped"][:20]:
            print(f"    {r['group']}/{r['method']} ({r['count']}건): "
                  f"탄수화물 {r['carb_min']:g}~{r['carb_max']:g}g (편차 {r['carb_spread']:g}g)")
    print(f"\n파일 크기: {raw_mb:.1f}MB (gzip {gz_mb:.1f}MB) → {out}")

    if gz_mb > 3.0:
        print("\n경고: gzip 3MB 초과. 설계 문서 4.5대로 카테고리 분할을 검토하세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
