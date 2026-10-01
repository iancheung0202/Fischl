"""Generates a rough placeholder map (SVG) + anchor points so the site looks like a map until you have real art.
Run from the web/ folder:  python tools/make_placeholder_map.py"""

import json
import math
import random


def blob(cx, cy, rx, ry, rng, n=22, j=0.3):
    pts = [
        (
            cx + math.cos(2 * math.pi * i / n) * rx * (1 + rng.uniform(-j, j)),
            cy + math.sin(2 * math.pi * i / n) * ry * (1 + rng.uniform(-j, j)),
        )
        for i in range(n)
    ]
    mid = lambda a, b: ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    s = mid(pts[-1], pts[0])
    d = f"M{s[0]:.0f} {s[1]:.0f}"
    for i in range(n):
        e = mid(pts[i], pts[(i + 1) % n])
        d += f"Q{pts[i][0]:.0f} {pts[i][1]:.0f} {e[0]:.0f} {e[1]:.0f}"
    return d + "Z"


def svg(water, land, edge, shapes, extras=""):
    land_paths = "".join(
        f'<path d="{d}" fill="none" stroke="{edge}" stroke-opacity=".12" stroke-width="16"/><path d="{d}" fill="{land}" stroke="{edge}" stroke-width="2.5"/>'
        for d in shapes
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 600"><defs><filter id="p"><feTurbulence type="fractalNoise" baseFrequency=".8" numOctaves="3"/>'
        f'<feColorMatrix values="0 0 0 0 .35 0 0 0 0 .27 0 0 0 0 .12 0 0 0 .14 0"/></filter></defs>'
        f'<rect width="1000" height="600" fill="{water}"/>{land_paths}{extras}<rect width="1000" height="600" filter="url(#p)"/></svg>'
    )


def hills(rng, cx, cy, n, spread):
    out = ""
    for _ in range(n):
        x, y = cx + rng.uniform(-spread, spread), cy + rng.uniform(
            -spread * 0.6, spread * 0.6
        )
        out += f'<path d="M{x-9:.0f} {y+6:.0f}L{x:.0f} {y-9:.0f}L{x+9:.0f} {y+6:.0f}" fill="none" stroke="#7a6446" stroke-width="2" stroke-linecap="round"/>'
    return out


rng = random.Random(7)
anchors, islands = [], []
for gy in range(3):
    for gx in range(5):
        cx, cy = 100 + gx * 200 + rng.uniform(-30, 30), 100 + gy * 200 + rng.uniform(
            -25, 25
        )
        islands.append(blob(cx, cy, rng.uniform(70, 95), rng.uniform(50, 68), rng))
        anchors.append([round(cx), round(cy)])
extras = "".join(hills(rng, a[0], a[1], 5, 55) for a in anchors)
open("static/world/world-map.svg", "w").write(
    svg("#e7d9b4", "#d4c196", "#8a7048", islands, extras)
)

rng = random.Random(3)
land = [blob(500, 310, 470, 270, rng, 30, 0.1)]
lakes = "".join(
    f'<path d="{blob(x, y, r, r*.6, rng, 14, .25)}" fill="#7fa3b0" stroke="#4e6f7d" stroke-width="2"/>'
    for x, y, r in [(420, 300, 60), (700, 420, 45)]
)
open("static/world/region-map.svg", "w").write(
    svg(
        "#5b7f8e",
        "#8fae6e",
        "#4e6340",
        land,
        lakes + hills(rng, 850, 120, 14, 110) + hills(rng, 600, 200, 8, 80),
    )
)

json.dump(
    {
        "world": {"image": "/world/world-map.svg", "anchors": anchors},
        "region": {
            "image": "/world/region-map.svg",
            "camp": [120, 500],
            "routes": {
                "4": {"name": "Dawn Winery", "d": "M120 500C200 470 300 460 400 420"},
                "8": {
                    "name": "Windwail Highland",
                    "d": "M120 500C180 380 260 330 360 320S560 340 650 250",
                },
                "12": {
                    "name": "Stormterror Peak",
                    "d": "M120 500C100 350 120 220 250 160S450 60 560 130 760 230 820 130 880 100 900 90",
                },
            },
        },
    },
    open("static/world/map.json", "w"),
    indent=1,
)
