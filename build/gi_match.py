"""GI 수치 붙이기.

세 단계로 시도한다.
  1) '대표식품명 조리법' → '대표식품명' → '식품명' 정확 매칭  → measured
  2) 같은 그룹 + 같은 조리법 안의 measured 항목에서 상속        → estimated
  3) 어느 쪽도 아니면                                         → none

설계 문서 5절 단서: 추정 GI 도 판정에 그대로 쓰이므로 상속은 보수적으로만
허용한다. 같은 그룹 안에서만 상속하고, 그룹이 없으면 상속하지 않는다.

[리뷰 반영] 상속 도너를 그룹만으로 고르면 조리법이 다른 항목이 엉뚱한 값을
물려받는다 — 예: 감자 그룹에서 '삶기' 실측치가 먼저 나오면 '생것'도 그
값을 받아버렸다. 도너를 (그룹, 조리법) 조합으로 좁혀서, 조리법이 같은
실측치가 없으면 상속하지 않고 none 으로 남긴다(규칙 3 으로 넘어감).
"""

import csv
from pathlib import Path


def load_gi_map(path: Path) -> dict[str, float]:
    if not path.exists():
        return {}
    table: dict[str, float] = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            key = (row.get("key") or "").strip()
            if not key:
                continue
            try:
                table[key] = float(row["gi"])
            except (KeyError, TypeError, ValueError):
                raise SystemExit(f"gi_map.csv 의 GI 값이 숫자가 아닙니다: {row}")
    return table


def apply_gi(records, gi_map_path: Path) -> dict[str, int]:
    table = load_gi_map(gi_map_path)
    stats = {"실측": 0, "추정": 0, "없음": 0}

    # 1단계 — 정확 매칭
    for r in records:
        keys = []
        if r.rep_name and r.method:
            keys.append(f"{r.rep_name} {r.method}")
        if r.rep_name:
            keys.append(r.rep_name)
        keys.append(r.name)

        for key in keys:
            if key in table:
                r.gi_value, r.gi_kind, r.gi_basis = table[key], "measured", None
                stats["실측"] += 1
                break

    # 2단계 — 같은 그룹 + 같은 조리법 안에서만 상속.
    # 조리법이 GI 를 크게 바꾸므로, 도너를 (그룹, 조리법) 조합으로 좁힌다.
    # 같은 조리법의 실측치가 없으면 상속하지 않고 규칙 3(영양성분 판정)에
    # 맡긴다 — 근거 없는 추정보다 그게 안전하다.
    donors: dict[tuple[str, str | None], tuple[float, str]] = {}
    for r in records:
        if r.gi_kind == "measured" and r.group:
            donors.setdefault((r.group, r.method), (r.gi_value, r.display or r.name))

    for r in records:
        if r.gi_kind == "measured":
            continue
        key = (r.group, r.method) if r.group else None
        if key and key in donors:
            value, source_name = donors[key]
            r.gi_value, r.gi_kind, r.gi_basis = value, "estimated", f"{source_name} 기준"
            stats["추정"] += 1
        else:
            r.gi_value, r.gi_kind, r.gi_basis = None, "none", None
            stats["없음"] += 1

    return stats


if __name__ == "__main__":
    from group import apply_groups
    from normalize import load_records

    base = Path(__file__).resolve().parent
    recs, _ = load_records(base / "raw", base / "data" / "category_allow.csv")
    apply_groups(recs, base / "data" / "food_group.csv")
    stats = apply_gi(recs, base / "data" / "gi_map.csv")

    total = sum(stats.values())
    print(f"총 {total:,}건")
    for k, v in stats.items():
        print(f"  {k}: {v:,} ({v / total * 100:.1f}%)")

    print("\n[실측 GI 샘플 20건]")
    shown = 0
    for r in recs:
        if r.gi_kind == "measured":
            print(f"  {r.display or r.name}  GI {r.gi_value:g}")
            shown += 1
            if shown >= 20:
                break
