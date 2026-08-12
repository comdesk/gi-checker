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

# 그 음식의 '기본' 부위. 그룹은 갈라야 하지만(육과 알은 다른 음식이다)
# 화면 이름에 붙이면 어색하다 — '생 오징어류 육' 이 아니라 '생 오징어류'.
DEFAULT_PARTS = frozenset({"육", "전체"})

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


# 양념·조미 표기. 같은 재료·같은 조리법이라도 양념이 붙으면 다른 음식이다.
#
#   오징어_육_구운것          탄수  0.1g  초록
#   오징어_육_조미하여 구운것    탄수 26.6g  빨강   ← 26g 이 전부 양념이다
#
# 이것을 한 칸('굽기')에 넣으면 앱이 둘 중 하나만 골라 보여주게 되고,
# "오징어는 구우면 안 된다" 또는 "구워도 괜찮다" 중 아무 말이나 하게 된다.
# 양념 여부를 조리법과 함께 키로 써서 두 줄로 나란히 보이게 한다.
#
# 긴 표기를 먼저 둔다 — '당류에 절인것' 이 '절인것' 보다 먼저 걸려야 한다.
SEASONING_WORDS = [
    ("당류를 가한", "설탕 넣음"),
    ("당류에 절인", "설탕 절임"),
    ("조미", "양념"),
    ("양념", "양념"),
    ("튀김옷", "튀김옷"),
    # 조림은 간장·설탕을 넣고 졸이는 것이라 탄수화물이 크게 붙는다
    # (젓새우 조린것 35.1g vs 생것 0.9g). '통조림' 은 '조린것' 을 포함하지
    # 않으므로 걸리지 않는다.
    ("장류를 넣고", "장류 조림"),
    ("조린것", "조림"),
    ("소금에 절인", "소금 절임"),
    ("간장에 절인", "간장 절임"),
    ("식초에 절인", "식초 절임"),
]


def _find_seasoning(name: str) -> str | None:
    """이름에 양념·절임 표기가 있으면 화면에 쓸 짧은 말로 돌려준다.

    '통조림' 의 '조림' 처럼 다른 낱말에 묻힌 것은 잡지 않는다 — 위 목록의
    표기들은 전부 두 글자 이상이고 다른 낱말의 일부로 나타나지 않는다
    (실측 확인: '조미' 25건·'양념' 48건 모두 진짜 양념 표기였다).
    """
    for word, label in SEASONING_WORDS:
        if word in name:
            return label
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


# 수과원 데이터는 이름 끝에 '어디서 언제 뜬 시료인지' 를 붙여 놓았다.
#   오징어류_오징어_육_조미하여 구운것_대표_평균
#   눈볼대_육_생것_남해_11월
# '대표 평균' 은 대표 시료를 여러 달 평균 냈다는 뜻이고 '남해 11월' 은 채집지와
# 시기다. 음식 이름이 아니라 시료 표기이므로 화면에서는 뗀다 — 원본 표기는
# 영양성분 상자의 '원본' 줄에 그대로 남으므로 정보가 사라지지는 않는다.
_SAMPLE_TIME = re.compile(r"^(평균|\d{1,2}월)$")
# 시기 바로 앞에 오는 채집지. 실측으로 967건 전수를 확인해 뽑았다.
# '대구'·'기장'·'진주' 는 음식 이름이기도 하지만(대구, 기장, 진주조개) 이 자리에
# 올 때는 전부 지명이었고, 음식 이름은 앞 조각에 따로 남아 있다.
_SAMPLE_PLACE = {
    "대표", "수입", "부산", "여수", "포항", "통영", "완도", "진안", "남해", "강릉",
    "삼천포", "제주", "진주", "인천", "경기", "창원", "거제", "신안", "군산", "해남",
    "충무", "양양", "영덕", "진해", "문경", "대구", "금산", "광양", "대전", "거문도",
    "자란도", "율촌", "춘천", "영암", "기장", "울릉도", "보령", "가평(청평)",
    # 처음 목록을 만들 때 상위 40개만 보고 지나쳐 34건이 남아 있었다.
    # 이번엔 '평균|N월' 앞에 오는 조각을 전수로 훑어 빠짐없이 채웠다.
    "경주", "속초", "동해EEZ", "원양산", "장흥", "동해", "남해중부", "목포",
    "영광", "사천", "구산면", "대청댐", "서해남부EEZ",
}
_SAMPLE_PLACE_RE = re.compile(r"^수입\(.+\)$")


def strip_sample_tag(name: str) -> str:
    """이름 끝의 시료 표기(채집지·시기)를 뗀다. 뗄 게 없으면 그대로.

    최소 두 조각은 남긴다 — 다 떼어내고 이름이 사라지면 안 된다.
    """
    parts = [p.strip() for p in name.split("_") if p.strip()]
    if len(parts) >= 3 and _SAMPLE_TIME.match(parts[-1]):
        parts = parts[:-1]
        if (len(parts) >= 3
                and (parts[-1] in _SAMPLE_PLACE or _SAMPLE_PLACE_RE.match(parts[-1]))):
            parts = parts[:-1]
    return "_".join(parts)


def sample_tag(name: str) -> str:
    """strip_sample_tag 가 떼어낸 부분('대표 7월', '부산 5월'). 없으면 빈 문자열.

    답이 갈리는 시료를 화면에 나란히 놓아야 할 때 이름을 되살리는 데 쓴다.
    """
    kept = strip_sample_tag(name)
    rest = name[len(kept):].strip("_")
    return rest.replace("_", " ").strip()


# 영문 품종명·상품 코드를 이름에서 뺀다.
#   피 IEC525(NO.5) 도정 생것          -> 피 도정 생것            (연구 계통 번호)
#   파프리카 Raon yellow(미니파프리카) ... -> 파프리카 미니파프리카 ...  (상품 품종명)
#   아이스티 NEW복숭아아이스티            -> 아이스티 복숭아아이스티
#   소보로빵 PB정통소보루               -> 소보로빵 정통소보루
#
# 단, 괄호 안에 한글이 있으면 그건 설명이라 살린다 — '(중량1g)' 의 'g' 까지
# 지우면 '(중량1)' 이 되어 뜻이 망가진다. 그래서 괄호 밖만 손댄다.
_PAREN = re.compile(r"\(([^()]*)\)")
_LATIN_RUN = re.compile(r"[A-Za-z][A-Za-z0-9.\-]*(\s+[A-Za-z][A-Za-z0-9.\-]*)*")
_HANGUL = re.compile(r"[가-힣]")


def _strip_latin(segment: str) -> str:
    """조각에서 영문 표기를 뺀다. 남는 것이 없으면 빈 문자열(호출부가 버린다)."""
    kept_parens = []

    def take(m):
        inner = m.group(1)
        if _HANGUL.search(inner):        # '(미니파프리카)', '(중량1g)' 은 설명이다
            kept_parens.append(inner)
        return "\x00"                    # 자리만 남겨둔다

    outside = _PAREN.sub(take, segment)
    outside = _LATIN_RUN.sub("", outside)
    # 괄호 자리를 되돌린다. 괄호 밖에 아무것도 안 남았으면 괄호를 벗긴다.
    rest = outside.replace("\x00", "").strip(" -·,")
    if not rest:
        return " ".join(kept_parens).strip()
    for inner in kept_parens:
        rest = f"{rest}({inner})"
    return rest.strip(" -·,")


def _drop_redundant_class(parts: list[str]) -> list[str]:
    """'오징어류_오징어_...' 의 앞머리를 뗀다.

    원본은 분류군('~류')과 실제 종을 나란히 적어 놓았다. 사람이 읽을 때는
    종 이름만 있으면 된다.
        오징어류 오징어 육 구운것  ->  오징어 육 구운것
        장어류 뱀장어 육 ...      ->  뱀장어 육 ...
    종이 분류군과 다른 이름이면(오징어류 한치) 그대로 둘 수도 있지만, 그때도
    '한치' 만으로 충분히 알아본다 — 어차피 분류군은 검색용 원본에 남는다.
    """
    if len(parts) >= 3 and parts[0].endswith("류") and len(parts[0]) >= 2:
        return parts[1:]
    return parts


def _readable(name: str) -> str:
    """원본 표기를 사람이 읽을 수 있게. '_' 는 공백으로.

    '수컷,다리'·'양식,육' 처럼 쉼표로 붙여 놓은 것은 공백으로 푼다 —
    원본의 표기 습관일 뿐이고 사람은 그렇게 읽지 않는다.
    """
    segments = _drop_redundant_class(
        [p for p in strip_sample_tag(name).split("_") if p])
    # 쉼표 묶음을 먼저 푼다. '수컷,다리' 는 두 낱말이고, '양식,육' 의 '육' 은
    # 아래 기본 부위 제거에 걸려야 한다 — 붙어 있으면 둘 다 안 된다.
    parts = [w for seg in segments for w in seg.split(",") if w.strip()]
    # 영문 품종명·상품 코드를 빼고, 빼고 나서 남는 게 없으면 그 조각을 버린다.
    parts = [s for s in (_strip_latin(w) for w in parts) if s] or parts
    # '육'·'전체' 는 기본 부위라 이름에 넣으면 어색하다 ('멸치 전체 쪄서 말린것').
    # 그룹은 이미 갈라져 있으므로 이름에서 빼도 헷갈리지 않는다.
    if len(parts) >= 3:
        parts = [p for p in parts if p not in DEFAULT_PARTS] or parts
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def apply_groups(records, map_path: Path) -> dict[str, int]:
    manual = load_manual(map_path)
    splits = load_species_split(map_path.parent / "species_split.csv")
    stats = dict.fromkeys(
        ("조리법있음", "조리법없음", "수동", "단독그룹해제",
         "부위분리", "종분리", "양념표기"), 0)

    # 화면에 쓸 그룹 이름. 그룹 키와 다를 수 있다 —
    # 키 '호박 단호박' 은 다른 그룹과 겹치지 않기 위한 것이고,
    # 사람이 부르는 이름은 그냥 '단호박' 이다.
    labels: dict[int, str] = {}

    for r in records:
        r.seasoning = _find_seasoning(r.name)
        if r.seasoning:
            stats["양념표기"] += 1
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
                # 단 '육'·'전체' 는 그 음식의 기본 상태라 이름에 붙이면 어색하다
                # ('생 오징어류 육'). 그룹 키는 그대로 두고 이름에서만 뺀다.
                base = labels.get(id(r), r.rep_name)
                labels[id(r)] = base if part in DEFAULT_PARTS else f"{base} {part}"
                stats["부위분리"] += 1

        # 화면용 이름.
        #   '고구마_찐것' (대표식품명 + 조리법뿐) → '찐 고구마'
        #   '소고기_수입산(미국산)_설도_구운것(석쇠)' → 정보가 많으므로 원본을 읽기 좋게만
        prefix = METHOD_PREFIX.get(r.method) if r.method else None
        # 시료 표기를 뗀 뒤에 본다 — '오징어_육_구운것_대표_평균' 의 마지막
        # 조각은 '평균' 이라 그대로 두면 어떤 이름도 단순형으로 인정되지 않는다.
        parts = [p for p in strip_sample_tag(r.name).split("_") if p]
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
