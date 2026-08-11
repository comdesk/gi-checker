"""GI 표 PDF → 중간 CSV. 한 번만 돌리면 된다 (산출물을 커밋한다).

Supplemental Table 1 은 139쪽짜리 표다. 페이지마다 머리글·꼬리글이 섞여 있고
줄바꿈이 제각각이라 완벽한 파싱은 불가능하다. 목표는 '사람이 훑어보며
gi_map.csv 를 채울 수 있을 정도'로만 뽑는 것이다.
"""

import csv
import re
import sys
from pathlib import Path

from pypdf import PdfReader

BASE = Path(__file__).resolve().parent
PDF = BASE / "raw" / "gi_table1.pdf"
OUT = BASE / "data" / "gi_table_raw.csv"

# [Step 1 수정 — 브리프의 원본 정규식은 실사용 불가였다]
# 브리프 원본 ROW 정규식('식품명 ... 숫자 ... 숫자')으로 뽑아보니 줄 안의 아무
# 숫자나 걸려 GI 값이 거의 다 엉뚱했다 (예: 'resistant starch from tapioca) 11'
# 로 뽑히지만 실제 GI 는 70). PDF 표를 직접 보니 진짜 GI 값은 표 전체에서
# 예외 없이 '68±4' 처럼 '평균±표준오차'로만 나온다 — 같은 줄의 다른 숫자
# (GL, 피험자 수, 검사분량 등)는 '±' 표기가 없다. 그래서 '±' 자체를 앵커로
# 삼아 그 앞의 숫자만 GI 로 뽑도록 정규식을 바꿨다. 브리프가 "GI 값이 전부
# 엉뚱하면 정규식을 고치라"고 명시적으로 허용한 범위 안의 수정이다.
NOISE = re.compile(
    r"(Atkinson|Supplemental Table|Online Supplemental|^\s*\d+\s*$|"
    r"Average available carbohydrate|Average carbohydrate portion)"
)

# 진짜 GI 값 ('68±4' 형태). 캡처된 숫자 앞부분을 식품명 후보로 쓴다.
MEASURED = re.compile(r"(?P<gi>\d{1,3})\s*±\s*\d+(?:\.\d+)?")

# 요약행: 'Boiled sweet potato, mean of 13 studies   46' 처럼 같은 조리법
# 여러 실측치를 평균해 대표값 하나로 보여주는 줄. 개별 실측 줄보다
# 사람이 gi_map.csv 를 채울 때 참고하기 훨씬 좋다.
SUMMARY = re.compile(
    r"^(?P<name>[A-Za-z][^0-9]{2,100}?),?\s*mean of \d+\s*"
    r"(?:studies|foods|types? of [a-z]+)\s+(?P<gi>\d{1,3})\s*$"
)


def main() -> int:
    # Windows 콘솔(cp949)이 PDF 원문의 é 같은 문자를 못 찍어 죽는 것을 막는다.
    # 파일 출력(utf-8-sig)에는 영향 없다 — 콘솔 표시만 안전하게 대체한다.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    if not PDF.exists():
        print(f"GI PDF 가 없습니다: {PDF}")
        return 1

    reader = PdfReader(PDF)
    rows = []
    for page_no, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        for raw_line in text.splitlines():
            line = " ".join(raw_line.split())
            if not line or NOISE.search(line):
                continue

            sm = SUMMARY.match(line)
            if sm:
                gi = int(sm.group("gi"))
                if 0 < gi <= 150:
                    rows.append({
                        "page": page_no,
                        "name_en": sm.group("name").strip(" ,;") + " (mean)",
                        "gi": gi,
                        "line": line[:160],
                    })
                continue

            m = MEASURED.search(line)
            if not m:
                continue
            gi = int(m.group("gi"))
            if not (0 < gi <= 150):
                continue
            name = line[:m.start()].strip(" ,;") or line[:80]
            rows.append({
                "page": page_no,
                "name_en": name[:80],
                "gi": gi,
                "line": line[:160],
            })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["page", "name_en", "gi", "line"])
        w.writeheader()
        w.writerows(rows)

    print(f"{len(rows):,}행 추출 → {OUT}")
    print("\n[샘플 15행]")
    for r in rows[:15]:
        print(f"  p{r['page']:>3} | GI {r['gi']:>3} | {r['name_en'][:60]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
