#!/usr/bin/env python3
"""Generate the Night Dial watch face: the Watch Face Format XML and its
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
    """The hour, minute and seconds hands while awake; the hour and minute
    hands with their orange hollowed out, and no seconds, in always-on mode. frozen is an (hour,
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


def bitmap_fonts(face):
    """The weather's image fonts: the condition icons by day and by night,
    one per [WEATHER.CONDITION] value (as text: "0" to "15"), and the
    temperature's characters."""
    fonts = el(face, "BitmapFonts")
    size = round(WEATHER_ICON["size"] * SCALE)
    for family, when in (("weather_icons_day", 0), ("weather_icons_night", 1)):
        font = el(fonts, "BitmapFont", name=family)
        for value, icons in enumerate(WEATHER_CONDITIONS):
            # One character per name, or a word for "10" and up.
            el(font, "Character" if value < 10 else "Word", name=str(value),
               resource=f"weather_{icons[when]}", width=size, height=size)
    for key in TEMPERATURE_COLORS:
        font = el(fonts, "BitmapFont", name=f"weather_temperature{temperature_set(key)}")
        for ch, name in TEMPERATURE_CHARS.items():
            w, h = TEMPERATURE_GLYPHS[name]
            el(font, "Character", name=ch, resource=f"weather_temp{temperature_set(key)}_{name}",
               width=w, height=h)
    # The battery percentage: the orange temperature digits and a "%", and
    # for a low battery the red (hot) ones.
    for low, digits in (("", ""), ("_low", "_hot")):
        font = el(fonts, "BitmapFont", name=f"battery_percent{low}")
        for d in range(10):
            w, h = TEMPERATURE_GLYPHS[str(d)]
            el(font, "Character", name=str(d), resource=f"weather_temp{digits}_{d}",
               width=w, height=h)
        w, h = BATTERY_IMAGES["percent"]
        el(font, "Character", name="%", resource=f"battery_percent{low}", width=w, height=h)
    # The date gauge's day of the month: its gray digits.
    font = el(fonts, "BitmapFont", name="date_digits")
    for ch, (w, h) in DATE_IMAGES["digits"].items():
        el(font, "Character", name=ch, resource=f"date_digit_{ch}", width=w, height=h)


def text_part(parent, y, width, height, align="CENTER", **text):
    """A PartText across the group at y, and its Text."""
    part = el(parent, "PartText", x=0, y=round(y), width=round(width), height=math.ceil(height))
    return el(part, "Text", align=align, **text)


def template(parent, fmt, *expressions):
    """A Template of fmt with a Parameter per expression."""
    t = el(parent, "Template")
    t.text = fmt
    for e in expressions:
        el(t, "Parameter", expression=e)


def weather_height():
    """The weather display's height: the icon, the temperature and the
    condition's name, and the gaps between them."""
    gap1, gap2 = WEATHER["gaps"]
    return (WEATHER_ICON["size"] + gap1 + WEATHER["temperature"] + gap2
            + WEATHER["text"] * 1.4)


def battery(scene, sample=None):
    """The battery level (see BATTERY): the battery with a segment lit per
    20% (rounded up), and the percentage below it, level with the
    temperature; both red below BATTERY_LOW's limit. Hidden in always-on
    mode. sample is a fixed percentage to show instead (see TEST_BATTERY),
    for the test build."""
    level = str(sample) if sample is not None else "[BATTERY_PERCENT]"
    (iw, ih), temp = BATTERY_IMAGES["icon"], WEATHER["temperature"]
    # The percentage's row: the weather's temperature row (see weather).
    cx, cy = SIZE - WEATHER["center"][0], WEATHER["center"][1]
    text_y = round(cy - weather_height() / 2) + WEATHER_ICON["size"] + WEATHER["gaps"][0]
    top = round(text_y - BATTERY["gap"] - ih)
    width = 2 * iw
    group = el(scene, "Group", name="battery", x=round(cx - width / 2), y=top,
               width=width, height=math.ceil(text_y + temp + 1 - top))
    ambient_hide(group)

    # Red below the low limit, orange from it up: the battery images and the
    # percentage's font for each.
    n, limit = BATTERY["segments"], BATTERY_LOW["limit"]
    step = 100 / n
    low = el(group, "Condition")
    el(el(low, "Expressions"), "Expression", name="low").text = f"{level} < {limit}"
    for branch, (lowest, highest), suffix in (
            (el(low, "Compare", expression="low"), (0, battery_segments(limit - 1)), "_low"),
            (el(low, "Default"), (battery_segments(limit), n), "")):
        # The battery: the image with as many segments lit as the level
        # calls for, the fewest by default. Each image's range excludes the
        # others: when the level changes, the runtime moves off a Compare
        # that turns false only to one that turns true, or else to the
        # Default, so overlapping ranges (> 60 still true when > 80 turns
        # false) would leave the Default showing.
        lit = el(branch, "Condition")
        exprs = el(lit, "Expressions")
        images = []
        for k in range(highest, lowest, -1):
            expression = f"{level} > {fmt((k - 1) * step)}"
            if k < highest:
                expression += f" && {level} <= {fmt(k * step)}"
            el(exprs, "Expression", name=f"lit{k}").text = expression
            images.append((el(lit, "Compare", expression=f"lit{k}"), k))
        for b, k in images + [(el(lit, "Default"), lowest)]:
            part = el(b, "PartImage", x=(width - iw) // 2, y=0, width=iw, height=ih)
            el(part, "Image", resource=f"battery{suffix}_{k}")

        # The percentage ("%" as a parameter: a literal one would be a
        # format code).
        t = text_part(branch, text_y - top, width, temp + 1)
        template(el(t, "BitmapFont", family=f"battery_percent{suffix}", size=temp), "%s%s",
                 level, '"%"')


def date_gauge(scene, sample=None):
    """The date gauge (see DATE_GAUGE): the dial, the pointer turned to the
    day of the week, the hub over it and the day of the month below the
    hub. Hidden in always-on mode. sample is a fixed date to show instead
    (see TEST_DATE), for the test build."""
    def d(source):
        """The expression for a date source, or its sample value."""
        return str(sample[source]) if sample else f"[{source}]"

    gx, gy = date_gauge_center()
    size = DATE_IMAGES["dial"]
    b = box(gx, gy, size, size)
    group = el(scene, "Group", name="dateGauge", **b)
    ambient_hide(group)
    cx, cy = gx - b["x"], gy - b["y"]  # the gauge center in the group
    dial = el(group, "PartImage", **box(cx, cy, size, size))
    el(dial, "Image", resource="date_dial")

    # The pointer, its pivot at the gauge center, turned from Sunday's
    # place by a day's step per day ([DAY_OF_WEEK] is 1 for Sunday).
    w, top, bottom = HAND_IMAGES["date_pointer"]
    step = DATE_GAUGE["arc"] / (len(DAY_NAMES) - 1)
    pointer = el(group, "PartImage", x=round(cx - w / 2), y=round(cy - top), width=w,
                 height=top + bottom, pivotX=0.5, pivotY=top / (top + bottom))
    el(pointer, "Image", resource="date_pointer")
    el(pointer, "Transform", target="angle",
       value=f"{fmt(day_angle(0))} + ({d('DAY_OF_WEEK')} - 1) * {fmt(step)}")

    hub_size = DATE_IMAGES["hub"]
    hub_part = el(group, "PartImage", **box(cx, cy, hub_size, hub_size))
    el(hub_part, "Image", resource="date_hub")

    # The day of the month, centered below the hub. Each digit image ends
    # in the digits' spacing, so the box moves right by half of it.
    height = DATE_GAUGE["date"]["height"]
    trailing = NUMERALS["tracking"] * height
    top_y = cy + DATE_GAUGE["hub"][0][0] + DATE_GAUGE["date"]["gap"]
    part = el(group, "PartText", x=round(trailing / 2), y=round(top_y), width=size,
              height=math.ceil(height + 1))
    t = el(part, "Text", align="CENTER")
    template(el(t, "BitmapFont", family="date_digits", size=height), "%s", d("DAY"))


def weather(scene, sample=None):
    """The weather display (see WEATHER): the condition's icon, the
    temperature and the condition's name. Without weather data, the sun
    and "--°" in their place, and no name. Hidden in always-on mode. sample
    is fixed weather to show instead (see TEST_WEATHER), for the test build."""
    def w(source):
        """The expression for a weather data source, or its sample value."""
        return str(sample[source]) if sample else f"[WEATHER.{source}]"

    cx, cy = WEATHER["center"]
    icon, temp, text = WEATHER_ICON["size"], WEATHER["temperature"], WEATHER["text"]
    gap1, gap2 = WEATHER["gaps"]
    line = text * 1.4  # the name's line height
    height = weather_height()
    width = WEATHER["text_width"]
    group = el(scene, "Group", name="weather", x=round(cx - width / 2),
               y=round(cy - height / 2), width=round(width), height=math.ceil(height))
    ambient_hide(group)
    shown = el(group, "Condition")
    el(el(shown, "Expressions"), "Expression", name="available").text = w("IS_AVAILABLE")
    content = el(el(shown, "Compare", expression="available"), "Group", name="weatherShown",
                 x=0, y=0, width=round(width), height=math.ceil(height))
    # No weather data: the sun and "--°".
    none = el(el(shown, "Default"), "Group", name="weatherNone", x=0, y=0,
              width=round(width), height=math.ceil(height))
    sun = el(none, "PartImage", x=round((width - icon) / 2), y=0, width=round(icon),
             height=round(icon))
    el(sun, "Image", resource="weather_clear_day")
    t = text_part(none, icon + gap1, width, temp + 1)
    template(el(t, "BitmapFont", family="weather_temperature", size=temp), "--°")

    # The icon: the day or night set, by the condition's value.
    day = el(content, "Condition")
    el(el(day, "Expressions"), "Expression", name="isDay").text = w("IS_DAY")
    for branch, family in ((el(day, "Compare", expression="isDay"), "weather_icons_day"),
                           (el(day, "Default"), "weather_icons_night")):
        t = text_part(branch, 0, width, icon)
        template(el(t, "BitmapFont", family=family, size=icon), "%s",
                 f"{w('CONDITION')} <= 15 ? {w('CONDITION')} : 0")

    # The temperature, colored by how hot or cold it is (in °F).
    celsius = f'{w("TEMPERATURE_UNIT")} == 1'
    fahrenheit = f"({celsius} ? {w('TEMPERATURE')} * 9 / 5 + 32 : {w('TEMPERATURE')})"
    colored = el(content, "Condition")
    exprs = el(colored, "Expressions")
    el(exprs, "Expression", name="hot").text = f"{fahrenheit} > {TEMPERATURE_LIMITS['hot']}"
    el(exprs, "Expression", name="cold").text = f"{fahrenheit} < {TEMPERATURE_LIMITS['cold']}"
    for branch, key in ((el(colored, "Compare", expression="hot"), "hot"),
                        (el(colored, "Compare", expression="cold"), "cold"),
                        (el(colored, "Default"), "")):
        t = text_part(branch, icon + gap1, width, temp + 1)
        template(el(t, "BitmapFont", family=f"weather_temperature{temperature_set(key)}",
                    size=temp), "%s°%s", w("TEMPERATURE"), f'{celsius} ? "C" : "F"')

    t = text_part(content, icon + gap1 + temp + gap2, width, line, ellipsis="TRUE", maxLines=1)
    template(el(t, "Font", family="SYNC_TO_DEVICE", size=text, color=ORANGE, weight="MEDIUM"),
             "%s", w("CONDITION_NAME"))


def watch_face(test=False):
    face = ET.Element("WatchFace", width=str(SIZE), height=str(SIZE))
    el(face, "Metadata", key="CLOCK_TYPE", value="ANALOG")
    # The picker preview's time (the same as the test build).
    h, m, s = TEST_TIME
    el(face, "Metadata", key="PREVIEW_TIME", value=f"{h:02d}:{m:02d}:{s:02d}")
    bitmap_fonts(face)
    scene = el(face, "Scene", backgroundColor="#000000")
    dial(scene)
    weather(scene, sample=TEST_WEATHER if test else None)
    battery(scene, sample=TEST_BATTERY if test else None)
    date_gauge(scene, sample=TEST_DATE if test else None)
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
    In always-on mode the same hand with the orange hollowed out, leaving
    an orange line as wide as the insert's border around the black."""
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

    c.draw.polygon(c.pixels(outline), fill=rgb(HAND_BODY))
    center_bar(HAND_LINE_COLORS["center"], HAND_LINE_COLORS["seam"])
    c.draw.polygon(c.pixels(border), fill=rgb(HAND_LINE_COLORS["border"]))
    c.draw.polygon(c.pixels(insert), fill=rgb(ORANGE))
    if ambient:
        c.draw.polygon(c.pixels(inset(insert, lines["border"])), fill=rgb(HAND_BODY))
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


def render_glyphs(text, height, color=ORANGE):
    """Each character of text as an image `height` pixels tall, in the hour
    numerals' style (see NUMERALS), all on the same baseline: Varela Round
    thickened and narrowed, each "1" a bar with round ends, "-" a short bar
    and "°" a small ring at the top. In `color` (#RRGGBB)."""
    stroke = NUMERALS["stroke"] * height
    color = rgb(color)
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
        elif ch == "-":
            g = Image.new("RGBA", (math.ceil(0.45 * height), bottom - top), (0, 0, 0, 0))
            mid = (flat[1] + flat[3]) / 2 - top
            ImageDraw.Draw(g).rounded_rectangle(
                [0, mid - stroke / 2, g.width - 1, mid + stroke / 2], radius=stroke / 2,
                fill=color)
        elif ch == "°":
            ring = 0.40 * height
            g = Image.new("RGBA", (math.ceil(ring), bottom - top), (0, 0, 0, 0))
            y = flat[1] - top
            ImageDraw.Draw(g).ellipse([0, y, ring - 1, y + ring - 1], outline=color,
                                      width=round(0.75 * stroke))
        elif ch == "%":
            # A little taller than the digits: drawn whole, then shrunk to
            # their height.
            b = font.getbbox(ch, stroke_width=grow)
            g = Image.new("RGBA", (b[2] - b[0], b[3] - b[1]), (0, 0, 0, 0))
            ImageDraw.Draw(g).text((-b[0], -b[1]), ch, font=font, fill=color,
                                   stroke_width=grow, stroke_fill=color)
            k = (bottom - top) / g.height
            g = g.resize((round(g.width * k * NUMERALS["condense"]), bottom - top),
                         Image.LANCZOS)
        else:
            b = font.getbbox(ch, stroke_width=grow)
            g = Image.new("RGBA", (b[2] - b[0], bottom - top), (0, 0, 0, 0))
            ImageDraw.Draw(g).text((-b[0], -top), ch, font=font, fill=color,
                                   stroke_width=grow, stroke_fill=color)
            g = g.resize((round(g.width * NUMERALS["condense"]), g.height), Image.LANCZOS)
        glyphs.append(g)
    return glyphs


def render_label(text, k, height=None, color=ORANGE):
    """An hour numeral's image at k pixels per unit, `height` units tall
    (NUMERALS["height"] by default), in `color` (see render_glyphs)."""
    height = (height or NUMERALS["height"]) * k
    glyphs = render_glyphs(text, height, color)
    top, bottom = 0, glyphs[0].height
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


# ------------------------------------------------------------- weather icons

#: Weather icons: orange, in the style of the reference sun (a solid disc
#: with thin rays, long and short). Their size in watch face units, and the
#: width of their thin lines as a fraction of the icon's half-size.
WEATHER_ICON = dict(size=44.0, line=0.075)

#: The weather display, left of the center: the condition's icon, the
#: temperature below it and the condition's name below that, all orange and
#: centered on `center`. The temperature's digit height (in the hour
#: numerals' style), the name's font size (the watch's own font), the gaps
#: between the three, and the name's box width, in watch face units. Hidden
#: when the watch has no weather; hidden in always-on mode.
WEATHER = dict(center=(92.0, 225.0), temperature=18.0, text=17.0, gaps=(4.0, 5.0),
               text_width=160.0)
#: The icon for each [WEATHER.CONDITION] value, 0 to 15, by day and by night.
WEATHER_CONDITIONS = (
    ("unknown", "unknown"), ("clear_day", "clear_night"), ("cloudy", "cloudy"),
    ("fog", "fog"), ("heavy_rain", "heavy_rain"), ("heavy_snow", "heavy_snow"),
    ("rain", "rain"), ("snow", "snow"), ("clear_day", "clear_night"),  # 8: sunny
    ("thunderstorm", "thunderstorm"), ("sleet", "sleet"), ("light_snow", "light_snow"),
    ("light_rain", "light_rain"), ("mist", "mist"),
    ("partly_cloudy_day", "partly_cloudy_night"), ("windy", "windy"),
)
#: The temperature's characters and their image names.
TEMPERATURE_CHARS = {**{str(n): str(n) for n in range(10)},
                     "-": "minus", "°": "degree", "F": "f", "C": "c"}
#: Each temperature character's image size in pixels (set by
#: render_temperature_glyphs).
TEMPERATURE_GLYPHS = {}
#: The temperature's colors: red above the hot limit, blue below the cold
#: one, orange between (limits in °F; converted when the watch uses °C).
#: Each color is its own image font: "weather_temperature", then "_hot"
#: and "_cold".
TEMPERATURE_COLORS = {"": ORANGE, "hot": "#FF3B30", "cold": "#3D8BFF"}
TEMPERATURE_LIMITS = dict(hot=90, cold=40)


def temperature_set(key):
    """The image name suffix of a TEMPERATURE_COLORS set: "" or "_hot"."""
    return f"_{key}" if key else ""


class Icon:
    """A weather icon drawn as a grayscale mask, in icon coordinates: -1 to
    1 across and down, the icon's center at 0."""

    def __init__(self):
        self.n = round(WEATHER_ICON["size"] * DRAW_SCALE)
        self.mask = Image.new("L", (self.n, self.n), 0)
        self.draw = ImageDraw.Draw(self.mask)
        self.w = WEATHER_ICON["line"]

    def px(self, x, y):
        return (x + 1) / 2 * self.n, (y + 1) / 2 * self.n

    def size(self, v):
        return v / 2 * self.n

    def disc(self, x, y, r, fill=255):
        (cx, cy), r = self.px(x, y), self.size(r)
        self.draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)

    def line(self, x0, y0, x1, y1, width=None, fill=255):
        """A straight line with round ends."""
        width = width or self.w
        self.draw.line([self.px(x0, y0), self.px(x1, y1)], fill=fill,
                       width=round(self.size(width)))
        for x, y in ((x0, y0), (x1, y1)):
            self.disc(x, y, width / 2, fill)

    def polygon(self, points, fill=255):
        self.draw.polygon([self.px(x, y) for x, y in points], fill=fill)

    def sun(self, x, y, k):
        """The reference sun: a disc and 16 rays, long and short."""
        self.disc(x, y, 0.39 * k)
        for i in range(16):
            a = math.radians(i * 22.5)
            outer = (1.0 if i % 2 == 0 else 0.80) * k
            self.line(x + 0.55 * k * math.sin(a), y - 0.55 * k * math.cos(a),
                      x + outer * math.sin(a), y - outer * math.cos(a))

    def moon(self, x, y, k):
        """A crescent: a disc with an offset disc cut out of it."""
        self.disc(x, y, 0.62 * k)
        self.disc(x + 0.36 * k, y - 0.26 * k, 0.52 * k, fill=0)

    def cloud(self, x, y, k, grow=0.0, fill=255):
        """A cloud: three puffs on a flat-bottomed base. grow widens it on
        every side (for the gap around it)."""
        for cx, cy, r in ((-0.42, 0.10, 0.30), (0.05, -0.12, 0.40), (0.45, 0.12, 0.27)):
            self.disc(x + cx * k, y + cy * k, r * k + grow, fill)
        x0, y0 = self.px(x - 0.72 * k - grow, y - 0.0 * k - grow)
        x1, y1 = self.px(x + 0.72 * k + grow, y + 0.40 * k + grow)
        self.draw.rounded_rectangle([x0, y0, x1, y1], radius=self.size(0.2 * k + grow),
                                    fill=fill)

    def cloud_over(self, x, y, k):
        """A cloud in front of what's already drawn, with a gap around it."""
        self.cloud(x, y, k, grow=self.w * 1.2, fill=0)
        self.cloud(x, y, k)

    def flake(self, x, y, r):
        """A small six-armed snowflake."""
        for i in range(3):
            a = math.radians(i * 60)
            dx, dy = r * math.cos(a), r * math.sin(a)
            self.line(x - dx, y - dy, x + dx, y + dy, width=self.w * 0.9)

    def drops(self, xs, y0, y1):
        """Slanted rain lines under a cloud."""
        for x in xs:
            self.line(x, y0, x - 0.12 * (y1 - y0) / 0.34, y1, width=self.w * 1.2)

    def wind(self, y, x0, x1, r):
        """A wind line ending in a curl."""
        self.line(x0, y, x1, y)
        (cx, cy), rr = self.px(x1, y - r), self.size(r)
        w = round(self.size(self.w))
        self.draw.arc([cx - rr, cy - rr, cx + rr, cy + rr], start=180, end=90, fill=255,
                      width=w)
        self.disc(x1 - r, y - r, self.w / 2)


def weather_icons():
    """The weather icons by name: functions drawing each on an Icon."""
    def clear_day(i): i.sun(0, 0, 0.95)
    def clear_night(i): i.moon(-0.05, 0.05, 1.3)

    def partly_cloudy_day(i):
        i.sun(-0.28, -0.30, 0.62)
        i.cloud_over(0.12, 0.22, 0.85)

    def partly_cloudy_night(i):
        i.moon(-0.30, -0.32, 0.85)
        i.cloud_over(0.12, 0.22, 0.85)

    def cloudy(i):
        i.cloud(0.24, -0.45, 0.62)
        i.cloud_over(-0.08, 0.12, 1.0)

    def precip(i, rain=(), flakes=(), long=False):
        i.cloud(0, -0.28, 0.95)
        if rain:
            i.drops(rain, 0.30, 0.80 if long else 0.62)
        for x, y in flakes:
            i.flake(x, y, 0.13)

    def light_rain(i): precip(i, rain=(-0.15, 0.25))
    def rain(i): precip(i, rain=(-0.35, 0.05, 0.45))
    def heavy_rain(i): precip(i, rain=(-0.50, -0.20, 0.10, 0.40, 0.70), long=True)
    def light_snow(i): precip(i, flakes=((-0.25, 0.52), (0.30, 0.60)))
    def snow(i): precip(i, flakes=((-0.45, 0.50), (0.05, 0.72), (0.50, 0.50)))

    def heavy_snow(i):
        precip(i, flakes=((-0.55, 0.45), (-0.15, 0.62), (0.25, 0.45), (0.62, 0.62),
                          (0.05, 0.88)))

    def sleet(i):
        precip(i, rain=(-0.52, 0.25))
        i.flake(-0.16, 0.60, 0.13)
        i.flake(0.60, 0.60, 0.13)

    def thunderstorm(i):
        i.cloud(0, -0.30, 0.95)
        i.polygon([(0.08, 0.20), (-0.20, 0.60), (0.0, 0.60), (-0.14, 0.95), (0.28, 0.48),
                   (0.07, 0.48), (0.24, 0.20)])

    def fog(i):
        i.cloud(0, -0.35, 0.85)
        for y, x0, x1 in ((0.30, -0.70, 0.70), (0.55, -0.85, 0.55), (0.80, -0.55, 0.85)):
            i.line(x0, y, x1, y, width=i.w * 1.3)

    def mist(i):
        for row, y in enumerate((-0.45, -0.15, 0.15, 0.45)):
            x = -0.85 + (0.18 if row % 2 else 0)
            while x < 0.80:
                i.line(x, y, min(x + 0.42, 0.85), y, width=i.w * 1.3)
                x += 0.62

    def windy(i):
        i.wind(-0.35, -0.85, 0.35, 0.22)
        i.wind(0.05, -0.85, 0.60, 0.20)
        i.wind(0.45, -0.85, 0.15, 0.18)

    def unknown(i):
        font = ImageFont.truetype(str(NUMERAL_FONT), round(i.n * 0.95))
        b = i.draw.textbbox((0, 0), "?", font=font)
        i.draw.text(((i.n - b[2] - b[0]) / 2, (i.n - b[3] - b[1]) / 2), "?", font=font,
                    fill=255)

    return dict(unknown=unknown, clear_day=clear_day, clear_night=clear_night,
                partly_cloudy_day=partly_cloudy_day, partly_cloudy_night=partly_cloudy_night,
                cloudy=cloudy, fog=fog, mist=mist, light_rain=light_rain, rain=rain,
                heavy_rain=heavy_rain, light_snow=light_snow, snow=snow,
                heavy_snow=heavy_snow, sleet=sleet, thunderstorm=thunderstorm, windy=windy)


def render_weather_icons():
    """Each weather icon in orange, as a master and at screen size, and a
    sheet of all of them for review (build/masters/weather_icons.png)."""
    masters = {}
    for name, paint in weather_icons().items():
        icon = Icon()
        paint(icon)
        img = Image.new("RGBA", icon.mask.size, rgb(ORANGE))
        img.putalpha(icon.mask)
        size = WEATHER_ICON["size"]
        master = img.resize((round(size * MASTER_SCALE),) * 2, Image.LANCZOS)
        masters[name] = master
        MASTERS.mkdir(parents=True, exist_ok=True)
        master.save(MASTERS / f"weather_{name}.png")
        master.resize((round(size * SCALE),) * 2, Image.LANCZOS).save(
            DRAWABLE / f"weather_{name}.png")
    # The review sheet: every icon with its name, on black.
    cell = round(WEATHER_ICON["size"] * MASTER_SCALE)
    cols = 6
    rows = math.ceil(len(masters) / cols)
    label = ImageFont.truetype(str(NUMERAL_FONT), cell // 9)
    sheet = Image.new("RGBA", (cols * (cell + 40), rows * (cell + 80)), (0, 0, 0, 255))
    draw = ImageDraw.Draw(sheet)
    for n, (name, img) in enumerate(masters.items()):
        x, y = (n % cols) * (cell + 40) + 20, (n // cols) * (cell + 80) + 20
        sheet.alpha_composite(img, (x, y))
        draw.text((x + cell / 2, y + cell + 30), name.replace("_", " "), font=label,
                  fill=(160, 160, 160, 255), anchor="mm")
    sheet.convert("RGB").save(MASTERS / "weather_icons.png")


def render_temperature_glyphs():
    """The temperature's characters in the hour numerals' style, each with
    the numerals' spacing after it, as masters and at screen size: a set
    per TEMPERATURE_COLORS color."""
    height = WEATHER["temperature"] * DRAW_SCALE
    gap = round(NUMERALS["tracking"] * height)
    for key, color in TEMPERATURE_COLORS.items():
        glyphs = render_glyphs("".join(TEMPERATURE_CHARS), height, color)
        for (ch, name), g in zip(TEMPERATURE_CHARS.items(), glyphs):
            img = Image.new("RGBA", (g.width + gap, g.height), (0, 0, 0, 0))
            img.alpha_composite(g)
            w, h = img.width / DRAW_SCALE, img.height / DRAW_SCALE
            master = img.resize((round(w * MASTER_SCALE), round(h * MASTER_SCALE)),
                                Image.LANCZOS)
            file = f"weather_temp{temperature_set(key)}_{name}.png"
            master.save(MASTERS / file)
            size = (max(1, round(w * SCALE)), round(h * SCALE))
            master.resize(size, Image.LANCZOS).save(DRAWABLE / file)
            TEMPERATURE_GLYPHS[name] = size


# ------------------------------------------------------------------- battery

#: The battery level: an orange battery outline with a terminal nub on the
#: right and a row of segments inside, one per 20%, and the percentage
#: below it in the temperature's digits and size. In watch face units: the
#: body's width and height, its outline's width and corner radius, the nub's
#: width and height, the space between the outline and the segments, the
#: gaps between segments, and the percentage's gap below the battery.
#:
#: On the face it mirrors the weather, right of the center, the percentage
#: level with the temperature. Hidden in always-on mode.
BATTERY = dict(body=(38.0, 18.0), line=2.2, radius=4.0, nub=(3.2, 7.0), pad=1.8,
               segments=5, segment_gap=1.6, gap=5.0)
#: Below this percentage the battery and its percentage are red (the hot
#: temperature's red): the "_low" images and the hot temperature digits.
BATTERY_LOW = dict(limit=20, color=TEMPERATURE_COLORS["hot"])
#: The battery image's size and the "%" image's, in pixels (set by
#: render_battery).
BATTERY_IMAGES = {}


def render_battery_icon(filled, low=False):
    """The battery with `filled` of its segments lit (left first), drawn
    large, as a master image and at screen size: battery_<filled>.png, or
    battery_low_<filled>.png in the low battery's red."""
    k = DRAW_SCALE
    (bw, bh), line, (nw, nh) = BATTERY["body"], BATTERY["line"], BATTERY["nub"]
    margin = 1.0
    w, h = math.ceil(bw + nw + 2 * margin), math.ceil(bh + 2 * margin)
    img = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = rgb(BATTERY_LOW["color"] if low else ORANGE)
    name = f"battery{'_low' if low else ''}_{filled}"
    x0, y0 = (w - bw - nw) / 2, (h - bh) / 2
    draw.rounded_rectangle([x0 * k, y0 * k, (x0 + bw) * k, (y0 + bh) * k],
                           radius=BATTERY["radius"] * k, outline=color, width=round(line * k))
    # The nub, from under the outline's right side out, its outer corners round.
    ny = y0 + (bh - nh) / 2
    draw.rounded_rectangle([(x0 + bw - line) * k, ny * k, (x0 + bw + nw) * k, (ny + nh) * k],
                           radius=nw * 0.55 * k, fill=color, corners=(False, True, True, False))
    # The segments, evenly across the inside.
    n, gap, pad = BATTERY["segments"], BATTERY["segment_gap"], BATTERY["pad"]
    ix, iy = x0 + line + pad, y0 + line + pad
    iw, ih = bw - 2 * (line + pad), bh - 2 * (line + pad)
    sw = (iw - gap * (n - 1)) / n
    for i in range(filled):
        sx = ix + i * (sw + gap)
        draw.rounded_rectangle([sx * k, iy * k, (sx + sw) * k, (iy + ih) * k],
                               radius=0.8 * k, fill=color)
    master = img.resize((w * MASTER_SCALE, h * MASTER_SCALE), Image.LANCZOS)
    MASTERS.mkdir(parents=True, exist_ok=True)
    master.save(MASTERS / f"{name}.png")
    master.resize((w * SCALE, h * SCALE), Image.LANCZOS).save(DRAWABLE / f"{name}.png")
    BATTERY_IMAGES["icon"] = (w * SCALE, h * SCALE)
    return master


def render_battery_percent(low=False):
    """The percentage's "%" in the temperature digits' style and size:
    battery_percent.png, or battery_percent_low.png in the low battery's
    red. Returns the master. Unlike the digits it has no spacing after it:
    it always comes last, and the spacing would shift the centered
    percentage left of the battery above it."""
    height = WEATHER["temperature"] * DRAW_SCALE
    name = f"battery_percent{'_low' if low else ''}"
    img = render_glyphs("%", height, BATTERY_LOW["color"] if low else ORANGE)[0]
    w, h = img.width / DRAW_SCALE, img.height / DRAW_SCALE
    master = img.resize((round(w * MASTER_SCALE), round(h * MASTER_SCALE)), Image.LANCZOS)
    master.save(MASTERS / f"{name}.png")
    size = (round(w * SCALE), round(h * SCALE))
    master.resize(size, Image.LANCZOS).save(DRAWABLE / f"{name}.png")
    BATTERY_IMAGES["percent"] = size
    return master


def battery_segments(level):
    """How many segments are lit at a percentage: one per step, rounded up."""
    return math.ceil(level * BATTERY["segments"] / 100)


def render_battery():
    """The battery icons and the "%", in orange and in the low battery's
    red, each icon for as many segments as a level in its color can light,
    and a review sheet of the battery at several levels with its
    percentage (build/masters/battery.png)."""
    limit = BATTERY_LOW["limit"]
    icons = {n: render_battery_icon(n)
             for n in range(battery_segments(limit), BATTERY["segments"] + 1)}
    low_icons = {n: render_battery_icon(n, low=True)
                 for n in range(battery_segments(limit - 1) + 1)}
    percent, low_percent = render_battery_percent(), render_battery_percent(low=True)
    # The review sheet: the battery over its percentage, at sample levels,
    # built from the master images, on black.
    digits = {str(d): Image.open(MASTERS / f"weather_temp_{d}.png") for d in range(10)}
    digits["%"] = percent
    low_digits = {str(d): Image.open(MASTERS / f"weather_temp_hot_{d}.png") for d in range(10)}
    low_digits["%"] = low_percent
    gap = round(BATTERY["gap"] * MASTER_SCALE)
    samples = (100, 80, 55, 38, 20, 12, 5)
    cells = []
    for level in samples:
        low = level < BATTERY_LOW["limit"]
        icon = (low_icons if low else icons)[battery_segments(level)]
        glyphs = [(low_digits if low else digits)[c] for c in f"{level}%"]
        text_w = sum(g.width for g in glyphs)
        cell = Image.new("RGBA", (max(icon.width, text_w), icon.height + gap + glyphs[0].height),
                         (0, 0, 0, 0))
        cell.alpha_composite(icon, ((cell.width - icon.width) // 2, 0))
        x = (cell.width - text_w) // 2
        for g in glyphs:
            cell.alpha_composite(g, (x, icon.height + gap))
            x += g.width
        cells.append(cell)
    pad = 60
    sheet = Image.new("RGBA", (sum(c.width for c in cells) + pad * (len(cells) + 1),
                               max(c.height for c in cells) + 2 * pad), (0, 0, 0, 255))
    x = pad
    for c in cells:
        sheet.alpha_composite(c, (x, pad))
        x += c.width + pad
    sheet.convert("RGB").save(MASTERS / "battery.png")


# ---------------------------------------------------------------- date gauge

#: The date gauge, in the 1:30 segment, in the reference gauge's colors: a
#: small dial with gray tick marks around its edge, the days of the
#: week, SUN to SAT, upright in gray inside them around an arc open at the
#: bottom, an orange pointer at today's on a light gray hub, and the day of
#: the month in gray below the hub. In watch face units:
#:
#: - distance: the gauge center's distance from the dial center, at 45
#:   degrees.
#: - ticks: (inner radius, length, width) of the tick marks, one at each
#:   day and one between days, from Sunday to Saturday.
#: - labels: the day names' letter height, and the gap between each name's
#:   outer edge and the ticks (placed like the hour numerals).
#: - arc: the days' span in degrees, Sunday at its left end, Saturday at
#:   its right.
#: - pointer: its outline as in SECOND_HAND (distances as fractions of its
#:   length), the reference's: straight sides widening from the hub to a
#:   shoulder at 0.71 of its length, then straight to a sharp point, its
#:   tail hidden under the hub. Like the seconds hand it runs over the day
#:   names, to `gap` short of the ticks.
#: - hub: discs as (radius, color), outermost first, each drawn over the
#:   last: light gray rings with a dark one between, as in the reference.
#: - date: the day of the month's digit height and its gap below the hub.
DATE_GAUGE = dict(
    distance=110.0,
    ticks=(50.0, 4.4, 1.8),
    labels=dict(height=8.0, gap=3.0),
    arc=240.0,
    pointer=dict(gap=2.0, outline=((-0.10, 2.35), (0.0, 2.47), (0.71, 3.33), (1.0, 0.0))),
    hub=((6.0, "#DCDCDC"), (4.5, "#161616"), (3.5, "#BEBEBE"), (2.4, "#8E8E8E"),
         (0.8, "#222222")),
    date=dict(height=16.0, gap=4.0),
)
#: The gauge's gray, for its tick marks, day names and date, as measured
#: from the reference.
GAUGE_GRAY = "#A4A4A4"
DAY_NAMES = ("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT")
#: The date gauge's image sizes and the pointer's length (set by
#: render_date_gauge): "dial" and "hub" (pixels square), "digits" (each
#: digit's (width, height) in pixels) and "pointer" (watch face units).
DATE_IMAGES = {}


def date_gauge_center():
    """The date gauge's center on the face."""
    return polar(45, DATE_GAUGE["distance"])


def day_angle(day):
    """The pointer's angle, clockwise from 12, for a day of the week (0 for
    Sunday to 6 for Saturday)."""
    arc = DATE_GAUGE["arc"]
    return -arc / 2 + day * arc / (len(DAY_NAMES) - 1)


def render_date_dial():
    """The gauge's tick marks and day names: one image the size of the
    gauge, date_dial.png. Returns the master and its size in units."""
    g = DATE_GAUGE
    inner, length, width = g["ticks"]
    size = math.ceil(2 * (inner + length + 1))
    k = DRAW_SCALE
    img = Image.new("RGBA", (size * k,) * 2, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    c = size / 2
    step = g["arc"] / (2 * (len(DAY_NAMES) - 1))
    for i in range(2 * (len(DAY_NAMES) - 1) + 1):
        # A flat-ended bar along the radius: (along, across) corners.
        a = math.radians(-g["arc"] / 2 + i * step)
        ux, uy = math.sin(a), -math.cos(a)
        corners = [(r * ux - t * uy, r * uy + t * ux)
                   for r, t in ((inner, -width / 2), (inner + length, -width / 2),
                                (inner + length, width / 2), (inner, width / 2))]
        draw.polygon([((c + x) * k, (c + y) * k) for x, y in corners], fill=rgb(GAUGE_GRAY))
    # The day names, each with its outer edge `gap` inside the ticks.
    limit = inner - g["labels"]["gap"]
    for day, name in enumerate(DAY_NAMES):
        label = render_label(name, k, g["labels"]["height"], GAUGE_GRAY)
        w, h = label.width / k, label.height / k
        a = math.radians(day_angle(day))
        reach = abs(w / 2 * math.sin(a)) + abs(h / 2 * math.cos(a))
        distance = limit - reach
        x, y = c + distance * math.sin(a), c - distance * math.cos(a)
        img.alpha_composite(label, (round((x - w / 2) * k), round((y - h / 2) * k)))
    DATE_IMAGES["pointer"] = inner - g["pointer"]["gap"]
    master = img.resize((size * MASTER_SCALE,) * 2, Image.LANCZOS)
    MASTERS.mkdir(parents=True, exist_ok=True)
    master.save(MASTERS / "date_dial.png")
    master.resize((size * SCALE,) * 2, Image.LANCZOS).save(DRAWABLE / "date_dial.png")
    DATE_IMAGES["dial"] = size * SCALE
    return master, size


def render_date_pointer():
    """The gauge's pointer: orange, widening from the hub to a point."""
    p = DATE_GAUGE["pointer"]
    c = HandCanvas("date_pointer", dict(length=DATE_IMAGES["pointer"] / R,
                                        outline=p["outline"]))
    c.draw.polygon(c.polygon(p["outline"]), fill=rgb(ORANGE))
    c.save()


def render_date_hub():
    """The gauge's hub, drawn large: date_hub.png. Returns the master."""
    size = 2 * math.ceil(DATE_GAUGE["hub"][0][0] + 1)
    k = DRAW_SCALE
    img = Image.new("RGBA", (size * k,) * 2, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    c = size * k / 2
    for radius, color in DATE_GAUGE["hub"]:
        r = radius * k
        draw.ellipse([c - r, c - r, c + r, c + r], fill=rgb(color))
    master = img.resize((size * MASTER_SCALE,) * 2, Image.LANCZOS)
    master.save(MASTERS / "date_hub.png")
    master.resize((size * SCALE,) * 2, Image.LANCZOS).save(DRAWABLE / "date_hub.png")
    DATE_IMAGES["hub"] = size * SCALE
    return master


def render_date_digits():
    """The date's digits in the hour numerals' style, gray, each with the
    numerals' spacing after it: date_digit_<n>.png. Returns the masters."""
    height = DATE_GAUGE["date"]["height"] * DRAW_SCALE
    gap = round(NUMERALS["tracking"] * height)
    masters = []
    DATE_IMAGES["digits"] = {}
    for d, g in enumerate(render_glyphs("0123456789", height, GAUGE_GRAY)):
        img = Image.new("RGBA", (g.width + gap, g.height), (0, 0, 0, 0))
        img.alpha_composite(g)
        w, h = img.width / DRAW_SCALE, img.height / DRAW_SCALE
        master = img.resize((round(w * MASTER_SCALE), round(h * MASTER_SCALE)), Image.LANCZOS)
        master.save(MASTERS / f"date_digit_{d}.png")
        size = (round(w * SCALE), round(h * SCALE))
        master.resize(size, Image.LANCZOS).save(DRAWABLE / f"date_digit_{d}.png")
        DATE_IMAGES["digits"][str(d)] = size
        masters.append(master)
    return masters


def render_date_gauge():
    """The date gauge's images, and a review sheet of the gauge on Friday
    the 20th (build/masters/date_gauge.png)."""
    dial, size = render_date_dial()
    render_date_pointer()
    hub = render_date_hub()
    digits = render_date_digits()
    # The review sheet, from the masters: the dial, the pointer at Friday,
    # the hub and the date, on black.
    k = MASTER_SCALE
    pad = 8 * k
    sheet = Image.new("RGBA", (dial.width + 2 * pad,) * 2, (0, 0, 0, 255))
    sheet.alpha_composite(dial, (pad, pad))
    cx = cy = pad + size / 2 * k
    w, top, _ = HAND_IMAGES["date_pointer"]
    layer = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
    layer.alpha_composite(Image.open(MASTERS / "date_pointer.png"),
                          (round(cx - w * k / 2), round(cy - top * k)))
    sheet.alpha_composite(layer.rotate(-day_angle(5), resample=Image.BICUBIC, center=(cx, cy)))
    sheet.alpha_composite(hub, (round(cx - hub.width / 2), round(cy - hub.height / 2)))
    shown = [digits[2], digits[0]]
    trailing = NUMERALS["tracking"] * DATE_GAUGE["date"]["height"] * k
    x = round(cx - (sum(d.width for d in shown) - trailing) / 2)
    y = round(cy + (DATE_GAUGE["hub"][0][0] + DATE_GAUGE["date"]["gap"]) * k)
    for d in shown:
        sheet.alpha_composite(d, (x, y))
        x += d.width
    sheet.convert("RGB").save(MASTERS / "date_gauge.png")


def render_images():
    DRAWABLE.mkdir(parents=True, exist_ok=True)
    render_triangle()
    render_numerals()
    render_weather_icons()
    render_temperature_glyphs()
    render_battery()
    render_date_gauge()
    render_hand("hand_hour", HOUR_HAND)
    render_hand("hand_hour_ambient", HOUR_HAND, ambient=True)
    render_hand("hand_minute", MINUTE_HAND)
    render_hand("hand_minute_ambient", MINUTE_HAND, ambient=True)
    render_second_hand()


#: The test build's time (hour, minute, second), also the picker preview's.
TEST_TIME = (10, 9, 36)
#: The test build's weather, in place of the watch's (the emulator often
#: has none): the WEATHER data sources' values, unit 1 being Celsius.
TEST_WEATHER = dict(IS_AVAILABLE=1, IS_DAY=1, CONDITION=1, TEMPERATURE=72,
                    TEMPERATURE_UNIT=0, CONDITION_NAME='"Clear Sky"')
#: The test build's battery percentage, in place of the watch's.
TEST_BATTERY = 80
#: The test build's date, in place of the watch's: Friday the 20th
#: ([DAY_OF_WEEK] is 1 for Sunday).
TEST_DATE = dict(DAY_OF_WEEK=6, DAY=20)


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
