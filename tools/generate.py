#!/usr/bin/env python3
"""Generate the Classic Analog watch face: the Watch Face Format XML and its
images.

The layout is computed from the screen radius, so the XML is generated
rather than written by hand. Run this after changing anything below, then
build with Gradle (build.sh does both).

Writes:
  watchface/src/main/res/raw/watchface.xml   the watch face
  watchface/src/main/res/drawable/hand_*.png the hands

With --test, the hands are frozen at TEST_TIME, to check the layout on the
emulator. build.sh test does this and then writes the normal XML back.

Needs Python 3 and Pillow.
"""

import math
import pathlib
import sys
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
RES = ROOT / "watchface" / "src" / "main" / "res"
DRAWABLE = RES / "drawable"

# --------------------------------------------------------------------- layout

#: Watch Face Format coordinate space. The face is scaled to the display.
SIZE = 450
#: Center and radius of the dial.
C = SIZE / 2
R = SIZE / 2

#: Dial ring at the edge of the face: a dot for every minute, larger at the
#: hours, and a triangle pointing inward at 12, 3, 6 and 9. The ring's
#: radius as a fraction of the screen's; the dot radii and the triangle's
#: width and height in watch face units.
RING = 0.96
MINUTE_DOT = 1.8
HOUR_DOT = 3.2
TRIANGLE = (11.0, 10.0)

#: Hour numerals 1 to 12, orange and upright, inside the ring. Drawn with
#: Varela Round (SIL Open Font License, tools/fonts/), thickened to the
#: reference's stroke weight, with each "1" a plain bar with round ends.
#: Their digit height, the gap between each numeral's outer edge and the
#: ring's hour dots, in watch face units; the stroke width and the space
#: between digits as fractions of the digit height; and how much the font's
#: digits are narrowed, to the reference's proportions.
NUMERALS = dict(height=20.0, gap=9.0, stroke=0.17, tracking=0.08, condense=0.9)
NUMERAL_FONT = ROOT / "tools" / "fonts" / "VarelaRound-Regular.ttf"

#: Hands. Each is a length (a fraction of the radius) and outlines given as
#: (distance, half-width) points down one side, from the tail to the tip,
#: mirrored for the other side. A distance is a fraction of the hand's
#: length from the center (negative for a tail) and a half-width is in
#: watch face units.
#:
#: The hands are measured from the reference face, scaled by 1.43 watch
#: face units per reference pixel, which puts the minute hand's tip just
#: inside the dial ring as in the reference.
#:
#: The hour and minute hands, measured from the 960 px reference and scaled
#: by 0.547 units per pixel (the minute hand's tip sits as close to the dial
#: ring as in the reference). Every edge is a straight line.
#:
#: - outline: its sides run straight from under the hub to the shoulder,
#:   then straight to the point; (distance, half-width) at the hub end, at
#:   the shoulder and at the tip.
#: - insert: the orange, its sides parallel to the outline's, inside the
#:   outline's line, a black gap and its own gray border (`lines`: their
#:   widths). Distances of its flat hub end, its shoulder and its point.
#: - center: a bar down the middle from the hub to the insert, and on from
#:   the insert's point into the hand's: two bright gray lines with a dim
#:   seam between them. Its width and the seam's; the hour hand's is the
#:   thicker.
HOUR_HAND = dict(
    length=0.608,
    outline=((-0.04, 10.1), (0.836, 17.9), (1.0, 0.0)),
    lines=dict(outline=2.6, gap=3.4, border=2.6),
    insert=(0.352, 0.84, 0.902),
    center=dict(width=6.2, seam=1.2),
)
MINUTE_HAND = dict(
    length=0.914,
    outline=((-0.03, 9.25), (0.862, 15.0), (1.0, 0.0)),
    lines=dict(outline=2.4, gap=2.5, border=2.5),
    insert=(0.332, 0.856, 0.910),
    center=dict(width=4.8, seam=1.0),
)
#: The hour and minute hands' colors: the outline, the insert's border, and
#: the center bar's lines and seam, as measured from the reference.
HAND_LINE_COLORS = dict(outline="#333333", border="#373737", center="#4C4C4C",
                        seam="#1E1E1E")
#: The seconds hand: a light gray needle with a blunt end, stopping just
#: inside the dial ring's triangles (at 0.938 of the radius), and a
#: counterweight that widens away from the hub.
SECOND_HAND = dict(
    length=0.92,
    outline=((-0.394, 5.0), (-0.193, 3.6), (-0.096, 2.5), (-0.021, 2.2), (0.0, 1.8),
             (1.0, 1.6)),
)
#: Center hub: a near-black disc with three thin gray rings, (radius, ring width)
#: in watch face units.
HUB_RINGS = ((17.2, 2.1), (13.6, 2.1), (8.6, 2.1))

#: Alpha of the dial marks in always-on mode.
AMBIENT_ALPHA = 154

# --------------------------------------------------------------------- colors

ORANGE = "#FF8000"
#: The hour and minute hands' near-black body, also the hub's fill, and
#: the hub's rings.
HAND_BODY = "#050505"
HAND_EDGE_COLOR = "#363636"
#: The seconds hand.
SECOND_GRAY = "#BCBCBC"
#: The hands' edge in always-on mode, brighter so the outline reads alone.
AMBIENT_EDGE = "#9A9A9A"


def polar(degrees, distance):
    """Point at an angle clockwise from 12 o'clock and a distance from the
    center."""
    a = math.radians(degrees)
    return C + distance * math.sin(a), C - distance * math.cos(a)


def fmt(v):
    """Short number for XML attributes."""
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s == "-0" else s


# ------------------------------------------------------------------ XML tools


def el(parent, tag, **attrs):
    """Add a child element. Attribute values may be numbers."""
    e = ET.SubElement(parent, tag)
    for k, v in attrs.items():
        e.set(k.rstrip("_"), fmt(v) if isinstance(v, float) else str(v))
    return e


def box(cx, cy, w, h):
    """Integer x, y, width, height of a box centered on (cx, cy)."""
    w, h = math.ceil(w), math.ceil(h)
    return {"x": round(cx - w / 2), "y": round(cy - h / 2), "width": w, "height": h}


def ambient_hide(parent):
    """Hide an element in always-on mode."""
    el(parent, "Variant", mode="AMBIENT", target="alpha", value="0")


def ambient_only(parent):
    """Show an element only in always-on mode (its alpha must be 0)."""
    el(parent, "Variant", mode="AMBIENT", target="alpha", value="255")


# ---------------------------------------------------------------- the scene


def dial(scene):
    """The orange ring at the edge of the face: a dot for every minute,
    larger at the hours, and a triangle pointing inward at 12, 3, 6 and 9.
    Dimmed in always-on mode."""
    group = el(scene, "Group", name="dial", x=0, y=0, width=SIZE, height=SIZE)
    el(group, "Variant", mode="AMBIENT", target="alpha", value=AMBIENT_ALPHA)
    draw = el(group, "PartDraw", x=0, y=0, width=SIZE, height=SIZE)
    for i in range(60):
        if i % 15 == 0:
            continue  # a triangle, below
        radius = HOUR_DOT if i % 5 == 0 else MINUTE_DOT
        x, y = polar(i * 6, R * RING)
        dot = el(draw, "Ellipse", x=x - radius, y=y - radius,
                 width=2 * radius, height=2 * radius)
        el(dot, "Fill", color=ORANGE)
    w, h = TRIANGLE
    for i in range(4):
        x, y = polar(i * 90, R * RING)
        tri = el(group, "PartImage", angle=float(i * 90), pivotX=0.5, pivotY=0.5,
                 **box(x, y, w, h))
        el(tri, "Image", resource="marker_triangle")
    numerals = el(group, "PartImage", x=0, y=0, width=SIZE, height=SIZE)
    el(numerals, "Image", resource="numerals")


def hand_parts(clock, kind, resource, angle=None):
    """One hand image, its pivot at the dial center (see render_hand). With
    an angle, a still image at that angle instead of a moving hand."""
    w, top, bottom = HAND_IMAGES[resource]
    b = dict(x=round(C - w / 2), y=round(C - top), width=w, height=top + bottom,
             pivotX=0.5, pivotY=top / (top + bottom))
    if angle is None:
        return el(clock, kind, resource=resource, **b)
    hand = el(clock, "PartImage", angle=float(angle), **b)
    el(hand, "Image", resource=resource)
    return hand


def hub(parent):
    """Center hub over the hands: a near-black disc with three thin gray rings.
    The same in always-on mode."""
    outer = HUB_RINGS[0][0] + HUB_RINGS[0][1]
    b = box(C, C, 2 * outer + 2, 2 * outer + 2)
    draw = el(parent, "PartDraw", name="hub", **b)
    hx, hy = C - b["x"], C - b["y"]
    e = el(draw, "Ellipse", x=hx - outer, y=hy - outer, width=2 * outer, height=2 * outer)
    el(e, "Fill", color=HAND_BODY)
    for radius, width in HUB_RINGS:
        e = el(draw, "Ellipse", x=hx - radius, y=hy - radius,
               width=2 * radius, height=2 * radius)
        el(e, "Stroke", color=HAND_EDGE_COLOR, thickness=width)


def analog_clock(parent, frozen=None):
    """The hour, minute and seconds hands while awake; outlined hour and
    minute hands and no seconds in always-on mode. frozen is an (hour,
    minute, second) to draw the awake hands at instead of the time, for the
    test build."""
    if frozen is None:
        clock = el(parent, "AnalogClock", x=0, y=0, width=SIZE, height=SIZE, name="hands")
        angles = (None, None, None)
    else:
        clock = el(parent, "Group", x=0, y=0, width=SIZE, height=SIZE, name="hands")
        h, m, s = frozen
        angles = ((h % 12) * 30 + m / 2 + s / 120, m * 6 + s / 10, s * 6)
    ambient_hide(clock)
    for kind, resource, angle in zip(("HourHand", "MinuteHand", "SecondHand"),
                                     ("hand_hour", "hand_minute", "hand_second"), angles):
        hand_parts(clock, kind, resource, angle=angle)

    sleep = el(parent, "AnalogClock", x=0, y=0, width=SIZE, height=SIZE,
               name="sleepHands", alpha=0)
    ambient_only(sleep)
    hand_parts(sleep, "HourHand", "hand_hour_ambient")
    hand_parts(sleep, "MinuteHand", "hand_minute_ambient")
    hub(parent)


def watch_face(test=False):
    face = ET.Element("WatchFace", width=str(SIZE), height=str(SIZE))
    el(face, "Metadata", key="CLOCK_TYPE", value="ANALOG")
    # The picker preview's time (the same as the test build).
    h, m, s = TEST_TIME
    el(face, "Metadata", key="PREVIEW_TIME", value=f"{h:02d}:{m:02d}:{s:02d}")
    scene = el(face, "Scene", backgroundColor="#000000")
    dial(scene)
    analog_clock(scene, frozen=TEST_TIME if test else None)
    return face


# ------------------------------------------------------------------- images

#: Pixels per watch face unit in the images. Keep it at 1, about the
#: screen's own size: the runtime rotates the hands with bilinear filtering
#: and no mipmaps, so a larger image shrunk on the way skips pixels and its
#: edges come out wavy (at 4, the insert's edge wandered by 0.8 px).
SCALE = 1
#: Pixels per unit the hands are drawn at, for smooth edges. Each hand is
#: drawn once at this size, scaled down to a master image at MASTER_SCALE
#: (written to build/masters/ for review) and from there to SCALE.
DRAW_SCALE = 32
MASTER_SCALE = 8
MASTERS = ROOT / "build" / "masters"
#: Each hand image's width, and its height above and below the dial center,
#: in watch face units (set by render_hand).
HAND_IMAGES = {}


def rgb(color):
    """(r, g, b, 255) for a #RRGGBB color."""
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


class HandCanvas:
    """A supersampled image of a hand pointing up, the dial center `top`
    units below its top edge, sized to the hand's outline. Points are
    (distance, half-width) as in HOUR_HAND."""

    def __init__(self, name, hand):
        self.name = name
        self.ln = hand["length"] * R
        shape = hand["outline"]
        # Even width, so the image centers on the dial.
        self.w = 2 * math.ceil(max(hw for _, hw in shape) + 1)
        self.top = math.ceil(max(d for d, _ in shape) * self.ln + 1)
        self.bottom = math.ceil(max(0.0, -min(d for d, _ in shape)) * self.ln + 1)
        HAND_IMAGES[name] = (self.w, self.top, self.bottom)
        self.k = DRAW_SCALE
        self.img = Image.new("RGBA", (self.w * self.k, (self.top + self.bottom) * self.k),
                             (0, 0, 0, 0))
        self.draw = ImageDraw.Draw(self.img)

    def y(self, d):
        """Image row of a distance along the hand."""
        return (self.top - d * self.ln) * self.k

    def polygon(self, points):
        """The closed outline of mirrored (distance, half-width) points."""
        cx, k = self.w * self.k / 2, self.k
        left = [(cx - hw * k, self.y(d)) for d, hw in points]
        right = [(cx + hw * k, self.y(d)) for d, hw in reversed(points) if hw > 0]
        return left + right

    def pixels(self, points):
        """Image coordinates of (x, y) points in watch face units, x across
        the hand from its center line and y along it from the dial center."""
        cx, k = self.w * self.k / 2, self.k
        return [(cx + x * k, (self.top - y) * k) for x, y in points]

    def save(self):
        """Scale down to the master image and from it to the watch's."""
        h = self.top + self.bottom
        master = self.img.resize((self.w * MASTER_SCALE, h * MASTER_SCALE), Image.LANCZOS)
        MASTERS.mkdir(parents=True, exist_ok=True)
        master.save(MASTERS / f"{self.name}.png")
        master.resize((self.w * SCALE, h * SCALE), Image.LANCZOS).save(
            DRAWABLE / f"{self.name}.png")


def inset(points, delta):
    """A convex polygon of (x, y) points moved inward by delta on every
    side: each edge shifted along its normal, the corners where the shifted
    edges meet."""
    n = len(points)
    area = sum(points[i][0] * points[(i + 1) % n][1] - points[(i + 1) % n][0] * points[i][1]
               for i in range(n))
    sign = 1 if area > 0 else -1  # inward is to the left of a counterclockwise edge
    lines = []
    for i in range(n):
        (x0, y0), (x1, y1) = points[i], points[(i + 1) % n]
        length = math.hypot(x1 - x0, y1 - y0)
        nx, ny = -(y1 - y0) / length * sign, (x1 - x0) / length * sign
        lines.append(((x0 + nx * delta, y0 + ny * delta), (x1 - x0, y1 - y0)))
    out = []
    for i in range(n):
        (p, r), (q, s) = lines[i - 1], lines[i]
        t = ((q[0] - p[0]) * s[1] - (q[1] - p[1]) * s[0]) / (r[0] * s[1] - r[1] * s[0])
        out.append((p[0] + t * r[0], p[1] + t * r[1]))
    return out


def clip_below(points, y0):
    """The part of a polygon at or above y0 (Sutherland-Hodgman)."""
    out = []
    for i in range(len(points)):
        a, b = points[i - 1], points[i]
        if (a[1] >= y0) != (b[1] >= y0):
            t = (y0 - a[1]) / (b[1] - a[1])
            out.append((a[0] + t * (b[0] - a[0]), y0))
        if b[1] >= y0:
            out.append(b)
    return out


def render_hand(name, hand, ambient=False):
    """An hour or minute hand (see HOUR_HAND), every edge a straight line.
    In always-on mode the body is black and only the lines are drawn, the
    insert outlined in orange."""
    c = HandCanvas(name, hand)
    k, ln = c.k, c.ln
    (d0, hw0), (ds, hws), (dt, _) = hand["outline"]
    outline = [(-hw0, d0 * ln), (-hws, ds * ln), (0.0, dt * ln), (hws, ds * ln), (hw0, d0 * ln)]

    # The orange's sides: the outline's sides moved in by the outline's
    # line, the gap and the border, from the insert's hub end out.
    lines = hand["lines"]
    start, shoulder, tip = (d * ln for d in hand["insert"])
    sides = clip_below(inset(outline, lines["outline"] + lines["gap"] + lines["border"]), start)
    # The orange: those sides out to its own shoulder, then a point; its
    # gray border around it, outside it.
    right = [p for p in sides if p[0] > 1e-6]
    (xa, ya), (xb, yb) = min(right, key=lambda p: p[1]), max(right, key=lambda p: p[0])
    xs = xa + (xb - xa) * min(1.0, (shoulder - ya) / (yb - ya))
    insert = [(-xa, start), (-xs, shoulder), (0.0, tip), (xs, shoulder), (xa, start)]
    border = inset(insert, -lines["border"])

    def width(key):
        """One of the hand's line widths in image pixels."""
        return round(lines[key] * k)

    def center_bar(line, seam):
        """The center bar: from the hub to under the insert, and from under
        the insert's point into the hand's, trimmed to the outline."""
        layer = Image.new("RGBA", c.img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        for half, color in ((hand["center"]["width"] / 2, line),
                            (hand["center"]["seam"] / 2, seam)):
            for y0, y1 in ((d0 * ln, start + 1.0), (tip - 1.0, dt * ln)):
                draw.polygon(c.pixels([(-half, y0), (-half, y1), (half, y1), (half, y0)]),
                             fill=rgb(color))
        mask = Image.new("L", c.img.size, 0)
        ImageDraw.Draw(mask).polygon(c.pixels(outline), fill=255)
        c.img.paste(layer, mask=Image.composite(layer.getchannel("A"), mask, mask))

    if ambient:
        c.draw.polygon(c.pixels(outline), fill=rgb("#000000"))
        center_bar(AMBIENT_EDGE, "#000000")
        c.draw.polygon(c.pixels(border), fill=rgb("#000000"), outline=rgb(ORANGE),
                       width=width("border"))
        c.draw.polygon(c.pixels(outline), outline=rgb(AMBIENT_EDGE), width=width("outline"))
        c.save()
        return

    c.draw.polygon(c.pixels(outline), fill=rgb(HAND_BODY))
    center_bar(HAND_LINE_COLORS["center"], HAND_LINE_COLORS["seam"])
    c.draw.polygon(c.pixels(border), fill=rgb(HAND_LINE_COLORS["border"]))
    c.draw.polygon(c.pixels(insert), fill=rgb(ORANGE))
    c.draw.polygon(c.pixels(outline), outline=rgb(HAND_LINE_COLORS["outline"]),
                   width=width("outline"))
    c.save()


def render_second_hand():
    """The seconds hand: a light gray needle and counterweight."""
    c = HandCanvas("hand_second", SECOND_HAND)
    c.draw.polygon(c.polygon(SECOND_HAND["outline"]), fill=rgb(SECOND_GRAY))
    c.save()


def render_triangle():
    """The dial ring's triangle marker: orange, pointing down (inward at 12),
    with a slightly rounded look from supersampling."""
    w, h = (math.ceil(v) for v in TRIANGLE)
    k = DRAW_SCALE
    img = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
    ImageDraw.Draw(img).polygon([(0, 0), (w * k, 0), (w * k / 2, h * k)],
                                fill=(0xFF, 0x80, 0x00, 255))
    img.resize((w * SCALE, h * SCALE), Image.LANCZOS).save(DRAWABLE / "marker_triangle.png")


def render_label(text, k):
    """An hour numeral's image at k pixels per unit, NUMERALS["height"]
    tall: Varela Round digits thickened to the stroke weight, each "1" a
    bar with round ends."""
    height = NUMERALS["height"] * k
    stroke = NUMERALS["stroke"] * height
    color = rgb(ORANGE)
    # The font's own stem width, from a lowercase l, to thicken by.
    probe = ImageFont.truetype(str(NUMERAL_FONT), 1000)
    box = probe.getbbox("0")
    size = 1000 * height / (box[3] - box[1])
    font = ImageFont.truetype(str(NUMERAL_FONT), round(size))
    lb = font.getbbox("l")
    stem_img = Image.new("L", (lb[2] + 4, lb[3] + 4), 0)
    ImageDraw.Draw(stem_img).text((0, 0), "l", font=font, fill=255)
    row = [stem_img.getpixel((x, (lb[1] + lb[3]) // 2)) for x in range(stem_img.width)]
    stem = sum(row) / 255
    # Thick enough that the upright strokes keep the stroke width once the
    # digits are narrowed.
    grow = max(0, round((stroke / NUMERALS["condense"] - stem) / 2))
    # Smaller so the thickened digits still come out `height` tall.
    font = ImageFont.truetype(str(NUMERAL_FONT), round(size * height / (height + 2 * grow)))

    # Every digit on the same baseline, the label as tall as a "0"; a "1"
    # as tall as a flat-topped "7".
    top, bottom = font.getbbox("0", stroke_width=grow)[1::2]
    flat = font.getbbox("7", stroke_width=grow)
    glyphs = []
    for ch in text:
        if ch == "1":
            g = Image.new("RGBA", (math.ceil(stroke), bottom - top), (0, 0, 0, 0))
            ImageDraw.Draw(g).rounded_rectangle(
                [0, flat[1] - top, g.width - 1, flat[3] - top - 1], radius=stroke / 2,
                fill=color)
        else:
            b = font.getbbox(ch, stroke_width=grow)
            g = Image.new("RGBA", (b[2] - b[0], bottom - top), (0, 0, 0, 0))
            ImageDraw.Draw(g).text((-b[0], -top), ch, font=font, fill=color,
                                   stroke_width=grow, stroke_fill=color)
            g = g.resize((round(g.width * NUMERALS["condense"]), g.height), Image.LANCZOS)
        glyphs.append(g)
    gap = round(NUMERALS["tracking"] * height)
    out = Image.new("RGBA", (sum(g.width for g in glyphs) + gap * (len(glyphs) - 1),
                             bottom - top), (0, 0, 0, 0))
    x = 0
    for g in glyphs:
        out.alpha_composite(g, (x, 0))
        x += g.width + gap
    return out


def render_numerals():
    """The hour numerals, upright, each placed so its outer edge keeps the
    same gap from the ring's hour dots. One face-size image."""
    master = Image.new("RGBA", (SIZE * MASTER_SCALE,) * 2, (0, 0, 0, 0))
    limit = R * RING - HOUR_DOT - NUMERALS["gap"]
    for hour in range(1, 13):
        label = render_label(str(hour), DRAW_SCALE)
        w, h = label.width / DRAW_SCALE, label.height / DRAW_SCALE
        label = label.resize((round(w * MASTER_SCALE), round(h * MASTER_SCALE)), Image.LANCZOS)
        a = math.radians(hour * 30)
        reach = abs(w / 2 * math.sin(a)) + abs(h / 2 * math.cos(a))
        x, y = polar(hour * 30, limit - reach)
        master.alpha_composite(label, (round(x * MASTER_SCALE - label.width / 2),
                                       round(y * MASTER_SCALE - label.height / 2)))
    MASTERS.mkdir(parents=True, exist_ok=True)
    master.save(MASTERS / "numerals.png")
    master.resize((SIZE * SCALE,) * 2, Image.LANCZOS).save(DRAWABLE / "numerals.png")


def render_images():
    DRAWABLE.mkdir(parents=True, exist_ok=True)
    render_triangle()
    render_numerals()
    render_hand("hand_hour", HOUR_HAND)
    render_hand("hand_hour_ambient", HOUR_HAND, ambient=True)
    render_hand("hand_minute", MINUTE_HAND)
    render_hand("hand_minute_ambient", MINUTE_HAND, ambient=True)
    render_second_hand()


#: The test build's time (hour, minute, second), also the picker preview's.
TEST_TIME = (10, 9, 36)


def write_xml(test=False):
    face = watch_face(test)
    ET.indent(face, space="    ")
    out = RES / "raw" / "watchface.xml"
    out.parent.mkdir(parents=True, exist_ok=True)
    body = ET.tostring(face, encoding="unicode")
    note = "Generated by tools/generate.py. Edit that script, not this file."
    if test:
        # No double hyphens: they aren't allowed in an XML comment.
        note = "TEST BUILD with frozen hands (generate.py test option). Don't ship this."
    header = f"<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<!-- {note} -->\n"
    out.write_text(header + body + "\n", encoding="utf-8", newline="\n")


def main():
    test = "--test" in sys.argv[1:]
    render_images()  # first: the XML needs the hand image sizes
    write_xml(test)
    print(f"Wrote {RES / 'raw' / 'watchface.xml'}{' (test build)' if test else ''}"
          f" and the images in {DRAWABLE}")


if __name__ == "__main__":
    main()
