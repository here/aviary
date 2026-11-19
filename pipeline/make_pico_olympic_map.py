#!/usr/bin/env python3
"""Draw site/maps/pico-olympic-osm.jpg: Pico Bl and Olympic Bl over OpenStreetMap tiles (zoom 15, x 5612-5619, y 13083-13085).

Usage: python pipeline/make_pico_olympic_map.py <folder of tiles named X_Y.png> site/maps/pico-olympic-osm.jpg
Tiles come from https://tile.openstreetmap.org/15/{x}/{y}.png (24 tiles, fetched once; keep the OSM credit on the image).
"""
import json, math, sys
from PIL import Image, ImageDraw, ImageFont
T = sys.argv[1]; OUT = sys.argv[2]
Z, X0, X1, Y0, Y1 = 15, 5612, 5619, 13083, 13085
mos = Image.new("RGB", ((X1 - X0 + 1) * 256, (Y1 - Y0 + 1) * 256))
for x in range(X0, X1 + 1):
    for y in range(Y0, Y1 + 1):
        mos.paste(Image.open(f"{T}/{x}_{y}.png").convert("RGB"), ((x - X0) * 256, (y - Y0) * 256))
def px(lon, lat):
    n = 2 ** Z
    fx = (lon + 180) / 360 * n
    fy = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return ((fx - X0) * 256, (fy - Y0) * 256)
# lighten the basemap so the two streets stand out
mos = Image.blend(mos, Image.new("RGB", mos.size, (255, 255, 255)), 0.35)
d = ImageDraw.Draw(mos, "RGBA")
F = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"; FB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
f12, f14, f16b = ImageFont.truetype(F, 13), ImageFont.truetype(F, 15), ImageFont.truetype(FB, 17)
pico = json.load(open("corridors/pico.json")); oly = json.load(open("corridors/olympic.json"))
PICO_EXT = [[-118.278913, 34.045558], [-118.276904, 34.044641], [-118.274968, 34.043757], [-118.271792, 34.042334], [-118.26806, 34.04063]]
ORANGE, BLUE = (194, 80, 15, 255), (42, 120, 214, 255)
def line(pts, col, w, dash=False):
    p = [px(*q) for q in pts]
    if not dash:
        d.line(p, fill=col, width=w, joint="curve")
        return
    for (a, b) in zip(p, p[1:]):
        L = math.dist(a, b); n = max(1, int(L / 14))
        for i in range(0, n, 2):
            t0, t1 = i / n, min((i + 1) / n, 1)
            d.line([(a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0), (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)], fill=col, width=w)
line(oly["line"], BLUE, 9)
line(pico["line"], ORANGE, 9)
line(PICO_EXT, ORANGE, 9, dash=True)
def label(xy, text, font, col, anchor="ls"):
    d.text(xy, text, font=font, fill=col, anchor=anchor, stroke_width=4, stroke_fill=(255, 255, 255, 255))
for name, lon, lat in oly["breakpoints"]:
    x, y = px(lon, lat); d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=(255, 255, 255, 255), outline=BLUE, width=3)
for name, lon, lat in pico["breakpoints"] + [["Figueroa St", -118.26806, 34.04063]]:
    x, y = px(lon, lat); d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=(255, 255, 255, 255), outline=ORANGE, width=3)
    label((x, y + 24), name.split(" (")[0], f14, (40, 40, 40, 255), "mt")
x, y = px(-118.318, 34.0536); label((x, y - 16), "Olympic Bl: comparison street (no project), Metro line 28", f16b, BLUE)
x, y = px(-118.318, 34.0478); label((x, y + 22), "Pico Bl: LADOT Safety and Mobility Project, Crenshaw Bl to Figueroa St", f16b, ORANGE, "lt")
x, y = px(-118.2775, 34.0438); label((x + 10, y + 26), "dashed: project, no bus data", f12, ORANGE, "lt")
# crop to the study area
x0, y0 = px(-118.3335, 34.0600); x1, y1 = px(-118.2585, 34.0360)
img = mos.crop((int(x0), int(y0), int(x1), int(y1)))
dd = ImageDraw.Draw(img)
dd.rectangle([img.width - 250, img.height - 22, img.width, img.height], fill=(255, 255, 255))
dd.text((img.width - 8, img.height - 5), "© OpenStreetMap contributors", font=f12, fill=(60, 60, 60), anchor="rs")
w = 1600; img = img.resize((w, img.height * w // img.width), Image.LANCZOS)
img.save(OUT, quality=82, optimize=True, progressive=True)
print(img.size)
