"""홈 화면 아이콘 만들기. 표준 라이브러리만 쓴다 (npm 의존성 0 원칙).

신호등 세 알을 그린다. 이 앱이 하는 일이 그것이고, 48px 로 줄여도 알아본다.
글자는 넣지 않는다 — 작은 아이콘에서 한글은 뭉개지고, 폰트를 끌어와야 한다.

안티에일리어싱은 4배로 그린 뒤 줄이는 방식(슈퍼샘플링)으로 낸다.
"""

import struct
import zlib
from pathlib import Path

SS = 4          # 슈퍼샘플링 배율
BG = (22, 24, 29)          # --ink. 홈 화면에서 밝은 배경·어두운 배경 양쪽에 뜬다
GREEN = (31, 122, 76)      # --green
AMBER = (217, 154, 31)     # --amber
RED = (200, 55, 45)        # --red


def _png(width: int, height: int, pixels: list[list[tuple[int, int, int, int]]]) -> bytes:
    """RGBA 픽셀 배열 → PNG 바이트."""
    raw = bytearray()
    for row in pixels:
        raw.append(0)                      # 필터 타입 0 (None)
        for r, g, b, a in row:
            raw += bytes((r, g, b, a))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


def _blend(dst, src, alpha):
    return tuple(round(d + (s - d) * alpha) for d, s in zip(dst, src))


def _draw(size: int, *, maskable: bool) -> bytes:
    """신호등 아이콘 하나를 그린다.

    maskable=True 면 안드로이드가 아이콘을 원형·둥근사각으로 잘라내므로
    안쪽 80% 안에만 그린다(안전 영역). False 면 화면을 꽉 채운다.
    """
    big = size * SS
    # 배경 둥근 사각형의 모서리 반지름. maskable 은 어차피 잘리므로 꽉 채운다.
    radius = 0 if maskable else big * 0.22
    safe = 0.80 if maskable else 1.0

    # 신호등 세 알: 세로로 배치. 지름과 간격을 안전 영역 기준으로 잡는다.
    span = big * safe
    top = (big - span) / 2
    diameter = span * 0.34
    gap = (span - diameter * 3) / 4
    centers = [(big / 2, top + gap * (i + 1) + diameter * (i + 0.5))
               for i in range(3)]
    colors = (GREEN, AMBER, RED)
    r_dot = diameter / 2

    canvas = [[(0, 0, 0, 0)] * big for _ in range(big)]
    for y in range(big):
        for x in range(big):
            px, py = x + 0.5, y + 0.5
            # 배경(둥근 사각형) 안인가
            inside = True
            if radius:
                cx = min(max(px, radius), big - radius)
                cy = min(max(py, radius), big - radius)
                inside = (px - cx) ** 2 + (py - cy) ** 2 <= radius ** 2
            if not inside:
                continue
            color = BG
            for (dx, dy), dot in zip(centers, colors):
                if (px - dx) ** 2 + (py - dy) ** 2 <= r_dot ** 2:
                    color = dot
                    break
            canvas[y][x] = (*color, 255)

    # 4x4 평균으로 줄인다 = 안티에일리어싱
    out = []
    for y in range(size):
        row = []
        for x in range(size):
            acc = [0, 0, 0, 0]
            for sy in range(SS):
                for sx in range(SS):
                    p = canvas[y * SS + sy][x * SS + sx]
                    # 투명 픽셀은 색을 섞지 않는다 (검은 테두리가 생긴다)
                    weight = p[3] / 255
                    acc[0] += p[0] * weight
                    acc[1] += p[1] * weight
                    acc[2] += p[2] * weight
                    acc[3] += p[3]
            n = SS * SS
            alpha = acc[3] / n
            if alpha <= 0:
                row.append((0, 0, 0, 0))
                continue
            scale = n * (alpha / 255)
            row.append((round(acc[0] / scale), round(acc[1] / scale),
                        round(acc[2] / scale), round(alpha)))
        out.append(row)
    return _png(size, size, out)


ICONS = (
    ("icon-192.png", 192, False),
    ("icon-512.png", 512, False),
    ("icon-maskable-512.png", 512, True),
    ("apple-touch-icon.png", 180, True),   # iOS 는 알아서 둥글게 자른다
)


def build(web_dir: Path) -> list[tuple[str, int]]:
    made = []
    for filename, size, maskable in ICONS:
        data = _draw(size, maskable=maskable)
        (web_dir / filename).write_bytes(data)
        made.append((filename, len(data)))
    return made


if __name__ == "__main__":
    web = Path(__file__).resolve().parent.parent / "web"
    for name, size in build(web):
        print(f"  {name:<26} {size:,} bytes")
