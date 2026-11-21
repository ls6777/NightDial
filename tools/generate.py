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

from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parent.parent
RES = ROOT / "watchface" / "src" / "main" / "res"
DRAWABLE = RES / "drawable"

# --------------------------------------------------------------------- layout

#: Watch Face Format coordinate space. The face is scaled to the display.
SIZE = 450
#: Center and radius of the dial.
C = SIZE / 2
R = SIZE / 2

#: Dial marks, as fractions of the radius: the outer end of every mark, and
#: the length and width of the minute marks, the hour marks and the marks at
#: 12, 3, 6 and 9.
MARK_OUTER = 0.97
MINUTE_MARK = (0.04, 1.5)
HOUR_MARK = (0.10, 4.0)
QUARTER_MARK = (0.14, 6.0)

#: Hands: (length, width at the center, width at the tip), the lengths as
#: fractions of the radius and the widths in watch face units.
HOUR_HAND = (0.52, 9.0, 5.0)
MINUTE_HAND = (0.82, 7.0, 3.5)
#: Seconds hand: tail and tip as fractions of the radius, and its width.
SECOND_HAND = (0.18, 0.90, 2.0)
#: Center hub radius, in watch face units.
HUB_RADIUS = 7

#: Alpha of the dial marks in always-on mode.
AMBIENT_ALPHA = 154

# --------------------------------------------------------------------- colors

WHITE = "#FFFFFF"
GRAY = "#9A9A9A"
MINUTE_GRAY = "#808080"
RED = "#FF3B30"


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
    """A mark for every minute: thin gray minute marks, white hour marks,
    longer at 12, 3, 6 and 9. Dimmed in always-on mode."""
    group = el(scene, "Group", name="dial", x=0, y=0, width=SIZE, height=SIZE)
    el(group, "Variant", mode="AMBIENT", target="alpha", value=AMBIENT_ALPHA)
    draw = el(group, "PartDraw", x=0, y=0, width=SIZE, height=SIZE)
    for i in range(60):
        if i % 15 == 0:
            (length, width), color = QUARTER_MARK, WHITE
        elif i % 5 == 0:
            (length, width), color = HOUR_MARK, WHITE
        else:
            (length, width), color = MINUTE_MARK, MINUTE_GRAY
        x0, y0 = polar(i * 6, R * (MARK_OUTER - length))
        x1, y1 = polar(i * 6, R * MARK_OUTER)
        line = el(draw, "Line", startX=x0, startY=y0, endX=x1, endY=y1)
        el(line, "Stroke", color=color, thickness=width)


def hand_parts(clock, kind, resource, tint=None, angle=None):
    """One hand image, its pivot at the dial center (see render_hand). With
    an angle, a still image at that angle instead of a moving hand."""
    w, top, bottom = HAND_IMAGES[resource]
    b = dict(x=round(C - w / 2), y=round(C - top), width=w, height=top + bottom,
             pivotX=0.5, pivotY=top / (top + bottom))
    if angle is None:
        hand = el(clock, kind, resource=resource, **b)
    else:
        hand = el(clock, "PartImage", angle=float(angle), **b)
        el(hand, "Image", resource=resource)
    if tint:
        hand.set("tintColor", tint)
    return hand


def hub(parent, color, ambient):
    """Center hub over the hands."""
    side = 2 * (HUB_RADIUS + 2)
    b = box(C, C, side, side)
    draw = el(parent, "PartDraw", name="hubSleep" if ambient else "hub", **b)
    if ambient:
        draw.set("alpha", "0")
        ambient_only(draw)
    else:
        ambient_hide(draw)
    hx, hy = C - b["x"], C - b["y"]
    for radius, fill in ((HUB_RADIUS, color), (HUB_RADIUS / 3, "#000000")):
        e = el(draw, "Ellipse", x=hx - radius, y=hy - radius,
               width=2 * radius, height=2 * radius)
        el(e, "Fill", color=fill)


def analog_clock(parent, frozen=None):
    """White hands and a red seconds hand while awake; gray hands and no
    seconds in always-on mode. frozen is an (hour, minute, second) to draw
    the awake hands at instead of the time, for the test build."""
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
    hub(parent, RED, ambient=False)

    sleep = el(parent, "AnalogClock", x=0, y=0, width=SIZE, height=SIZE,
               name="sleepHands", alpha=0)
    ambient_only(sleep)
    hand_parts(sleep, "HourHand", "hand_hour", tint=GRAY)
    hand_parts(sleep, "MinuteHand", "hand_minute", tint=GRAY)
    hub(parent, GRAY, ambient=True)


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

#: Pixels per watch face unit in the images, so they stay sharp on screens
#: larger than the 450-unit coordinate space.
SCALE = 4
#: Supersampling for smooth edges.
SS = 4
#: Each hand image's width, and its height above and below the dial center,
#: in watch face units (set by render_hand and render_second_hand).
HAND_IMAGES = {}


def render_hand(name, length, base, tip):
    """A white tapered hand pointing up, with a rounded tip and a short
    tail, and a 1-unit dark edge so it stands out over the marks. White, so
    the always-on hands can tint it. The center of the dial is `top` units
    below the top of the image."""
    ln = length * R
    tail = base
    w = 2 * math.ceil((base + 4) / 2)  # even, so the image centers on the dial
    top = math.ceil(ln + 2)
    bottom = math.ceil(tail + 2)
    HAND_IMAGES[name] = (w, top, bottom)

    k = SCALE * SS
    W, H = w * k, (top + bottom) * k
    cx = W / 2

    def outline(grow):
        m = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(m)
        bh, th = base / 2 + grow, tip / 2 + grow
        tip_y = (top - ln + tip / 2) * k
        d.polygon([(cx - bh * k, (top + tail) * k), (cx + bh * k, (top + tail) * k),
                   (cx + th * k, tip_y), (cx - th * k, tip_y)], fill=255)
        d.ellipse([cx - th * k, tip_y - th * k, cx + th * k, tip_y + th * k], fill=255)
        return m

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    img.paste((0, 0, 0, 255), mask=outline(1))
    img.paste((255, 255, 255, 255), mask=outline(0))
    img.resize((w * SCALE, (top + bottom) * SCALE), Image.LANCZOS).save(DRAWABLE / f"{name}.png")


def render_second_hand():
    """Red line through the center, from a short tail to near the edge."""
    tail, tip, width = SECOND_HAND[0] * R, SECOND_HAND[1] * R, SECOND_HAND[2]
    w, top, bottom = 4, math.ceil(tip), math.ceil(tail)
    HAND_IMAGES["hand_second"] = (w, top, bottom)
    k = SCALE * SS
    img = Image.new("RGBA", (w * k, (top + bottom) * k), (0, 0, 0, 0))
    ImageDraw.Draw(img).line([(w * k / 2, (top - tip) * k), (w * k / 2, (top + tail) * k)],
                             fill=(0xFF, 0x3B, 0x30, 255), width=round(width * k))
    img.resize((w * SCALE, (top + bottom) * SCALE), Image.LANCZOS).save(
        DRAWABLE / "hand_second.png")


def render_images():
    DRAWABLE.mkdir(parents=True, exist_ok=True)
    render_hand("hand_hour", *HOUR_HAND)
    render_hand("hand_minute", *MINUTE_HAND)
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
