"""조리법 뽑아내기와 화면용 이름 만들기.

그룹 자체는 원본의 `대표식품명`(FoodRecord.rep_name)을 그대로 쓴다.
'고구마_찐것' 의 대표식품명이 이미 '고구마' 이므로 추측할 것이 없다.
"""

import csv
import re
from pathlib import Path

# 원본 식품명에 나타나는 조리법 표기 → 우리 표기.
# 목록 순서는 우선순위와 무관하다 — _find_method 가 이름에서 가장 나중에
# 나오는(rfind) 표기를 최종 공정으로 고른다. 순서는 그냥 가독성용.
METHOD_WORDS = [
    ("말린것", "말리기"), ("건조", "말리기"),
    ("삶은것", "삶기"), ("데친것", "데치기"),
    ("찐것", "찌기"), ("구운것", "굽기"), ("볶은것", "볶기"),
    ("튀긴것", "튀기기"), ("절인것", "절이기"), ("훈제", "훈제"),
    # Step 3 검수 추가: 원본에 자주 나오지만 놓치고 있던 표기.
    # '분말화한것' 은 밀·보리·멥쌀 등 곡류 그룹에서 100건 이상 빠져 있었고,
    # '착즙' 은 귤/오렌지/자몽처럼 통과일과 혈당 반응이 크게 달라 이 앱의
    # 핵심 메시지("같은 재료라도 이렇게 드세요")에 직결된다.
    ("분말화한것", "가루"), ("착즙", "착즙"),
    # 리뷰 반영: '말린것을 불린것'(무말랭이) 처럼 마른 것을 다시 물에 불린
    # 최종 상태. '말린것' 하나로만 잡히면 완전히 다른 식감/수분 상태를
    # 놓친다.
    ("불린것", "불리기"),
    ("생것", "생것"), ("날것", "생것"),
]

METHOD_PREFIX = {
    "삶기": "삶은", "찌기": "찐", "굽기": "구운", "볶기": "볶은",
    "튀기기": "튀긴", "말리기": "말린", "데치기": "데친",
    "절이기": "절인", "훈제": "훈제", "생것": "생",
    "가루": "가루낸", "착즙": "착즙한", "불리기": "불린",
}

# _find_method 에서 '가장 나중에 나오는 조리법' 을 고를 때 쓰는 표기 집합.
# _readable/simple 판정에서도 '두 번째 조각이 조리법 표기와 정확히
# 일치하는지' 검사할 때 재사용한다 (리뷰 Critical 2).
METHOD_TOKENS = {word for word, _ in METHOD_WORDS}


def load_manual(path: Path) -> dict[str, tuple[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {r["name"]: (r["group"], r["method"])
                for r in csv.DictReader(f) if r.get("name")}


def _find_method(name: str) -> str | None:
    """이름에 여러 조리법이 나오면 가장 뒤에 있는 것이 최종 공정이다.

    '말린것을 삶은것' → 삶기 (말려서 보관했다가 삶아 먹는 것).
    같은 위치에서 표기 길이가 다르면(예: 겹치는 경우) 더 긴 표기를 우선한다.
    """
    best_pos, best_len, best_method = -1, -1, None
    for word, method in METHOD_WORDS:
        pos = name.rfind(word)
        if pos < 0:
            continue
        if pos > best_pos or (pos == best_pos and len(word) > best_len):
            best_pos, best_len, best_method = pos, len(word), method
    return best_method


def _readable(name: str) -> str:
    """원본 표기를 사람이 읽을 수 있게. '_' 는 공백으로."""
    return re.sub(r"\s+", " ", name.replace("_", " ")).strip()


def apply_groups(records, map_path: Path) -> dict[str, int]:
    manual = load_manual(map_path)
    stats = dict.fromkeys(("조리법있음", "조리법없음", "수동", "단독그룹해제"), 0)

    for r in records:
        if r.name in manual:
            r.group, r.method = manual[r.name]
            stats["수동"] += 1
        else:
            r.group = r.rep_name
            r.method = _find_method(r.name)
            stats["조리법있음" if r.method else "조리법없음"] += 1

        # 화면용 이름.
        #   '고구마_찐것' (대표식품명 + 조리법뿐) → '찐 고구마'
        #   '소고기_수입산(미국산)_설도_구운것(석쇠)' → 정보가 많으므로 원본을 읽기 좋게만
        prefix = METHOD_PREFIX.get(r.method) if r.method else None
        parts = [p for p in r.name.split("_") if p]
        # 리뷰 Critical 2: 두 번째 조각이 조리법 표기를 '포함'하는 것만으로는
        # 부족하다 — '당류에 절인것' 처럼 수식어가 붙은 조각을 '절인것'과
        # 같다고 보면 수식어(당류/소금 등, 당뇨 앱에서 제일 중요한 정보)가
        # display 에서 통째로 사라진다. 정확히 일치할 때만 simple 로 본다.
        simple = (len(parts) == 2 and parts[0] == r.group
                  and parts[1].strip() in METHOD_TOKENS)

        if prefix and simple:
            r.display = f"{prefix} {r.group}"
            r.alias.append(f"{prefix}{r.group}")
        else:
            r.display = _readable(r.name)
            if prefix:
                r.alias.append(f"{prefix}{r.group}")

    # 항목이 하나뿐인 그룹은 조리법 비교가 의미 없다 → 그룹만 해제.
    # display 는 그대로 둔다 ('찐 고구마' 는 그룹과 무관하게 좋은 이름이다).
    counts: dict[str, int] = {}
    for r in records:
        if r.group:
            counts[r.group] = counts.get(r.group, 0) + 1
    for r in records:
        if r.group and counts[r.group] < 2:
            r.group = None
            stats["단독그룹해제"] += 1

    return stats


if __name__ == "__main__":
    from normalize import load_records

    base = Path(__file__).resolve().parent
    recs, _ = load_records(base / "raw", base / "data" / "category_allow.csv")
    stats = apply_groups(recs, base / "data" / "food_group.csv")
    for k, v in stats.items():
        print(f"{k:>12}: {v:,}")

    groups: dict[str, list] = {}
    for r in recs:
        if r.group:
            groups.setdefault(r.group, []).append(r)

    print(f"\n그룹 수: {len(groups):,}")
    print("\n[항목이 많은 그룹 12개]")
    for name, items in sorted(groups.items(), key=lambda kv: -len(kv[1]))[:12]:
        methods = sorted({i.method or "-" for i in items})
        print(f"  {name} ({len(items)}건): {', '.join(methods)}")

    print("\n[display 샘플 15건]")
    for r in recs[:15]:
        print(f"  {r.name}  ->  {r.display}   (그룹={r.group}, 조리법={r.method})")
