"""원본 CSV → FoodRecord 공통 레코드. 여기서 품목을 추린다.

주의 세 가지 (실제 데이터에서 확인됨):
  1. UTF-8 BOM 이 있다 → encoding="utf-8-sig"
  2. 따옴표 안에 쉼표가 든 행이 있다 → csv.DictReader 필수, split(",") 금지
  3. '_' 는 조리법 구분자다 ('고구마_찐것'). 브랜드 표시가 아니므로 걸러내면 안 된다
"""

import csv
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from score import Nutrients

SOURCE_FILES = ("원재료성_농진청.csv", "원재료성_수과원.csv", "음식.csv")

COL = {
    "name": "식품명",
    "rep": "대표식품명",
    "category": "식품대분류명",
    "basis": "영양성분함량기준량",
    "kcal": "에너지(kcal)",
    "carb": "탄수화물(g)",
    "sugar": "당류(g)",
    "fiber": "식이섬유(g)",
    "fat": "지방(g)",
    "sodium": "나트륨(mg)",
}

# 실제 1인분 중량. 음식.csv 에만 있고(19,483/19,495행 값 있음) 원재료성 두 파일(53컬럼)엔
# 없다 — 그래서 COL 에 넣지 않고 파일별로 있으면만 쓰는 선택적 컬럼으로 다룬다.
# 영양성분 수치 자체는 이 값으로 환산하지 않는다(여전히 100g/100ml 기준 그대로) —
# serving_label 표시 문구만 실제 중량으로 바꿔치기한다.
WEIGHT_COL = "식품중량"

# 프랜차이즈 메뉴 표식. '커피_흑임자카페 라떼 핫(HOT) (R)' 같은 것들.
# 어느 카테고리에서든 적용 — 사이즈/온도/포장 표기는 원재료성 식품엔 절대 안 나온다.
FRANCHISE_MARKERS = [
    re.compile(r"\((HOT|ICED|R|L|G|S|M|XL|Tall|Grande|Venti|Max|Regular|Large|Small)\)", re.I),
    re.compile(r"\(Mini[^)]*\)", re.I),
    re.compile(r"\(\d+\s*(개입|조각|잔|팩|인분)\)"),
]

# 영문 브랜드명 표식. cap>0 카테고리(프랜차이즈가 몰린 빵·음료·유제품)에만 적용한다 —
# '파프리카(착색단고추)_Raon yellow(미니파프리카)_노란색_생것' 처럼 채소류 품종명에
# 영문이 섞이는 경우가 있어 전체 카테고리에 걸면 정상 품목을 오탐한다.
FRANCHISE_MARKERS_CAPPED_ONLY = [
    re.compile(r"[A-Za-z]{4,}"),
]

# 대분류명이 깨진 행 (수과원 파일의 '11', '12' 등)
BROKEN_CATEGORY = re.compile(r"^\s*\d+\s*$")


@dataclass
class FoodRecord:
    id: str
    name: str                      # 원본 표기 '고구마_찐것'
    display: str | None            # 화면용 — Task 4 가 채운다
    category: str                  # 화면 카테고리 7종
    rep_name: str                  # 원본 대표식품명
    serving_label: str             # '100g 기준'
    nutrients: Nutrients
    serving_grams: float | None = None   # 1회 분량 실제 중량(g). ml 은 1ml=1g 근사. 모르면 None
    group: str | None = None
    method: str | None = None
    gi_value: float | None = None
    gi_kind: str = "none"
    gi_basis: str | None = None
    alias: list[str] = field(default_factory=list)
    source: str | None = None   # None = 원본 CSV, 문자열 = 보충 레코드 출처
    caution: str | None = None  # 표시용 주의 문구. 신호등 등급은 바꾸지 않는다


def _num(value) -> float | None:
    """빈 문자열은 결측이므로 None. 명시적 결측 표기('-' 등)만 0.0 으로 본다.

    실측 데이터에는 빈 문자열만 나타나고 '해당없음' 류는 한 건도 없었지만,
    나중 갱신에서 나타날 수 있어 방어적으로 남겨둔다.
    """
    text = str(value or "").strip().replace(",", "")
    if text == "":
        return None
    if text in ("-", "N/A", "Tr", "tr", "해당없음"):
        return 0.0
    try:
        return float(text)
    except ValueError:
        return None


def _clean(name: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(name or "")).strip())


_WEIGHT_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*(g|ml)\s*$", re.I)


def _weight_label(raw: str) -> str | None:
    """'식품중량' 원본 값을 표시용 문구로 바꾼다. 형식이 아니면 None(호출부가 기본값 사용)."""
    m = _WEIGHT_RE.match(str(raw or ""))
    if not m:
        return None
    num, unit = m.groups()
    value = round(float(num))
    return f"{value}{unit.lower()}"


def _weight_grams(raw: str) -> float | None:
    """'식품중량' 원본 값에서 그램(밀리리터) 수치만 뽑는다. 형식이 아니면 None.

    ml 은 밀도를 몰라 1ml=1g 으로 근사한다 — 대부분 국·음료라 오차가 작다는
    가정이다. bundle.py 의 per_serving() 도 같은 가정을 쓴다.
    """
    m = _WEIGHT_RE.match(str(raw or ""))
    if not m:
        return None
    num, _unit = m.groups()
    return round(float(num))


def _is_franchise(name: str, *, capped: bool) -> bool:
    markers = FRANCHISE_MARKERS + FRANCHISE_MARKERS_CAPPED_ONLY if capped else FRANCHISE_MARKERS
    return any(p.search(name) for p in markers)


def load_allow(path: Path) -> dict[str, tuple[str, int]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {r["category"].strip(): (r["label"].strip(), int(r["cap"]))
                for r in csv.DictReader(f)}


def load_name_corrections(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {r["original"]: r["corrected"] for r in csv.DictReader(f) if r.get("original")}


def load_category_overrides(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {r["rep_name"]: r["category"] for r in csv.DictReader(f) if r.get("rep_name")}


def load_item_category_overrides(path: Path) -> dict[str, str]:
    """대표식품명 하나에 서로 다른 부위(씨앗/열매 vs 잎)가 섞여 있어
    대표식품명 단위 override 로는 못 잡는 경우, 식품명 단위로 강제 지정한다."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {r["name"]: r["category"] for r in csv.DictReader(f) if r.get("name")}


def load_extra_foods(path: Path, allow_labels: set[str]) -> list[FoodRecord]:
    """사람이 손으로 채운 보충 레코드. 원본 CSV 에 없는 음식을 메운다."""
    if not path.exists():
        return []

    out = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for lineno, row in enumerate(csv.DictReader(f), start=2):
            name = _clean(row.get("name"))
            if not name:
                continue
            if not (row.get("source") or "").strip():
                raise SystemExit(f"extra_foods.csv:{lineno} '{name}' 에 source 가 없습니다")

            category = _clean(row.get("category"))
            if category not in allow_labels:
                raise SystemExit(
                    f"extra_foods.csv:{lineno} '{name}' 의 카테고리 '{category}' 는 "
                    f"허용 목록에 없습니다: {sorted(allow_labels)}"
                )

            def num(key: str) -> float:
                value = _num(row.get(key))
                if value is None:
                    raise SystemExit(f"extra_foods.csv:{lineno} '{name}' 의 {key} 가 비어 있습니다")
                return value

            # 나트륨은 필수가 아니다 — 원본에 없으면 None(모름). 0으로 채우지 않는다.
            # 탄수화물을 0으로 채워 허위 초록을 만들었던 실수(Task 3)와 같은 종류의
            # 실수를 나트륨에서 반복하지 않는다. 0과 모름은 다르다.
            sodium = _num(row.get("sodium"))

            out.append(FoodRecord(
                id=re.sub(r"[^0-9A-Za-z가-힣+]+", "-", name).strip("-"),
                name=name,
                display=None,
                category=category,
                rep_name=_clean(row.get("rep_name")) or name,
                serving_label=_clean(row.get("serving_label")) or "100g 기준",
                nutrients=Nutrients(
                    kcal=num("kcal"), carb=num("carb"), sugar=num("sugar"),
                    fiber=num("fiber"), fat=num("fat"), sodium=sodium,
                ),
                method=_clean(row.get("method")) or None,
                source=_clean(row.get("source")),
            ))
    return out


def load_caution(path: Path) -> dict[str, str]:
    """표시용 주의 문구. key 는 대표식품명 또는 식품명과 일치시킨다(조리법 키는 없음).

    신호등 등급과는 무관한 표시 전용 장치 — 등급 규칙(score.py)은 절대 건드리지 않는다.
    """
    if not path.exists():
        return {}
    table: dict[str, str] = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        for lineno, row in enumerate(csv.DictReader(f), start=2):
            key = _clean(row.get("key"))
            if not key:
                continue
            if not (row.get("source") or "").strip():
                raise SystemExit(f"caution.csv:{lineno} '{key}' 에 source 가 없습니다")
            caution = _clean(row.get("caution"))
            if not caution:
                raise SystemExit(f"caution.csv:{lineno} '{key}' 에 caution 문구가 없습니다")
            table[key] = caution
    return table


def apply_caution(records: list, path: Path) -> int:
    """모든 처리가 끝난 뒤(보충 레코드 적재 이후) 호출한다. 적용 건수를 반환한다."""
    table = load_caution(path)
    if not table:
        return 0
    applied = 0
    for r in records:
        caution = table.get(r.rep_name) or table.get(r.name)
        if caution:
            r.caution = caution
            applied += 1
    return applied


def load_records(raw_dir: Path, allow_path: Path):
    allow = load_allow(allow_path)
    name_fix = load_name_corrections(allow_path.parent / "name_correction.csv")
    cat_override = load_category_overrides(allow_path.parent / "category_override.csv")
    item_override = load_item_category_overrides(allow_path.parent / "category_override_item.csv")
    stats = dict.fromkeys(
        ("총건수", "카테고리제외", "상품명제외", "프랜차이즈제외",
         "영양성분누락", "중복제외", "남은건수", "이름정정", "카테고리정정", "보충", "주의문구"), 0)

    kept, seen = [], set()
    capped: dict[tuple[str, str], list] = defaultdict(list)
    cap_for: dict[tuple[str, str], int] = {}

    for filename in SOURCE_FILES:
        path = raw_dir / filename
        if not path.exists():
            raise SystemExit(f"원본이 없습니다: {path}")

        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            missing = [c for c in COL.values() if c not in (reader.fieldnames or [])]
            if missing:
                raise SystemExit(f"{filename} 에 컬럼이 없습니다: {missing}\n"
                                 f"실제 헤더: {reader.fieldnames}")
            has_weight_col = WEIGHT_COL in (reader.fieldnames or [])

            for row in reader:
                stats["총건수"] += 1

                raw_cat = _clean(row[COL["category"]])
                if BROKEN_CATEGORY.match(raw_cat) or raw_cat not in allow:
                    stats["카테고리제외"] += 1
                    continue
                label, cap = allow[raw_cat]

                name = _clean(row[COL["name"]])
                if name in name_fix:
                    name = name_fix[name]
                    stats["이름정정"] += 1
                if not name:
                    stats["상품명제외"] += 1
                    continue
                if _is_franchise(name, capped=cap > 0):
                    stats["프랜차이즈제외"] += 1
                    continue

                values = {k: _num(row[COL[k]])
                          for k in ("kcal", "carb", "sugar", "fiber", "fat", "sodium")}
                # 탄수화물·열량 둘 중 하나라도 없으면 판정 자체가 불가능하니 제외한다.
                # (당류·식이섬유·지방은 없으면 0으로 채워도 판정에 지장 없음.
                #  나트륨은 판정에 아예 쓰이지 않으므로 0으로 채우지 않고 None(모름)으로
                #  둔다 — 탄수화물을 0으로 채워 허위 초록을 만들던 실수와 같은 종류를
                #  반복하지 않는다)
                if values["carb"] is None or values["kcal"] is None:
                    stats["영양성분누락"] += 1
                    continue

                # '+' 는 남긴다 — 한우 등급 표기(1+등급/1++등급)가 이걸로만 구분된다.
                # 지우면 서로 다른 두 식품이 같은 id로 충돌해 하나가 사라진다.
                food_id = re.sub(r"[^0-9A-Za-z가-힣+]+", "-", name).strip("-")
                if not food_id or food_id in seen:
                    stats["중복제외"] += 1
                    continue
                seen.add(food_id)

                basis = _clean(row[COL["basis"]]) or "100g"
                unit = "100ml" if "ml" in basis.lower() else "100g"

                # 실제 1인분 중량이 있으면(음식.csv 만 해당) 그걸 표시하고, 없으면
                # 기존대로 '100g/100ml 기준'. 영양성분 수치는 어느 쪽이든 100g/100ml
                # 그대로다 — 여기서 환산하지 않는다.
                serving_label = f"{unit} 기준"
                serving_grams = None
                if has_weight_col:
                    raw_weight = row.get(WEIGHT_COL, "")
                    weight_label = _weight_label(raw_weight)
                    if weight_label:
                        serving_label = weight_label
                        serving_grams = _weight_grams(raw_weight)

                record = FoodRecord(
                    id=food_id,
                    name=name,
                    display=None,
                    category=label,
                    rep_name=_clean(row[COL["rep"]]) or name,
                    serving_label=serving_label,
                    serving_grams=serving_grams,
                    nutrients=Nutrients(
                        kcal=round(values["kcal"], 1), carb=round(values["carb"], 1),
                        sugar=round(values["sugar"] or 0, 1),
                        fiber=round(values["fiber"] or 0, 1),
                        fat=round(values["fat"] or 0, 1),
                        sodium=None if values["sodium"] is None else round(values["sodium"], 1),
                    ),
                )

                if cap > 0:
                    key = (label, record.rep_name)
                    capped[key].append(record)
                    cap_for[key] = cap
                else:
                    kept.append(record)

    # 상한이 걸린 카테고리는 대표식품명마다 이름이 짧은 것부터 cap 개만 남긴다.
    # (cap 은 그 레코드가 속했던 원본 대분류의 값을 그대로 쓴다 — 같은 화면
    #  카테고리 라벨을 공유하는 다른 원본 대분류의 cap=0 과 섞이면 안 된다)
    for key, items in capped.items():
        cap = cap_for[key]
        items.sort(key=lambda r: (len(r.name), r.name))
        kept.extend(items[:cap])
        stats["프랜차이즈제외"] += max(0, len(items) - cap)

    # 같은 대표식품명 안에서 카테고리가 갈리면 다수를 따른다.
    # 원본 식품대분류명이 행마다 흔들리는 것을 바로잡는다.
    by_rep: dict[str, list] = defaultdict(list)
    for r in kept:
        by_rep[r.rep_name].append(r)

    for rep, items in by_rep.items():
        counts = Counter(r.category for r in items)
        if len(counts) > 1:
            winner = counts.most_common(1)[0][0]
            for r in items:
                if r.category != winner:
                    r.category = winner
                    stats["카테고리정정"] += 1

    # 수동 지정이 다수결보다 우선한다.
    for r in kept:
        if r.rep_name in cat_override:
            target = cat_override[r.rep_name]
            if r.category != target:
                r.category = target
                stats["카테고리정정"] += 1

    # 개별 식품명 지정이 대표식품명 지정보다 우선한다.
    # (같은 대표식품명 안에 씨앗/열매와 잎이 섞여 있어 대표식품명 단위로는 못 잡는 경우)
    for r in kept:
        if r.name in item_override:
            target = item_override[r.name]
            if r.category != target:
                r.category = target
                stats["카테고리정정"] += 1

    # 보충 레코드는 사람이 카테고리를 명시했으므로 다수결 대상이 아니다.
    extras = load_extra_foods(allow_path.parent / "extra_foods.csv",
                              {label for label, _cap in allow.values()})
    existing = {r.id for r in kept}
    for r in extras:
        if r.id in existing:
            stats["중복제외"] += 1
            continue
        kept.append(r)
        stats["보충"] += 1

    # 표시용 주의 문구. 신호등 등급을 매기는 규칙(score.py)이 전부 끝난 뒤에만 붙인다 —
    # 이 값은 화면 표시 전용이며 어떤 판정 로직에도 입력으로 쓰이지 않는다.
    stats["주의문구"] = apply_caution(kept, allow_path.parent / "caution.csv")

    stats["남은건수"] = len(kept)
    return kept, stats


if __name__ == "__main__":
    base = Path(__file__).resolve().parent
    recs, stats = load_records(base / "raw", base / "data" / "category_allow.csv")
    for k, v in stats.items():
        print(f"{k:>10}: {v:,}")
    print("\n[카테고리별]")
    by_cat: dict[str, int] = {}
    for r in recs:
        by_cat[r.category] = by_cat.get(r.category, 0) + 1
    for k, v in sorted(by_cat.items(), key=lambda kv: -kv[1]):
        print(f"  {k:>10}: {v:,}")
    print("\n[샘플 12건]")
    for r in recs[:12]:
        print(f"  {r.name} | {r.category} | 대표={r.rep_name} | {r.serving_label} | {r.nutrients}")
