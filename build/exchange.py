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

# 열량별 식단안에서 하루 몇 교환단위인지. 대한당뇨병학회 홈페이지의
# 열량별 교환단위수 배분표(1,500 / 1,800 / 2,100 kcal, 식단안 3종)에서
# 세 안이 모두 같은 범위를 주는 군만 적는다.
#   과일군 1,500->1  1,800->1~2  2,100->2   (세 안 일치)
#   우유군 합계      1~2                    (세 안 일치)
# 곡류군은 5~11, 채소군은 7~9 로 안마다 크게 달라 하루 횟수를 말하지 않는다 —
# 범위가 그만큼 넓으면 알려주는 것이 아니라 헷갈리게 하는 것이다.
DAILY = {
    "과일군": "하루 1~2번",
    "우유군": "하루 1~2번",
}


def load_exchange(path: Path) -> dict[str, dict]:
    """csv 를 읽어 key -> {grams, eyeball, foodGroup, daily} 로 만든다.

    '#' 로 시작하는 줄은 주석이다. csv 모듈은 주석을 모르므로 미리 걸러낸다.
    """
    if not path.exists():
        return {}
    lines = [ln for ln in path.read_text(encoding="utf-8-sig").splitlines()
             if ln.strip() and not ln.lstrip().startswith("#")]
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
        if food_group in DAILY:
            entry["daily"] = DAILY[food_group]
        table[key] = entry
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
CARB_BAND = {
    "과일군": (12.0, 0.4, 2.0),
    "곡류군": (23.0, 0.4, 2.0),
    "우유군": (10.0, 0.4, 2.0),
    "채소군": (3.0, 0.4, 3.0),
}


def _carb_off(carb: float, grams: float, food_group: str) -> float | None:
    """교환단위 기준 탄수화물 대비 몇 배인가. 허용 범위 안이면 None."""
    band = CARB_BAND.get(food_group)
    if band is None or carb is None:
        return None
    target, low, high = band
    ratio = (carb * grams / 100.0) / target
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
CONCENTRATING_EXEMPT = ("곡류군",)


def _method_mismatch(method: str | None, key: str, food_group: str) -> str | None:
    if food_group in CONCENTRATING_EXEMPT:
        return None
    if method in CONCENTRATING and method not in key:
        return method
    return None


def apply_exchange(records, path: Path) -> dict[str, int]:
    table = load_exchange(path)
    stats = {"붙음": 0, "없음": 0, "부위 불일치로 뺌": 0,
             "말린 것에 생것 분량이라 뺌": 0, "교환단위와 어긋나 뺌": 0}
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

            ratio = _carb_off(r.nutrients.carb, hit["grams"], hit["foodGroup"])
            if ratio is not None:
                stats["교환단위와 어긋나 뺌"] += 1
                rejects.append(
                    f"[{ratio:.1f}배] {r.name} (탄{r.nutrients.carb:g}g) ← 키 {key!r}")
                break

            r.exchange = dict(hit)
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
    """어느 레코드에도 안 붙은 키. 오타를 잡기 위한 것이다."""
    table = load_exchange(path)
    used = set()
    for r in records:
        for key in keys_for(r):
            if key in table:
                used.add(key)
                break
    return sorted(set(table) - used)


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

    missing = unused_keys(recs, path)
    if missing:
        print("\n[어디에도 안 붙은 키 — 오타이거나 그 음식이 데이터에 없다]")
        for k in missing:
            print(f"  {k}")

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
