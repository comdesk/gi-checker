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

# 같은 식물·같은 생선이라도 부위가 다르면 전혀 다른 음식이다.
# 조리법 비교는 같은 부위끼리만 의미가 있다.
#
# Task 11B 에서는 '알'·'내장' 을 뺐다 — "굴 내장이나 생선 알은 함께 먹는 부위라
# 분리가 오히려 어색하다" 는 판단이었다. 데이터를 보니 그 판단이 틀렸다.
# 원본은 이것들을 **따로 측정한 별개 항목**으로 싣고 있고, 값이 크게 다르다:
#   달걀   난백 탄수 0.1g  vs  난황 5.8g
#   명태   육   탄수 0.0g  vs  알 29.2g
#   치커리 잎(적치콘) 2.5g  vs  뿌리 17.5g
# 함께 먹는지 여부는 우리가 정할 일이 아니다. 따로 재어 놓은 것을 한 그룹에
# 넣으면 조리법 비교가 부위 비교로 바뀐다.
PART_MARKERS = (
    "줄기", "잎", "순", "싹", "뿌리",          # 식물
    "육", "알", "내장", "난백", "난황", "관자", "전체",  # 동물성
)

# 세그먼트가 부위 표시와 '정확히' 일치할 때만 잡는다('_줄기_', '_잎_' 처럼
# 밑줄 사이에 있을 때). 괄호 설명은 붙어도 된다 — '줄기(껍질 포함)' 도 줄기다.
#
# 이렇게 세그먼트 단위·정확 일치로 좁힌 이유: '순'·'싹' 은 짧아서 다른 단어에
# 걸리기 쉽다. 실제 데이터를 세그먼트 단위로 훑어본 결과(Step 1 검수):
#   '순' 이 들어간 세그먼트 65건 중 부위 표시로 걸리는 건 21건뿐이었다.
#   '순대'('순대_간편조리세트_…', '오징어순대' 등, 부위와 무관한 순대 요리)와
#   '순두부'('순두부찌개_해물' 등)·'순 현미밥'(품종/가공과 무관한 '순수'의 뜻)이
#   나머지 44건을 차지했는데, 이들은 전부 밑줄로 구분된 세그먼트 전체가 '순'과
#   일치하지 않아(예: '순두부찌개' != '순') 애초에 걸리지 않았다. 같은 이유로
#   '싹'도 오탐 없이 10건만 정확히 걸렸다('메밀_싹_생것' 등).
PART_PATTERN = {m: re.compile(rf"^{re.escape(m)}(\(.*\))?$") for m in PART_MARKERS}


def _find_part(name: str) -> str | None:
    """이름의 밑줄 세그먼트 중 부위 표시가 정확히 있으면 그 부위를 돌려준다.

    '어린잎'·'잎새버섯'·'잎줄기'처럼 다른 글자에 붙어 있으면 잡지 않는다(오탐 방지).
    첫 세그먼트(대표식품명 자리)도 포함해 전부 검사한다 — 부위 표시가 항상
    같은 위치에 오지 않는다('두릅_땅두릅_잎_생것'처럼 품종 다음에 오기도 한다).
    """
    for part in (p.strip() for p in name.split("_") if p.strip()):
        for marker, pattern in PART_PATTERN.items():
            if pattern.match(part):
                return marker
    return None


def load_species_split(path: Path) -> dict[str, set[str]]:
    """대표식품명 아래에 사실 서로 다른 음식이 묶여 있는 경우의 분리 목록.

    '호박' 안에 애호박·단호박·쥬키니가 함께 있으면 조리법 비교가 채소 비교로
    바뀐다("삶으면 좋고 찌면 주의" = 쥬키니 vs 단호박). 품종(감자 대지·수미)은
    답이 같아 합쳐도 되지만 이것들은 가게에서 따로 파는 다른 음식이다.

    영양성분 편차만으로는 이 둘을 가를 수 없다 — 경계선에서 흔들리는 같은
    음식과 구분이 안 된다. 사람이 판단해 적는다.
    """
    if not path.exists():
        return {}
    out: dict[str, set[str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        for lineno, row in enumerate(csv.DictReader(f), start=2):
            rep, marker = (row.get("rep_name") or "").strip(), (row.get("marker") or "").strip()
            if not rep:
                continue
            if not marker:
                raise SystemExit(f"species_split.csv:{lineno} '{rep}' 의 marker 가 비었습니다")
            if not (row.get("note") or "").strip():
                raise SystemExit(f"species_split.csv:{lineno} '{rep}' 에 근거(note)가 없습니다")
            out.setdefault(rep, set()).add(marker)
    return out


def _find_species(name: str, rep_name: str, splits: dict[str, set[str]]) -> str | None:
    markers = splits.get(rep_name)
    if not markers:
        return None
    for part in (p.strip() for p in name.split("_")):
        if part in markers:
            return part
    return None


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
    splits = load_species_split(map_path.parent / "species_split.csv")
    stats = dict.fromkeys(
        ("조리법있음", "조리법없음", "수동", "단독그룹해제", "부위분리", "종분리"), 0)

    # 화면에 쓸 그룹 이름. 그룹 키와 다를 수 있다 —
    # 키 '호박 단호박' 은 다른 그룹과 겹치지 않기 위한 것이고,
    # 사람이 부르는 이름은 그냥 '단호박' 이다.
    labels: dict[int, str] = {}

    for r in records:
        if r.name in manual:
            # 수동 지정은 사람이 이미 판단을 끝낸 예외다 — 부위 분리로 다시
            # 건드리지 않는다(현재 두 항목 다 부위 표시가 없어 영향은 없지만,
            # 수동 지정의 우선순위를 지킨다는 원칙을 코드로도 지킨다).
            r.group, r.method = manual[r.name]
            stats["수동"] += 1
        else:
            r.group = r.rep_name
            r.method = _find_method(r.name)
            stats["조리법있음" if r.method else "조리법없음"] += 1

            # 종 분리를 부위 분리보다 먼저 — '호박 단호박 잎' 처럼 겹칠 때
            # 종이 앞에 와야 읽힌다.
            species = _find_species(r.name, r.rep_name, splits)
            if species:
                r.group = f"{r.group} {species}"
                # 분리된 종은 그 자체로 사람이 쓰는 이름이다 ('단호박', '백미').
                # '데친 호박 단호박' 이 아니라 '데친 단호박' 이라고 해야 읽힌다.
                labels[id(r)] = species
                stats["종분리"] += 1

            part = _find_part(r.name)
            if part:
                r.group = f"{r.group} {part}"
                # 부위는 홀로 서지 못한다 — '데친 잎' 이 아니라 '데친 호박 잎'.
                labels[id(r)] = f"{labels.get(id(r), r.rep_name)} {part}"
                stats["부위분리"] += 1

        # 화면용 이름.
        #   '고구마_찐것' (대표식품명 + 조리법뿐) → '찐 고구마'
        #   '소고기_수입산(미국산)_설도_구운것(석쇠)' → 정보가 많으므로 원본을 읽기 좋게만
        prefix = METHOD_PREFIX.get(r.method) if r.method else None
        parts = [p for p in r.name.split("_") if p]
        # 리뷰 Critical 2: 두 번째 조각이 조리법 표기를 '포함'하는 것만으로는
        # 부족하다 — '당류에 절인것' 처럼 수식어가 붙은 조각을 '절인것'과
        # 같다고 보면 수식어(당류/소금 등, 당뇨 앱에서 제일 중요한 정보)가
        # display 에서 통째로 사라진다. 정확히 일치할 때만 simple 로 본다.
        #
        # 종·부위로 갈린 그룹은 이름이 여러 토막이다('호박_단호박_데친것' →
        # 그룹 '호박 단호박'). 조리법을 뺀 나머지가 그룹과 정확히 같으면
        # 그때도 단순형으로 본다.
        label = labels.get(id(r), r.group)
        r.group_label = label
        simple = (len(parts) >= 2 and " ".join(parts[:-1]) == r.group
                  and parts[-1].strip() in METHOD_TOKENS)

        if prefix and simple:
            r.display = f"{prefix} {label}"
            r.alias.append(f"{prefix}{label}")
        else:
            r.display = _readable(r.name)
            if prefix:
                r.alias.append(f"{prefix}{label}")

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
