"""오프라인(PWA) 산출물 검증.

첫 실행 한 번만 네트워크가 필요하고 그 뒤로는 없어도 열려야 한다.
빠진 파일이 하나라도 있으면 오프라인에서 깨지므로 목록을 대조한다.
"""

import json
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent.parent
WEB = BUILD.parent / "web"
sys.path.insert(0, str(BUILD))

from bundle import SW_VERSION_LINE, bundle_version


def _sw_version() -> str:
    m = SW_VERSION_LINE.search((WEB / "sw.js").read_text(encoding="utf-8"))
    assert m, "sw.js 에서 VERSION 줄을 찾지 못했다"
    return m.group(0).split("'")[1]


def test_서비스워커_판이_번들과_같다():
    """서비스워커는 자기 파일 내용이 바뀌어야 새로 설치된다.
    데이터만 갱신하고 이 줄을 안 고치면 사용자는 영영 옛 foods.json 을 본다."""
    bundle = json.loads((WEB / "foods.json").read_text(encoding="utf-8"))
    assert _sw_version() == bundle["version"]


def test_판이_데이터_내용을_따라간다():
    """날짜만 쓰면 같은 날 두 번 빌드했을 때 판이 안 바뀌어, 데이터를 고쳐도
    사용자 폰에는 옛것이 남는다. 판은 실제 데이터의 해시를 담아야 한다."""
    bundle = json.loads((WEB / "foods.json").read_text(encoding="utf-8"))
    assert bundle_version(bundle) == bundle["version"]

    changed = {**bundle, "foods": bundle["foods"][:-1]}
    assert bundle_version(changed) != bundle["version"]


def test_캐싱_목록에_실제_파일이_다_있다():
    """목록에 적힌 파일이 없으면 install 이 통째로 실패해 오프라인이 안 된다."""
    sw = (WEB / "sw.js").read_text(encoding="utf-8")
    listed = re.findall(r"'\./([^']+)'", sw)
    for name in listed:
        assert (WEB / name).exists(), f"sw.js 가 없는 파일을 캐싱하려 한다: {name}"


def test_앱이_쓰는_파일이_캐싱_목록에_다_있다():
    """반대 방향. 빠뜨리면 그 파일만 오프라인에서 안 열린다.

    목록을 손으로 적어두면 파일을 새로 만들 때 같이 늘리는 것을 잊는다.
    index.html 과 실제 import 문에서 뽑아내 대조한다."""
    sw = (WEB / "sw.js").read_text(encoding="utf-8")
    html = (WEB / "index.html").read_text(encoding="utf-8")

    needed = {"index.html", "foods.json"}
    needed |= set(re.findall(
        r'(?:src|href)="(?:\./)?([\w.\-]+\.(?:js|css|webmanifest|png))"', html))
    for js in WEB.glob("*.js"):
        if js.name == "sw.js":          # 서비스워커는 자기 자신을 캐싱하지 않는다
            continue
        needed |= {
            m for m in re.findall(r"""from\s+['"]\./([\w.\-]+)['"]""",
                                  js.read_text(encoding="utf-8"))
        }

    for name in sorted(needed):
        assert f"'./{name}'" in sw, f"{name} 이 캐싱 목록에 없다"


def test_매니페스트가_상대경로다():
    """GitHub Pages 는 /저장소이름/ 아래에 얹힌다.
    '/' 로 시작하는 경로를 쓰면 그 순간 전부 404 다."""
    manifest = json.loads((WEB / "manifest.webmanifest").read_text(encoding="utf-8"))
    for key in ("start_url", "scope"):
        assert not manifest[key].startswith("/"), f"{key}={manifest[key]}"
    for icon in manifest["icons"]:
        assert not icon["src"].startswith("/"), icon["src"]
        assert (WEB / icon["src"]).exists(), f"아이콘이 없다: {icon['src']}"


def test_html_도_상대경로다():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert not re.search(r'(?:src|href)="/', html), "절대경로가 있으면 하위 경로에서 깨진다"


def test_매니페스트에_필요한_것이_다_있다():
    manifest = json.loads((WEB / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifest["display"] == "standalone", "주소창 없이 앱처럼 떠야 한다"
    sizes = {i["sizes"] for i in manifest["icons"]}
    assert {"192x192", "512x512"} <= sizes, sizes
    purposes = {i.get("purpose") for i in manifest["icons"]}
    assert "maskable" in purposes, "안드로이드가 아이콘을 잘라내므로 maskable 이 필요하다"
