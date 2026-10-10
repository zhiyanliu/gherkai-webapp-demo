#!/usr/bin/env python3
"""Render the final demo-video visual system from archived recordings.

Requires Pillow, numpy, FFmpeg and the bundled Playwright/xterm runtime.
Terminal frames come from an actual ANSI replay, with readable holds and
magnified screenshot regions. Original recordings and the Deck remain unchanged.
"""

from __future__ import annotations

import io
import json
import math
import re
import subprocess
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from media_paths import BUILD, ROOT, RECORDING, SOURCE as SOURCES, DECK, FFMPEG, NODE, RUNTIME_MODULES

WORK = BUILD / "terminal-focus"
CN = "/System/Library/Fonts/Hiragino Sans GB.ttc"
EN = "/System/Library/Fonts/Supplemental/Arial.ttf"
EN_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
MONO = "/System/Library/Fonts/Menlo.ttc"
W, H = 1920, 1080
WINDOW = (144, 108, 1776, 950)
BROWSER = (270, 166, 1652, 942)
TERMINAL_BG = "#09130F"
HIGHLIGHT_BAR_WIDTH = 9
C = {
    "ink": "#253353", "muted": "#536783", "quiet": "#647797",
    "purple": "#7338BE", "cyan": "#067C94", "red": "#B22D50",
    "green": "#16785B", "line": "#ABBAD8", "surface": "#EEF3FC",
    "body": "#F8FAFF", "lavender": "#EDE7F9",
}


def font(size: int, *, bold=False, mono=False, latin=False):
    if mono:
        return ImageFont.truetype(MONO, size)
    if latin:
        return ImageFont.truetype(EN_BOLD if bold else EN, size)
    return ImageFont.truetype(CN, size, index=2 if bold else 0)


def text(im, xy, value, size=26, fill=None, bold=False, mono=False, latin=False):
    ImageDraw.Draw(im).text(
        xy, value, font=font(size, bold=bold, mono=mono, latin=latin),
        fill=fill or C["ink"], anchor="lt",
    )


def pill(im, xy, label, width, color=None, fill="#F0F3FF", size=21, height=38):
    x, y = xy
    ImageDraw.Draw(im).rounded_rectangle(
        (x, y, x + width, y + height), radius=height // 2, fill=fill,
    )
    f = font(size, bold=True)
    tx = x + (width - f.getlength(label)) / 2
    text(im, (tx, y + (height - size) / 2 - 1), label, size, color or C["cyan"], True)


def icon(im, kind, x, y, color, size=26):
    scale = 4
    glyph = Image.new("RGBA", (size * scale, size * scale))
    d = ImageDraw.Draw(glyph)
    k = size * scale / 26
    point = lambda x, y: (round(x * k), round(y * k))
    stroke = max(1, round(1.9 * k))
    if kind == "browser":
        d.rounded_rectangle((*point(2, 3), *point(24, 23)), round(3 * k),
                            outline=color, width=stroke)
        d.line([point(3, 9), point(23, 9)], fill=color, width=stroke)
        for dx in [6, 10]:
            d.ellipse((*point(dx, 5.5), *point(dx + 1, 6.5)), fill=color)
    elif kind == "terminal":
        d.line([point(3, 5), point(10, 12), point(3, 19)], fill=color,
               width=stroke, joint="curve")
        d.line([point(14, 20), point(24, 20)], fill=color, width=stroke)
    else:
        raise ValueError(f"Unknown demo surface: {kind}")
    glyph = glyph.resize((size, size), Image.Resampling.LANCZOS)
    im.paste(glyph, (round(x), round(y)), glyph)


def window_chrome(im, box, kind, title, *, detail=None, main=False, body_fill=None):
    """Smooth glass-tinted chrome with shared optical alignment and hierarchy."""
    x1, y1, x2, y2 = box
    width, height = x2 - x1, y2 - y1
    supersample = 3
    bar_height = 56 if main else 44
    radius = 18 if main else 11
    sw, sh = width * supersample, height * supersample
    pane = Image.new("RGBA", (sw, sh), body_fill or C["body"])
    xx = np.linspace(0, 1, sw)
    stops = np.array([[221, 207, 245], [214, 226, 245], [197, 231, 235]])
    if not main:
        stops = np.array([[230, 220, 247], [224, 234, 247], [208, 235, 238]])
    gradient = np.stack([np.interp(xx, [0, .53, 1], stops[:, channel])
                        for channel in range(3)], axis=1)
    # A small vertical light falloff adds depth without a hard bottom rule.
    tint = np.broadcast_to(gradient, (bar_height * supersample, sw, 3)).copy()
    sheen = np.linspace(.14, 0, bar_height * supersample)[:, None, None]
    tint = tint * (1 - sheen) + 255 * sheen
    pane.paste(Image.fromarray(tint.astype(np.uint8)), (0, 0))
    d = ImageDraw.Draw(pane)
    s = supersample

    def centered(value, x, center_y, size, color, bold=False):
        f = font(size * s, bold=bold)
        bounds = d.textbbox((0, 0), value, font=f, anchor="lt")
        y = center_y * s - (bounds[3] - bounds[1]) / 2
        d.text((round(x * s), round(y)), value, font=f, fill=color, anchor="lt")
        return f.getlength(value) / s

    if main:
        chip = (20, 11, 154, 45)
        d.rounded_rectangle(tuple(round(v * s) for v in chip), 9 * s,
                            fill=(255, 255, 255, 255))
        label = {"browser": "浏览器", "terminal": "终端"}[kind]
        label_width = font(19 * s, bold=True).getlength(label) / s
        group_width = 22 + 9 + label_width
        left = chip[0] + (chip[2] - chip[0] - group_width) / 2
        icon(pane, kind, left * s, 17 * s, "#6B56A6", 22 * s)
        centered(label, left + 31, 28, 19, "#64528F", True)
        title_end = 178 + centered(title, 178, 28, 22, "#354764")
        detail = detail or ""
        detail_size = 17
        available = width - 26 - title_end - 34
        while detail_size > 14 and font(detail_size * s).getlength(detail) / s + 26 > available:
            detail_size -= 1
        detail_width = font(detail_size * s).getlength(detail) / s + 26
        detail_x = width - 26 - detail_width
        assert title_end + 32 < detail_x, "Window title overlaps its metadata."
        d.rounded_rectangle((round(detail_x * s), 14 * s,
                             (width - 26) * s, 42 * s), 8 * s,
                            fill=(255, 255, 255, 255))
        centered(detail, detail_x + 13, 28, detail_size, "#586D88")
    else:
        icon(pane, kind, 18 * s, 12 * s, "#7E72A4", 20 * s)
        centered(title, 50, 22, 20, "#59647D")

    mask = Image.new("L", (sw, sh))
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, sw - 1, sh - 1), radius * s, fill=255)
    pane.putalpha(mask)
    edge = Image.new("RGBA", pane.size)
    ImageDraw.Draw(edge).rounded_rectangle(
        (s // 2, s // 2, sw - 1 - s // 2, sh - 1 - s // 2),
        radius * s, outline=(255, 255, 255, 190) if main else (205, 216, 233, 160),
        width=s,
    )
    pane.alpha_composite(edge)
    pane = pane.resize((width, height), Image.Resampling.LANCZOS)
    im.alpha_composite(pane, (x1, y1))


def background():
    yy, xx = np.mgrid[0:H, 0:W]
    base = np.zeros((H, W, 3), dtype=np.float32)
    weights = np.zeros((H, W, 1), dtype=np.float32)
    for x, y, spread, color in [
        (-120, -120, 830, (164, 125, 230)),
        (910, -180, 800, (156, 187, 248)),
        (2010, 200, 800, (92, 199, 216)),
        (-100, 1160, 950, (214, 176, 232)),
        (1340, 1170, 950, (172, 228, 237)),
    ]:
        weight = np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / spread**2)
        base += weight[:, :, None] * color
        weights += weight[:, :, None]
    im = Image.fromarray(np.clip(base / weights, 0, 255).astype(np.uint8)).convert("RGBA")
    grid = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(grid)
    for x in range(0, W, 80):
        d.line((x, 0, x, H), fill=(255, 255, 255, 14), width=1)
    for y in range(0, H, 80):
        d.line((0, y, W, y), fill=(255, 255, 255, 14), width=1)
    im.alpha_composite(grid)
    return im


def corner_ribbon(im):
    """A corner strap stays clear of the window and its title bar."""
    band = Image.new("RGBA", (500, 66))
    d = ImageDraw.Draw(band)
    for x in range(band.width):
        k = x / (band.width - 1)
        color = tuple(round(a * (1 - k) + b * k)
                       for a, b in zip((114, 52, 180), (27, 122, 177)))
        d.line((x, 0, x, 65), fill=color)
    d.line((0, 2, 500, 2), fill=(255, 255, 255, 110), width=1)
    d.line((0, 63, 500, 63), fill=(255, 255, 255, 70), width=1)
    label = "DEMO · 实操"
    f = font(27, bold=True)
    text(band, ((500 - f.getlength(label)) / 2, 18), label, 27, "white", True)
    rotated = band.rotate(-45, resample=Image.Resampling.BICUBIC, expand=True)
    layer = Image.new("RGBA", im.size)
    layer.paste(rotated, (1820 - rotated.width // 2, 85 - rotated.height // 2))
    shadow = Image.new("RGBA", im.size, (39, 42, 95, 0))
    shadow.putalpha(layer.getchannel("A").filter(ImageFilter.GaussianBlur(7)).point(lambda x: x // 4))
    im.alpha_composite(shadow)
    im.alpha_composite(layer)


@lru_cache(maxsize=16)
def workflow_icon(name, color, size):
    """Rasterize the Deck's Lucide vectors once for each size and state."""
    source = Path(__file__).parent / "assets/icons" / f"{name}.svg"
    svg = re.sub(r'stroke="[^"]+"', f'stroke="{color}"', source.read_text())
    sharp = str(RUNTIME_MODULES / "sharp")
    script = """const fs = require('fs');
const sharp = require(process.argv[1]);
sharp(fs.readFileSync(0), {density: 288})
  .resize(Number(process.argv[2]), Number(process.argv[2]))
  .png().toBuffer().then(buffer => process.stdout.write(buffer))
  .catch(error => { console.error(error); process.exitCode = 1; });
"""
    result = subprocess.run(
        [NODE, "-e", script, sharp, str(size)], input=svg.encode(),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    )
    return Image.open(io.BytesIO(result.stdout)).convert("RGBA")


def workflow_chevrons(im, current=3):
    """A readable five-stage navigator, with one active stage."""
    scale, width, height = 3, 1632, 44
    strip = Image.new("RGBA", (width * scale, height * scale))
    labels = ["01 需求", "02 用例", "03 本机执行", "04 失败反馈", "05 云端复验"]
    symbols = ["flag-triangle-right", "list-checks", "square-terminal",
               "file-search", "cloud-cog"]
    for index, label in enumerate(labels):
        x, cell_width, tip = index * 324, 336, 18
        points = [(x, 0), (x + cell_width - tip, 0), (x + cell_width, height / 2),
                  (x + cell_width - tip, height), (x, height)]
        if index == len(labels) - 1:
            points = [(x, 0), (x + cell_width, 0),
                      (x + cell_width, height), (x, height)]
        if index:
            points.append((x + tip, height / 2))
        mask = Image.new("L", strip.size)
        ImageDraw.Draw(mask).polygon([(round(px * scale), round(py * scale)) for px, py in points],
                                     fill=255)
        active = index == current
        start, end = ((126, 78, 201), (85, 113, 197)) if active else ((240, 241, 252), (216, 234, 244))
        gradient = Image.new("RGBA", strip.size)
        gd = ImageDraw.Draw(gradient)
        for column in range(x * scale, (x + cell_width) * scale + 1):
            k = (column / scale - x) / cell_width
            color = tuple(round(a * (1 - k) + b * k) for a, b in zip(start, end))
            gd.line((column, 0, column, height * scale), fill=color)
        gradient.putalpha(mask)
        strip.alpha_composite(gradient)
        d = ImageDraw.Draw(strip)
        f = font(21 * scale, bold=active)
        bounds = d.textbbox((0, 0), label, font=f, anchor="lt")
        color = "#FFFFFF" if active else "#52637F"
        icon_size, gap = 23 * scale, 10 * scale
        group_width = icon_size + gap + f.getlength(label)
        gx = round((x + cell_width / 2) * scale - group_width / 2)
        glyph = workflow_icon(symbols[index], color, icon_size)
        strip.alpha_composite(glyph, (gx, round((height * scale - icon_size) / 2)))
        tx = gx + icon_size + gap
        ty = height * scale / 2 - (bounds[3] - bounds[1]) / 2
        d.text((round(tx), round(ty)), label, font=f,
               fill=color, anchor="lt")
    im.alpha_composite(strip.resize((width, height), Image.Resampling.LANCZOS), (144, 1018))


def selection_band(im, box, *, accent="#FF88A4", fill="#683449"):
    """Lighten a terminal row with a flush left-edge marker, preserving ink."""
    x1, y1, x2, y2 = [round(value) for value in box]
    original = im.crop((x1, y1, x2, y2)).convert("RGB")
    tinted = ImageChops.screen(original, Image.new("RGB", original.size, fill))
    im.paste(tinted, (x1, y1))
    marker = Image.new("RGBA", (HIGHLIGHT_BAR_WIDTH, y2 - y1), accent)
    im.alpha_composite(marker, (x1 - HIGHLIGHT_BAR_WIDTH, y1))


def focus_label(im, center_x, y, label, color, *, passed=False):
    """Filled annotation tag, aligned directly beneath its target, without a leader."""
    s, height = 3, 46
    f = font(24 * s, bold=True)
    width = round(f.getlength(label) / s) + 72
    tag = Image.new("RGBA", (width * s, height * s))
    d = ImageDraw.Draw(tag)
    d.rounded_rectangle((0, 0, width * s - 1, height * s - 1), 12 * s, fill=color)
    cx, cy = 25 * s, 23 * s
    d.ellipse((cx - 12 * s, cy - 12 * s, cx + 12 * s, cy + 12 * s), fill="white")
    if passed:
        d.line([(cx - 6 * s, cy), (cx - 1 * s, cy + 5 * s), (cx + 7 * s, cy - 5 * s)],
               fill=color, width=3 * s, joint="curve")
    else:
        d.rounded_rectangle((cx - s, cy - 7 * s, cx + s, cy + 2 * s), s, fill=color)
        d.ellipse((cx - s, cy + 5 * s, cx + s, cy + 7 * s), fill=color)
    bounds = d.textbbox((0, 0), label, font=f, anchor="lt")
    d.text((48 * s, round((height * s - bounds[3] + bounds[1]) / 2)),
           label, font=f, fill="white", anchor="lt")
    tag = tag.resize((width, height), Image.Resampling.LANCZOS)
    im.alpha_composite(tag, (round(center_x - width / 2), y))


def shared_frame(kind, title, footer, detail, *, chapter="04 / 失败反馈",
                 takeaway="让失败依据进入下一轮", body_fill=None):
    im = background()
    text(im, (144, 29), "gherkai", 37, bold=True, latin=True)
    text(im, (320, 40), "github.com/zhiyanliu/gherkai", 22, C["muted"], mono=True)
    assert font(25, bold=True).getlength(takeaway) < 645, "Takeaway overlaps the ribbon."
    text(im, (1040, 39), takeaway, 25, C["ink"], bold=True)
    # Match the Deck's header divider height and vertical position, using the
    # demo frame's margins and a deeper teal–indigo–violet gradient.
    stops = np.array([[22, 121, 159], [80, 97, 202], [132, 77, 183]])
    xx = np.linspace(0, 1, WINDOW[2] - WINDOW[0])
    gradient = np.stack([np.interp(xx, [0, .5, 1], stops[:, channel])
                         for channel in range(3)], axis=1)
    rule = Image.fromarray(np.broadcast_to(gradient, (4, len(xx), 3)).astype(np.uint8))
    im.paste(rule, (WINDOW[0], 84))
    glow = Image.new("RGBA", im.size)
    gd = ImageDraw.Draw(glow)
    gd.rounded_rectangle((144, 118, 1776, 960), 20, fill=(47, 65, 115, 48))
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(13)))
    window_chrome(im, WINDOW, kind, title, detail=detail, main=True, body_fill=body_fill)
    pill(im, (144, 968), "观察点", 108, size=21, height=35)
    text(im, (270, 970), footer, 25)
    stage = int(chapter.split("/", 1)[0].strip()) - 1
    assert 0 <= stage < 5, "Demo chapter must match a workflow stage."
    workflow_chevrons(im, current=stage)
    corner_ribbon(im)
    return im


def extract_frame(source: Path, seconds: float):
    data = subprocess.check_output([
        FFMPEG, "-hide_banner", "-loglevel", "error", "-ss", str(seconds),
        "-i", str(source), "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-",
    ])
    return Image.open(io.BytesIO(data)).convert("RGB")




def cast_text(path):
    events = [json.loads(line) for line in path.read_text().splitlines()][1:]
    value = "".join(event[2] for event in events)
    return re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", value).splitlines()


def terminal_frame():
    source = SOURCES / "fault/explain.cast"
    lines = cast_text(source)
    command = lines[0].split("$ ", 1)[1]
    metadata = json.loads((WORK / "terminal-grid.json").read_text())
    grid = metadata["grid"]
    screenshot = Image.open(WORK / "terminal-output-grid.png").convert("RGB")
    row = grid["failure"] - grid["viewportY"]
    cell_w, row_h = screenshot.width / grid["cols"], screenshot.height / grid["rows"]
    scale = min(1570 / screenshot.width, 762 / screenshot.height)
    size = (round(screenshot.width * scale), round(screenshot.height * scale))
    position = ((W - size[0]) // 2, 176)
    for filename, source_image in [
        ("terminal-command.png", "terminal-command-grid.png"),
        ("terminal-overview.png", "terminal-output-grid.png"),
    ]:
        im = shared_frame(
            "terminal", "gherkai explain · 查看失败依据",
            "在执行结果中定位得分检查，再展开失败原因",
            "本机 · Midscene",
            body_fill=TERMINAL_BG,
        )
        im.paste(Image.open(WORK / source_image).resize(size, Image.Resampling.LANCZOS), position)
        if filename == "terminal-overview.png":
            box = (position[0],
                   round(position[1] + row * row_h * scale),
                   position[0] + size[0],
                   round(position[1] + (row + 1) * row_h * scale))
            selection_band(im, box)
        im.convert("RGB").save(WORK / filename)

    im = shared_frame(
        "terminal", "gherkai explain · 定格查看失败区域",
        "得分检查失败，返回的原因包含期望值与实际值",
        "本机 · Midscene",
        body_fill=TERMINAL_BG,
    )
    # Keep the actual invocation visible while its result is enlarged below.
    text(im, (205, 185), "$ " + command, 21, "#91E0B1", mono=True)
    crop_scale = 0.76
    regions = [
        {"name": "failed-step", "box": [round(8 * cell_w), round((row - 2) * row_h),
                                       round(66 * cell_w), round((row + 1) * row_h)],
         "position": [215, 305]},
        {"name": "failure-message", "box": [round(8 * cell_w), round((row + 1) * row_h),
                                          round(grid["messagePrefixEndPx"] * screenshot.width / grid["width"]),
                                          round((row + 2) * row_h)],
         "position": [215, 604]},
    ]
    for region in regions:
        crop = screenshot.crop(region["box"])
        crop = crop.resize((round(crop.width * crop_scale), round(crop.height * crop_scale)),
                           Image.Resampling.LANCZOS)
        im.paste(crop, tuple(region["position"]))
        x, y = region["position"]
        top = y + round(2 * row_h * crop_scale) if region["name"] == "failed-step" else y
        selection_band(im, (x - 2, top - 3, x + crop.width + 2, y + crop.height + 3))
    pill(im, (205, 232), "失败步", 110, color="white", fill="#CF3E6B", size=23, height=39)
    pill(im, (205, 528), "返回原因", 140, color="white", fill="#CF3E6B", size=23, height=39)
    text(im, (211, 747), "同一次输出中，点击与进度检查通过，得分检查失败。", 29, "#AFCCBB")
    im.convert("RGB").save(WORK / "terminal.png")
    return {
        "source": str(source.relative_to(RECORDING)), "command": command,
        "capture": "terminal-grid.json", "focus_regions": regions,
        "focus_image_scale": crop_scale,
        "method": "Original ANSI terminal replay, overview, then magnified image crops; no re-typeset CLI output.",
    }




def still_clip(source, destination, seconds):
    subprocess.run([
        FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
        "-loop", "1", "-framerate", "25", "-i", str(source), "-t", str(seconds),
        "-an", "-vf", "scale=1920:1080,setsar=1", "-c:v", "libx264",
        "-preset", "fast", "-crf", "18", "-r", "25", "-pix_fmt", "yuv420p", str(destination),
    ], check=True)


def flip_clip(outgoing, incoming, destination, *, reverse=False):
    """One short perspective half-turn marks a change of viewing mode."""
    front = Image.open(outgoing).convert("RGBA")
    back = Image.open(incoming).convert("RGBA")
    backdrop = background()
    source_points = [(0, 0), (W, 0), (W, H), (0, H)]
    frames = []
    for index in range(11):
        if index in (0, 10):
            frames.append((front if index == 0 else back).convert("RGB"))
            continue
        theta = math.pi * index / 10
        angle = theta if theta < math.pi / 2 else theta - math.pi
        if reverse:
            angle *= -1
        canvas = backdrop.copy()
        if abs(math.cos(angle)) < 0.001:
            ImageDraw.Draw(canvas).line((W // 2, 20, W // 2, H - 20), fill=C["purple"], width=3)
        else:
            points = []
            for x, y in source_points:
                x, y = x - W / 2, y - H / 2
                perspective = (3 * W) / (3 * W + x * math.sin(angle))
                points.append((W / 2 + x * math.cos(angle) * perspective,
                               H / 2 + y * perspective))
            matrix, values = [], []
            for (x, y), (u, v) in zip(points, source_points):
                matrix.extend([[x, y, 1, 0, 0, 0, -u * x, -u * y],
                               [0, 0, 0, x, y, 1, -v * x, -v * y]])
                values.extend([u, v])
            coefficients = np.linalg.solve(np.array(matrix), np.array(values))
            image = front if theta < math.pi / 2 else back
            image = ImageEnhance.Brightness(image).enhance(1 - 0.13 * abs(math.sin(angle)))
            warped = image.transform((W, H), Image.Transform.PERSPECTIVE,
                                     tuple(coefficients), Image.Resampling.BICUBIC)
            mask = Image.new("L", (W, H))
            ImageDraw.Draw(mask).polygon(points, fill=255)
            shadow = Image.new("RGBA", (W, H), (31, 48, 88, 0))
            shadow.putalpha(mask.filter(ImageFilter.GaussianBlur(20)).point(lambda x: x // 6))
            canvas.alpha_composite(shadow)
            canvas.alpha_composite(warped)
        frames.append(canvas.convert("RGB"))

    process = subprocess.Popen([
        FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", "25", "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p", str(destination),
    ], stdin=subprocess.PIPE)
    for frame in frames:
        process.stdin.write(frame.tobytes())
    process.stdin.close()
    if process.wait():
        raise RuntimeError("Could not encode the mode-switch animation.")
    if not reverse:
        strip = Image.new("RGB", (1920, 624), "#E9EDF7")
        for slot, index in enumerate([0, 2, 4, 6, 8, 10]):
            x, y = (slot % 3) * 640, (slot // 3) * 312
            text(strip, (x + 14, y + 10), f"{index / 25:.2f} s", 18, C["muted"])
            strip.paste(frames[index].resize((480, 270), Image.Resampling.LANCZOS), (x + 80, y + 36))
        strip.save(WORK / "transition-frames.png")
