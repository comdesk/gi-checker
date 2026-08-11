# 원본 자료 출처

`build/raw/` 는 버전관리에서 제외된다. 갱신할 때 아래에서 다시 받는다.

## 영양성분 CSV — 공공데이터포털, 로그인·활용신청 불필요

각 페이지에서 형식을 **CSV** 로 골라 받은 뒤 이름을 바꿔 `build/raw/` 에 둔다.

| 받는 곳 | 저장할 이름 | 실측 행 수 |
|---|---|---|
| https://www.data.go.kr/data/15100065/standard.do (원재료성식품) | `원재료성_농진청.csv` | 1,858 |
| 같은 페이지, 해양수산부 국립수산과학원 제공분 | `원재료성_수과원.csv` | 1,846 |
| https://www.data.go.kr/data/15100070/standard.do (음식) | `음식.csv` | 19,495 |

- 파일 형식: UTF-8 **BOM 있음**
- 컬럼 수는 세 파일이 다르다: `원재료성_농진청.csv`/`원재료성_수과원.csv`는 53개로
  서로 동일하지만, `음식.csv`는 **50개**다 — 원산지 관련 6개(`폐기율(%)`,
  `수입여부`, `원산지국코드`, `원산지국명`, `원산지역명`, `생산·채취·포획월`)가
  없는 대신 `업체명`, `1인(회)분량 참고량`, **`식품중량`** 3개가 더 있다
- `식품중량`은 **`음식.csv`에만 있다.** 19,483/19,495행에 값이 있고
  (예: `291.90ml`, `400g`), 실제 1인분 표시(`serving_label`)에 쓴다.
  원재료성 두 파일에는 이 컬럼 자체가 없다
- 모든 영양성분은 **100g 또는 100ml 기준**이다. 1회 제공량 컬럼은 없다
- `가공식품` (https://www.data.go.kr/data/15100066/standard.do, 306,293행)은
  거의 전부 브랜드 상품명이라 **의도적으로 제외**했다. 넣으려면
  `normalize.py` 의 `SOURCE_FILES` 에 추가하고 필터를 크게 강화해야 한다

## GI 표 — 논문 부록

Atkinson FS, Brand-Miller JC, Foster-Powell K, Buyken AE, Goletzke J.
"International tables of glycemic index and glycemic load values 2021:
a systematic review." Am J Clin Nutr. 2021;114(5):1625-1632.

Supplemental Table 1 (ISO 26642:2010 기준 실측 GI, 139쪽 PDF) 을 받아
`build/raw/gi_table1.pdf` 로 둔다. 공개 사본:
https://nutritotal.com.br/pro/wp-content/uploads/2021/09/Tabela1_IG.pdf
