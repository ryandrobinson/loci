#!/usr/bin/env python3
"""TokyoNight gradient README banner for loci.

Same recipe as the izakaya / Athena banners: figlet 'ANSI Shadow' + a per-char
gradient, serialized to a monospace-grid SVG so GitHub renders it in colour.
Zero deps — the figlet text is pre-rendered below.

    python3 docs/banner.py        # rewrites docs/banner.svg
"""

from pathlib import Path

ART = r"""
██╗      ██████╗  ██████╗██╗
██║     ██╔═══██╗██╔════╝██║
██║     ██║   ██║██║     ██║
██║     ██║   ██║██║     ██║
███████╗╚██████╔╝╚██████╗██║
╚══════╝ ╚═════╝  ╚═════╝╚═╝
""".strip("\n")

SUBTITLE = "✦ the genius of the place · summon with //"

BG = "#16161e"
# TokyoNight gradient stops: blue -> cyan -> purple -> teal -> green -> pink.
STOPS = [
    (122, 162, 247), (125, 207, 255), (187, 154, 247),
    (115, 218, 202), (158, 206, 106), (247, 118, 142),
]


def _lerp(a, b, t):
    return round(a + (b - a) * t)


def grad_color(p):
    x = ((p % 1) + 1) % 1
    seg = x * (len(STOPS) - 1)
    i = min(len(STOPS) - 2, int(seg))
    t = seg - i
    a, b = STOPS[i], STOPS[i + 1]
    return "#" + "".join("%02x" % _lerp(a[k], b[k], t) for k in range(3))


FONT_SIZE = 13
LINE_H = FONT_SIZE * 1.35
PAD = 22
CHAR_W = FONT_SIZE * 0.6


def build_svg():
    lines = ART.split("\n")
    max_cols = max(len(l) for l in lines)
    texts = []
    for row, line in enumerate(lines):
        y = PAD + row * LINE_H + FONT_SIZE
        n = max(len(line), 1)
        spans = []
        for i, ch in enumerate(line):
            if ch == " ":
                continue
            fill = grad_color((i / n) * 0.9 + row * 0.07)
            x = PAD + i * CHAR_W
            spans.append(
                f'<tspan x="{x:.2f}" textLength="{CHAR_W:.2f}" '
                f'lengthAdjust="spacingAndGlyphs" fill="{fill}">{ch}</tspan>'
            )
        texts.append(f'<text y="{y:.1f}" xml:space="preserve">{"".join(spans)}</text>')

    w = int(max_cols * CHAR_W + PAD * 2 + 0.999)
    sub_y = PAD + len(lines) * LINE_H + FONT_SIZE + 4
    h = int(sub_y + PAD - 6 + 0.999)
    font = ("ui-monospace, 'JetBrains Mono', 'SFMono-Regular', "
            "Menlo, Consolas, monospace")
    body = "\n".join(texts)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" font-family="{font}" font-size="{FONT_SIZE}">\n'
        f'<rect width="{w}" height="{h}" rx="12" fill="{BG}"/>\n'
        f'{body}\n'
        f'<text x="{w / 2}" y="{sub_y:.1f}" text-anchor="middle" '
        f'fill="#565f89" font-size="12">{SUBTITLE}</text>\n'
        f'</svg>\n'
    )


def main():
    out = Path(__file__).resolve().parent / "banner.svg"
    svg = build_svg()
    out.write_text(svg, encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
