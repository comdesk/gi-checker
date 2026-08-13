"""식품교환표 1교환단위량 붙이기 — '한 번에 이만큼' 을 말해주기 위한 것.

이 앱은 지금까지 '먹어도 되나' 만 답했다. 당뇨에서는 그것만으로 부족하다.
사과가 초록이라고 세 개를 드시면 초록인 의미가 없기 때문이다.

주의 — 1교환단위는 판정에 쓰면 안 된다.
  1교환단위는 '한 번에 먹는 양' 이 아니라 '탄수화물이 12g(과일군)이 되는 양'
  이다. 정의부터가 영양소 기준이다. 이것을 규칙 4(양)에 넣으면
      GL = GI x 탄수화물 / 100 = GI x 12 / 100
  이 되어 GI 가 80 인 과일도 GL 9.6 으로 초록 기준(10) 안에 들어온다.
  모든 과일이 예외 없이 통과하므로 규칙 4 가 아무 일도 하지 않게 된다.
  그래서 이 값은 화면에 표시만 하고 score.py 로 넘기지 않는다.

출처와 옮기지 않은 항목의 이유는 data/exchange.csv 머리말에 적어두었다.
"""

import csv
from pathlib import Path

# 분량 밑에 붙는 한 줄. 식품군마다 하고 싶은 말이 다르다.
#
# 과일군·우유군은 하루 횟수를 말한다. 학회의 열량별 교환단위수 배분표
# (1,500 / 1,800 / 2,100 kcal, 식단안 3종)에서 세 안이 모두 같은 범위를
# 주기 때문이다 — 과일군 1~2, 우유군 합계 1~2.
# 곡류군은 5~11 로 안마다 크게 달라 하루 횟수를 말하지 않는다. 범위가
# 그만큼 넓으면 알려주는 것이 아니라 헷갈리게 하는 것이다.
#
# 채소군은 횟수 대신 지침의 말을 그대로 옮긴다. 4판 고려사항이
# "대부분의 채소류는 에너지가 비교적 적고 식이섬유가 많으므로 충분히
# 섭취하도록 식사를 계획한다" 고 한다. 분량만 덩그러니 띄우면 없는 제한을
# 만드는 셈이라, 마음껏 드셔도 된다는 말을 같이 해야 한다.
ADVICE = {
    "과일군": "하루 1~2번",
    "우유군": "하루 1~2번",
    "채소군": "채소는 충분히 드셔도 좋습니다",
    # 4판 고려사항: "지방군에 속한 모든 식품은 소량의 섭취로도 높은 에너지를
    # 내므로, 적정 체중을 유지하기 위해서는 과량 섭취하지 않도록 한다."
    # 견과류는 몸에 좋다고 알려져 한 줌씩 드시기 쉬운데 1교환단위가 8g 이다.
    "지방군": "적은 양으로도 열량이 높습니다",
}

# 어육류군은 한 줄 조언을 두지 않는다. 지침이 하려는 말은 "고지방보다
# 저지방·중지방을 고르라" 인데, 우리 데이터는 삼겹살과 안심이 같은 '돼지고기'
# 그룹에 있어 그룹 단위로는 그 구분을 말할 수 없다. 지방 함량은 아래
# 영양성분표에 이미 나온다.

# 4판이 따로 짚은 것 — "1교환단위당 탄수화물 5g 이상인 채소는 탄수화물의
# 제한이 필요한 경우 과잉섭취는 주의하여야 한다". 해당 줄은 csv 의 advice
# 칸으로 이 문구를 덮어쓴다.
ADVICE_HIGH_CARB_VEGETABLE = "탄수화물이 있는 편이라 과하지 않게"


def _read_rows(path: Path) -> list[str]:
    """'#' 로 시작하는 줄은 주석이다. csv 모듈은 주석을 모르므로 미리 걸러낸다."""
    if not path.exists():
        return []
    return [ln for ln in path.read_text(encoding="utf-8-sig").splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]


# 1교환단위당 식이섬유 2.5g 이상. 지침이 곡류군에서 "식이섬유 함량이 높은
# 통곡물을 우선하여 선택한다" 고 하는 그 기준이다. 같은 값이면 이쪽이 낫다는
# 뜻이라 화면에 표를 붙인다.
#
# 표를 붙이는 조건은 두 가지를 **모두** 만족할 때다.
#   1) 지침의 목록에 있다 (data/fiber_rich.csv)
#   2) 그 레코드의 실측 식이섬유로 계산해도 2.5g 이상이다
#
# 처음엔 1번만 봤는데, 화면에 나가는 103건 중 37건이 바로 아래 영양성분표와
# 어긋났다 — '식이섬유가 많은 편입니다' 위에 표에는 '식이섬유 1.3g' 이 적히는
# 식이다. 지침은 다른 데이터베이스(FANTASY)를 쓰고 품종도 하나로 정해 싣기
# 때문에(예: 사과는 부사 기준) 우리 품종별 값과 갈린다.
#
# 어느 쪽이 맞는지 우리가 판단할 근거가 없다. 그래서 둘이 같은 말을 할 때만
# 붙인다. 표가 덜 붙는 것은 손해가 작지만, 화면이 스스로와 모순되는 것은
# 사용자가 앱을 못 믿게 만든다.
#
# 추정치로는 붙이지 않는다. 표는 '이쪽이 낫다'는 적극적인 권장이라
# 물려받은 값에 기대면 안 된다.
FIBER_THRESHOLD = 2.5


def load_fiber_rich(path: Path) -> set[str]:
    rows = _read_rows(path)
    if not rows:
        return set()
    keys = {(row.get("key") or "").strip() for row in csv.DictReader(rows)}
    keys.discard("")
    return keys


def load_exchange(path: Path) -> dict[str, dict]:
    """csv 를 읽어 key -> {grams, foodGroup, eyeball?, advice?, unit?, fiberRich?} 로.

    식이섬유 목록은 같은 폴더의 fiber_rich.csv 에서 키로 읽어와 합친다.
    """
    lines = _read_rows(path)
    if not lines:
        return {}
    fiber_rich = load_fiber_rich(path.with_name("fiber_rich.csv"))
    table: dict[str, dict] = {}
    for row in csv.DictReader(lines):
        key = (row.get("key") or "").strip()
        if not key:
            continue
        try:
            grams = float(row["grams"])
        except (KeyError, TypeError, ValueError):
            raise SystemExit(f"exchange.csv 의 grams 가 숫자가 아닙니다: {row}")
        if grams <= 0:
            raise SystemExit(f"exchange.csv 의 grams 가 0 이하입니다: {row}")
        if key in table:
            raise SystemExit(f"exchange.csv 에 키가 중복됩니다: {key!r}")
        food_group = (row.get("food_group") or "").strip()
        entry = {"grams": grams, "foodGroup": food_group}
        # 액체는 mL 로 적는다. 비어 있으면 g — 화면 쪽 기본값과 맞춰둔다.
        unit = (row.get("unit") or "").strip()
        if unit and unit != "g":
            entry["unit"] = unit
        eyeball = (row.get("eyeball") or "").strip()
        if eyeball:
            entry["eyeball"] = eyeball
        # 줄마다 적은 것이 식품군 기본값을 이긴다.
        advice = (row.get("advice") or "").strip() or ADVICE.get(food_group)
        if advice:
            entry["advice"] = advice
        # 지침 목록에 있다는 표시. 실제로 표를 붙일지는 apply_exchange 가
        # 그 레코드의 실측 식이섬유까지 보고 정한다.
        if key in fiber_rich:
            entry["_fiberListed"] = True
        table[key] = entry

    unknown = fiber_rich - set(table)
    if unknown:
        raise SystemExit(
            "fiber_rich.csv 에 exchange.csv 에 없는 키가 있습니다: "
            + ", ".join(sorted(unknown)))
    return table


def keys_for(r) -> list[str]:
    """이 레코드가 찾아볼 키를 좁은 것부터.

    식품명(name)을 맨 앞에 둔다. gi_match 는 맨 뒤에 두지만 여기서는 반대다 —
    교환표에는 한 그룹 안의 한 항목만 값이 다른 경우가 자주 있기 때문이다.
      누룽지는 '멥쌀밥' 그룹에 있지만 밥(70g)이 아니라 30g 이다
      복숭아는 천도만 150g 이고 백도·황도는 100g 이다
    식품명이 가장 구체적인 지목이므로 그것이 있으면 그것이 이긴다.

    나머지는 조리법이 붙은 키가 먼저다. 그래야 말린 것·삶은 것이 자기 값을
    갖는다 — 마른국수 30g 과 삶은국수 90g 은 세 배 다르다.
    """
    keys = [r.name]
    if r.group and r.method:
        keys.append(f"{r.group} {r.method}")
    if r.group:
        keys.append(r.group)
    if r.rep_name and r.method:
        keys.append(f"{r.rep_name} {r.method}")
    if r.rep_name:
        keys.append(r.rep_name)
    return keys


# ── 안전장치 1 — 먹는 부위가 다르면 붙이지 않는다 ──
# '더덕 순'(탄수화물 9.6g)과 '더덕 뿌리'(21.5g)는 다른 음식이다. 키에 없는
# 부위 표기가 이름에 있으면 그 키는 이 레코드의 것이 아니다.
# GI 쪽에서 보리 순이 보리쌀 GI 를 물려받은 것과 같은 종류의 사고를 막는다.
PART_WORDS = ("순", "잎", "줄기", "꽃", "뿌리", "씨", "껍질", "싹")


def _part_mismatch(name: str, key: str) -> str | None:
    for part in (p.strip() for p in name.split("_")):
        base = part.split("+")[0].strip()
        if base in PART_WORDS and base not in key:
            return base
    return None


# ── 안전장치 2 — 교환단위의 정의와 어긋나면 붙이지 않는다 ──
# 1교환단위는 '탄수화물이 이만큼 되는 양' 으로 정의된 값이다. 그러니 붙인 뒤
# 실제로 계산해 보면 그 값이 나와야 한다. 크게 어긋나면 키를 잘못 붙인 것이다.
#   멥쌀밥 누룽지(탄수화물 86.8g)에 밥 70g 을 붙이면 60.8g 이 나온다 — 밥
#   1교환단위(23g)의 2.6배다. 누룽지는 밥이 아니라는 뜻이다.
# 표가 스스로를 검산하게 하는 것이라, 내가 키를 잘못 적어도 걸린다.
# 식품군 -> (1교환단위 탄수화물 g, 허용 하한 배수, 허용 상한 배수)
# 채소군만 상한이 넓다. 논문이 이 9종을 고른 기준 자체가 '1교환단위에 당질
# 6g 이상' 이라 기준값 3g 과 원래 어긋나 있기 때문이다 — 연근 40g 이 6.9g 이다.
# 식품군 -> (검산할 영양소, 1교환단위 함량, 허용 하한 배수, 허용 상한 배수)
#
# 군마다 검산 축이 다르다. 교환단위를 정한 기준 영양소가 다르기 때문이다 —
# 어육류군은 탄수화물이 거의 0이라 탄수화물로는 아무것도 못 거른다. 대신
# 세 군(저·중·고지방) 모두 단백질 8g 으로 같아서 단백질이 좋은 축이 된다.
# 지방군은 지방 5g 이 기준이다.
CARB_BAND = {
    "과일군": ("carb", 12.0, 0.4, 2.0),
    "곡류군": ("carb", 23.0, 0.4, 2.0),
    "우유군": ("carb", 10.0, 0.4, 2.0),
    # 채소군만 위아래로 넓다. 지침이 정한 분량이 당질 3g 을 잘 안 지키기
    # 때문이다 — 김 2g 은 당질 0.7g(0.24배), 달래 70g 은 9.4g(3.13배)이다.
    # 채소는 '충분히 드시라'는 군이라 적게 잡히는 쪽은 해가 없다. 위쪽만
    # 지키면 된다. 아래쪽 0.1 은 명백한 오배정을 잡는 최소한이다.
    "채소군": ("carb", 3.0, 0.1, 3.5),
    "어육류군": ("protein", 8.0, 0.5, 2.0),
    "지방군": ("fat", 5.0, 0.5, 2.0),
}


def _nutrient_of(r, which: str) -> float | None:
    """검산에 쓸 영양소 값. 단백질만 Nutrients 밖(FoodRecord)에 있다."""
    if which == "protein":
        return r.protein
    return getattr(r.nutrients, which)


def _carb_off(r, grams: float, food_group: str) -> float | None:
    """교환단위 기준 영양소 대비 몇 배인가. 허용 범위 안이면 None.

    (이름은 탄수화물로 시작했지만 지금은 군마다 다른 영양소를 본다)
    """
    band = CARB_BAND.get(food_group)
    if band is None:
        return None
    which, target, low, high = band
    value = _nutrient_of(r, which)
    if value is None:
        return None
    ratio = (value * grams / 100.0) / target
    return None if low <= ratio <= high else ratio


# ── 안전장치 3 — 말리거나 가루낸 것에 생것 분량을 붙이지 않는다 ──
# 수분이 빠지면 같은 무게에 든 탄수화물이 몇 배가 된다. 말린 도라지 뿌리에
# 생 도라지의 40g 을 붙이면 당질이 30g — 채소 1교환단위(3g)의 열 배다.
# 조리법이 키에 적혀 있으면(예: '포도 말리기') 일부러 붙인 것이므로 통과시킨다.
CONCENTRATING = ("말리기", "가루")

# 곡류군은 뺀다. 이 규칙의 전제(생것은 물이 많다)가 성립하지 않기 때문이다 —
# 백미는 처음부터 마른 것이라 생것 78.7g, 가루 81.1g 로 거의 같다. 규칙을
# 그대로 두면 4판이 30g 이라고 명시한 밀가루·전분가루·미숫가루·쌀가루가
# 전부 막힌다. 곡류군은 안전장치 2(탄수화물 검산)로 충분하다 —
# 말린 고구마(2.3배)·구운 옥수수(2.4배)는 그쪽에서 걸린다.
# 지방군도 같은 이유로 뺀다. 견과·종실류는 말리거나 볶은 것이 기본 형태라
# ('아몬드 말린것', '참깨 볶은것') 규칙을 그대로 두면 지방군이 통째로 막힌다.
# 지방 검산(안전장치 2)이 대신 걸러준다.
CONCENTRATING_EXEMPT = ("곡류군", "지방군")


def _method_mismatch(method: str | None, key: str, food_group: str) -> str | None:
    if food_group in CONCENTRATING_EXEMPT:
        return None
    if method in CONCENTRATING and method not in key:
        return method
    return None


def _fiber_confirmed(r, grams: float) -> bool:
    """이 레코드의 실측 식이섬유로도 1교환단위에 2.5g 이상인가.

    물려받은 값(추정)이면 False — 표는 적극적인 권장이라 추정에 기대면 안 된다.
    """
    fiber = r.nutrients.fiber
    if fiber is None or "fiber" in r.inherited:
        return False
    return fiber * grams / 100.0 >= FIBER_THRESHOLD


def apply_exchange(records, path: Path) -> dict[str, int]:
    table = load_exchange(path)
    stats = {"붙음": 0, "없음": 0, "부위 불일치로 뺌": 0,
             "말린 것에 생것 분량이라 뺌": 0, "교환단위와 어긋나 뺌": 0,
             "식이섬유 표시": 0, "식이섬유 표시 보류": 0}
    used: set[str] = set()
    rejects: list[str] = []

    for r in records:
        r.exchange = None
        for key in keys_for(r):
            hit = table.get(key)
            if hit is None:
                continue

            part = _part_mismatch(r.name, key)
            if part:
                stats["부위 불일치로 뺌"] += 1
                rejects.append(f"[부위 {part}] {r.name} ← 키 {key!r}")
                break

            dried = _method_mismatch(r.method, key, hit["foodGroup"])
            if dried:
                stats["말린 것에 생것 분량이라 뺌"] += 1
                rejects.append(f"[{dried}] {r.name} ← 키 {key!r}")
                break

            ratio = _carb_off(r, hit["grams"], hit["foodGroup"])
            if ratio is not None:
                which = CARB_BAND[hit["foodGroup"]][0]
                value = _nutrient_of(r, which)
                stats["교환단위와 어긋나 뺌"] += 1
                rejects.append(
                    f"[{ratio:.1f}배] {r.name} ({which} {value:g}g) ← 키 {key!r}")
                break

            entry = dict(hit)
            listed = entry.pop("_fiberListed", False)
            if listed and _fiber_confirmed(r, entry["grams"]):
                entry["fiberRich"] = True
                stats["식이섬유 표시"] += 1
            elif listed:
                stats["식이섬유 표시 보류"] += 1
            r.exchange = entry
            used.add(key)
            stats["붙음"] += 1
            break

        if r.exchange is None:
            stats["없음"] += 1

    stats["쓰인 키"] = len(used)
    stats["안 쓰인 키"] = len(table) - len(used)
    stats["뺀 목록"] = rejects
    return stats


def unused_keys(records, path: Path) -> list[str]:
    """한 건도 못 붙은 키. 두 가지가 섞여 있고 원인이 다르므로 갈라서 돌려준다.

      '이름이 안 맞음'  키가 어느 레코드와도 매칭되지 않는다 — 대개 오타다
      '전부 걸러짐'     매칭은 되는데 안전장치가 다 걸러냈다 — 값이나 키가
                       그 음식에 안 맞는다는 뜻이다 (예: '무순' 이 부위
                       안전장치에 걸려 한 건도 못 붙었다)

    처음엔 앞의 것만 봤는데, 뒤의 것은 조용히 사라져서 못 찾았다.
    """
    table = load_exchange(path)
    apply_exchange(records, path)

    def first_hit(r):
        for key in keys_for(r):
            if key in table:
                return key
        return None

    matched, attached = set(), set()
    for r in records:
        key = first_hit(r)
        if key is None:
            continue
        matched.add(key)
        if r.exchange:
            attached.add(key)

    return sorted((set(table) - matched) | (matched - attached))


def dead_keys(records, path: Path) -> dict[str, list[str]]:
    """unused_keys 를 원인별로 나눈 것. 리포트에서 쓴다."""
    table = load_exchange(path)
    apply_exchange(records, path)

    matched, attached = set(), set()
    for r in records:
        for key in keys_for(r):
            if key in table:
                matched.add(key)
                if r.exchange:
                    attached.add(key)
                break

    return {
        "이름이 안 맞음": sorted(set(table) - matched),
        "전부 걸러짐": sorted(matched - attached),
    }


if __name__ == "__main__":
    from group import apply_groups
    from normalize import load_records

    base = Path(__file__).resolve().parent
    recs, _ = load_records(base / "raw", base / "data" / "category_allow.csv")
    apply_groups(recs, base / "data" / "food_group.csv")
    path = base / "data" / "exchange.csv"
    stats = apply_exchange(recs, path)

    total = stats["붙음"] + stats["없음"]
    print(f"총 {total:,}건 중 1교환단위량이 붙은 것 {stats['붙음']:,}건")
    print(f"  쓰인 키 {stats['쓰인 키']}개 / 안 쓰인 키 {stats['안 쓰인 키']}개")
    print(f"  안전장치로 뺀 것: 부위 불일치 {stats['부위 불일치로 뺌']}건, "
          f"말린 것 {stats['말린 것에 생것 분량이라 뺌']}건, "
          f"교환단위와 어긋남 {stats['교환단위와 어긋나 뺌']}건")
    for line in stats["뺀 목록"]:
        print(f"    {line}")

    for reason, keys in dead_keys(recs, path).items():
        if keys:
            print(f"\n[한 건도 못 붙은 키 — {reason}]")
            for k in keys:
                print(f"  {k}")

    # 식이섬유 표시는 지침 목록을 따른다. 우리 식약처 값으로 계산하면 어디가
    # 어긋나는지 여기서 확인할 수 있게 남겨둔다 — 숨기면 나중에 어느 쪽이
    # 맞는지 다시 따져볼 근거가 사라진다.
    from normalize import apply_nutrient_fixes, fill_missing
    apply_nutrient_fixes(recs, base / "data" / "nutrient_fix.csv")
    fill_missing(recs)
    apply_exchange(recs, path)

    gaps = []
    for r in recs:
        ex = r.exchange
        if not ex or r.nutrients.fiber is None:
            continue
        per_unit = r.nutrients.fiber * ex["grams"] / 100.0
        if ex.get("fiberRich") and per_unit < FIBER_THRESHOLD:
            gaps.append((per_unit, r.name, "지침은 많다는데 우리 값은 적다"))
    gaps.sort()
    if gaps:
        print(f"\n[지침과 우리 식이섬유 값이 어긋나는 것 {len(gaps)}건 "
              f"— 표시는 지침을 따른다]")
        seen = set()
        for per_unit, name, why in gaps:
            head = name.split("_")[0]
            if head in seen:
                continue
            seen.add(head)
            print(f"  {per_unit:4.1f}g  {name}  ({why})")

    print("\n[붙은 예시]")
    shown = 0
    for r in recs:
        if r.exchange:
            e = r.exchange
            eye = f" ({e['eyeball']})" if e.get("eyeball") else ""
            print(f"  {r.display or r.name:38} {e['grams']:g}g{eye}  [{e['foodGroup']}]")
            shown += 1
            if shown >= 30:
                break
