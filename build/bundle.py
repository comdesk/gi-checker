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


def build(base: Path):
    records, filter_stats = load_records(
        base / "raw", base / "data" / "category_allow.csv")
    group_stats = apply_groups(records, base / "data" / "food_group.csv")
    gi_stats = apply_gi(records, base / "data" / "gi_map.csv")

    foods, groups = [], {}
    level_counts = {"green": 0, "amber": 0, "red": 0}
    kind_counts = {"measured": 0, "estimated": 0, "na": 0, "none": 0}

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

        foods.append({
            "id": r.id,
            "name": r.name,
            "display": display,
            "group": r.group,
            "method": r.method,
            "category": r.category,
            "serving": {"label": r.serving_label},
            "nutrients": {
                "kcal": r.nutrients.kcal, "carb": r.nutrients.carb,
                "sugar": r.nutrients.sugar, "fiber": r.nutrients.fiber,
                "fat": r.nutrients.fat,
            },
            "gi": {
                "value": gi_value,
                "kind": gi_kind,
                "basis": r.gi_basis if gi_kind == "estimated" else None,
            },
            "verdict": {"level": verdict.level, "reason": verdict.reason},
            "source": r.source,
            "caution": r.caution,
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
    print(f"[보충 레코드] {extras:,}건   [주의 문구] {cautions:,}건")
    print(f"\n파일 크기: {raw_mb:.1f}MB (gzip {gz_mb:.1f}MB) → {out}")

    if gz_mb > 3.0:
        print("\n경고: gzip 3MB 초과. 설계 문서 4.5대로 카테고리 분할을 검토하세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
