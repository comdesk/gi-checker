"""버전은 데이터뿐 아니라 화면 코드가 바뀌어도 달라져야 한다.

실제로 겪은 사고다: 공유 버튼(코드만 바뀐 배포)에서 데이터가 그대로라
VERSION 이 안 바뀌었고, GitHub Pages 의 10분 CDN 캐시가 낡은 app.js 를
내려주는 사이 서비스워커가 그 낡은 파일을 새 캐시에 박제했다 — 화면은
새 데이터에 옛 코드가 섞였고, 버전이 안 바뀌니 영영 낫지 않았다.
"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from bundle import assets_digest

WEB = BASE.parent / "web"


def test_웹_파일이_바뀌면_다이제스트가_바뀐다(tmp_path):
    for name, body in [("app.js", "let a = 1;"), ("styles.css", "body{}")]:
        (tmp_path / name).write_text(body, encoding="utf-8")
    before = assets_digest(tmp_path)
    (tmp_path / "app.js").write_text("let a = 2;", encoding="utf-8")
    assert assets_digest(tmp_path) != before


def test_새_파일이_생겨도_다이제스트가_바뀐다(tmp_path):
    """share.js 처럼 파일이 추가되는 배포도 코드 변경이다."""
    (tmp_path / "app.js").write_text("let a = 1;", encoding="utf-8")
    before = assets_digest(tmp_path)
    (tmp_path / "share.js").write_text("export {};", encoding="utf-8")
    assert assets_digest(tmp_path) != before


def test_sw의_VERSION_줄은_다이제스트에_안_들어간다(tmp_path):
    """빌드가 VERSION 을 찍어 넣는 파일이라, 그 줄을 세면 순환이 된다 —
    버전을 계산하려면 sw.js 가 필요한데 sw.js 는 버전이 정해져야 완성된다."""
    (tmp_path / "sw.js").write_text(
        "const VERSION = '2026-01-01+aaaa';\nconst X = 1;", encoding="utf-8")
    before = assets_digest(tmp_path)
    (tmp_path / "sw.js").write_text(
        "const VERSION = '2026-12-31+bbbb';\nconst X = 1;", encoding="utf-8")
    assert assets_digest(tmp_path) == before
    # VERSION 줄이 아닌 본문이 바뀌면 당연히 달라져야 한다
    (tmp_path / "sw.js").write_text(
        "const VERSION = '2026-12-31+bbbb';\nconst X = 2;", encoding="utf-8")
    assert assets_digest(tmp_path) != before


def test_foods_json_은_다이제스트에_안_들어간다(tmp_path):
    """데이터는 이미 payload 해시가 세고 있다. 여기서 또 세면 이중이고,
    빌드 산출물이라 빌드 전후로 값이 달라져 재현이 깨진다."""
    (tmp_path / "app.js").write_text("let a = 1;", encoding="utf-8")
    before = assets_digest(tmp_path)
    (tmp_path / "foods.json").write_text('{"v":1}', encoding="utf-8")
    assert assets_digest(tmp_path) == before


def test_tests_폴더는_다이제스트에_안_들어간다(tmp_path):
    """테스트는 배포되지 않는다. 테스트만 고친 커밋이 버전을 바꾸면
    사용자 폰이 의미 없이 2.4MB 를 다시 받는다."""
    (tmp_path / "app.js").write_text("let a = 1;", encoding="utf-8")
    before = assets_digest(tmp_path)
    sub = tmp_path / "tests"
    sub.mkdir()
    (sub / "x.test.js").write_text("test", encoding="utf-8")
    assert assets_digest(tmp_path) == before


def test_실제_web_폴더로_계산이_된다():
    d = assets_digest(WEB)
    assert isinstance(d, str) and len(d) >= 8
