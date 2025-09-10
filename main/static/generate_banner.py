from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os
from pathlib import Path


WIDTH = 1800
HEIGHT = 600
LEFT_TEXT = "GLS VPN"
RIGHT_TEXT = "Ссылка на лучший впн в профиле"  # две "с"
OUTPUT_PATH = Path(__file__).with_name("gls-avatar-wordmark-rect.png")


def create_linear_gradient(width: int, height: int, color_start: tuple, color_end: tuple) -> Image.Image:
    base = Image.new("RGB", (width, height), color_start)
    overlay = Image.new("RGB", (width, height), color_end)

    # Left-to-right gradient mask
    mask_row = Image.new("L", (width, 1))
    mask_row.putdata([int(255 * x / max(1, width - 1)) for x in range(width)])
    mask = mask_row.resize((width, height))

    return Image.composite(overlay, base, mask)


def add_soft_glow(image: Image.Image) -> Image.Image:
    width, height = image.size
    glow_layer = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw_glow = ImageDraw.Draw(glow_layer)

    # Place an elliptical glow towards top-left
    center_x, center_y = int(width * 0.35), int(height * 0.35)
    radius_x, radius_y = int(width * 0.70), int(height * 0.90)
    bbox = (
        center_x - radius_x // 2,
        center_y - radius_y // 2,
        center_x + radius_x // 2,
        center_y + radius_y // 2,
    )

    draw_glow.ellipse(bbox, fill=(255, 255, 255, 120))
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=int(min(width, height) * 0.12)))

    base_rgba = image.convert("RGBA")
    return Image.alpha_composite(base_rgba, glow_layer)


def find_existing_path(paths: list[str]) -> str | None:
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None


def load_font(size: int, *, bold: bool) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    # Prefer Windows fonts for Cyrillic support; fallback to default PIL font
    windir = os.environ.get("WINDIR", r"C:\\Windows")
    fonts_dir = os.path.join(windir, "Fonts")

    bold_candidates = [
        os.path.join(fonts_dir, "Inter-Bold.ttf"),
        os.path.join(fonts_dir, "Inter-ExtraBold.ttf"),
        os.path.join(fonts_dir, "arialbd.ttf"),
        os.path.join(fonts_dir, "Arialbd.ttf"),
        os.path.join(fonts_dir, "segoeuib.ttf"),
    ]
    regular_candidates = [
        os.path.join(fonts_dir, "Inter-Regular.ttf"),
        os.path.join(fonts_dir, "arial.ttf"),
        os.path.join(fonts_dir, "segoeui.ttf"),
    ]

    font_path = find_existing_path(bold_candidates if bold else regular_candidates)
    if font_path:
        try:
            return ImageFont.truetype(font_path, size=size)
        except Exception:
            pass
    return ImageFont.load_default()


def measure_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def load_tagline_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    windir = os.environ.get("WINDIR", r"C:\\Windows")
    fonts_dir = os.path.join(windir, "Fonts")
    # Prefer elegant italic fonts that support Cyrillic; fallback to readable sans-serif
    pretty_candidates = [
        os.path.join(fonts_dir, "timesi.ttf"),            # Times New Roman Italic (alias)
        os.path.join(fonts_dir, "Timesi.ttf"),            # Alternative capitalization
        os.path.join(fonts_dir, "Times New Roman Italic.ttf"),
        os.path.join(fonts_dir, "georgiai.ttf"),          # Georgia Italic
        os.path.join(fonts_dir, "Georgia Italic.ttf"),
        os.path.join(fonts_dir, "segoeuii.ttf"),          # Segoe UI Italic
        os.path.join(fonts_dir, "calibrii.ttf"),          # Calibri Italic
        os.path.join(fonts_dir, "georgia.ttf"),
        os.path.join(fonts_dir, "segoeui.ttf"),
        os.path.join(fonts_dir, "calibri.ttf"),
        os.path.join(fonts_dir, "ariali.ttf"),           # Arial Italic
        os.path.join(fonts_dir, "arial.ttf"),
    ]
    for path in pretty_candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue
    return ImageFont.load_default()


def measure_multiline_block(draw: ImageDraw.ImageDraw, lines: list[str], font: ImageFont.ImageFont, line_gap: int) -> tuple[int, int, list[int]]:
    if not lines:
        return 0, 0, []
    widths: list[int] = []
    heights: list[int] = []
    for line in lines:
        w, h = measure_text(draw, line, font)
        widths.append(w)
        heights.append(h)
    total_height = sum(heights) + line_gap * max(0, len(lines) - 1)
    max_width = max(widths) if widths else 0
    return max_width, total_height, heights


def wrap_text_by_words(text: str, font: ImageFont.ImageFont, max_width: int, draw: ImageDraw.ImageDraw, max_lines: int = 2) -> list[str] | None:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        w, _ = measure_text(draw, candidate, font)
        if w <= max_width:
            current = candidate
        else:
            if not current:
                # Single word longer than max_width → cannot wrap at this size
                return None
            lines.append(current)
            current = word
            if len(lines) >= max_lines:
                return None
    if current:
        lines.append(current)
    return lines


def fit_fonts_vertical_layout(width: int, height: int, draw: ImageDraw.ImageDraw):
    # Two-line left block: "GLS" on top, "VPN" below
    left_lines = [seg for seg in LEFT_TEXT.split() if seg]
    if len(left_lines) >= 2:
        left_lines = [left_lines[0], left_lines[1]]
    elif len(left_lines) == 1:
        left_lines = [left_lines[0], ""]
    else:
        left_lines = ["GLS", "VPN"]

    # Initial sizes
    left_size = int(height * 0.26)
    right_size = int(height * 0.32)  # start very large; will shrink to fit

    left_font = load_font(left_size, bold=True)
    # Right caption uses the same family/style as GLS/VPN
    right_font = load_font(right_size, bold=True)

    margin_left = int(width * 0.045)
    margin_right = margin_left
    gap = int(width * 0.02)
    margin_v = int(height * 0.08)

    max_lines = 2
    for _ in range(160):
        line_gap_left = max(4, int(left_font.size * 0.18))
        left_w, left_h, _ = measure_multiline_block(draw, left_lines, left_font, line_gap_left)

        available_right_width = max(10, width - (margin_left + left_w + gap + margin_right))
        right_lines = wrap_text_by_words(RIGHT_TEXT, right_font, available_right_width, draw, max_lines=max_lines)
        if right_lines is None:
            # Right text too wide even for a single word on a line → shrink right font
            if right_font.size > int(height * 0.09):
                right_size = max(int(right_font.size * 0.92), int(height * 0.09))
                right_font = load_font(right_size, bold=True)
                continue
            else:
                # As a last resort allow more lines
                if max_lines < 3:
                    max_lines = 3
                    continue
                break

        line_gap_right = max(2, int(right_font.size * 0.12))
        right_w, right_h, _ = measure_multiline_block(draw, right_lines, right_font, line_gap_right)

        fits_height = (max(left_h, right_h) + margin_v * 2) <= height
        fits_width = (margin_left + left_w + gap + right_w + margin_right) <= width

        if fits_height and fits_width:
            return left_font, right_font, margin_left, gap, margin_v, left_lines, right_lines, line_gap_right

        # Prefer keeping right bigger: shrink left first for width constraint
        if not fits_width:
            if left_font.size > int(height * 0.10):
                left_size = max(int(left_font.size * 0.92), int(height * 0.10))
                left_font = load_font(left_size, bold=True)
                continue
            if right_font.size > int(height * 0.09):
                right_size = max(int(right_font.size * 0.92), int(height * 0.09))
                right_font = load_font(right_size, bold=True)
                continue
            if max_lines < 3:
                max_lines = 3
                continue

        if not fits_height:
            # Reduce the taller block first
            if right_h >= left_h and right_font.size > int(height * 0.09):
                right_size = max(int(right_font.size * 0.92), int(height * 0.09))
                right_font = load_font(right_size, bold=True)
                continue
            if left_font.size > int(height * 0.10):
                left_size = max(int(left_font.size * 0.92), int(height * 0.10))
                left_font = load_font(left_size, bold=True)
                continue
            if max_lines < 3:
                max_lines = 3
                continue

    # Fallback return if loop did not early-return
    line_gap_left = max(4, int(left_font.size * 0.18))
    left_w, left_h, _ = measure_multiline_block(draw, left_lines, left_font, line_gap_left)
    available_right_width = max(10, width - (margin_left + left_w + gap + margin_right))
    right_lines = wrap_text_by_words(RIGHT_TEXT, right_font, available_right_width, draw, max_lines=max_lines) or [RIGHT_TEXT]
    line_gap_right = max(2, int(right_font.size * 0.12))
    return left_font, right_font, margin_left, gap, margin_v, left_lines, right_lines, line_gap_right


def draw_text_with_shadow(base_rgba: Image.Image, xy: tuple[int, int], text: str, font: ImageFont.ImageFont,
                          fill=(255, 255, 255), shadow_offset=(0, 2), shadow_color=(11, 16, 32), shadow_alpha=120) -> Image.Image:
    width, height = base_rgba.size
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    # Shadow
    shadow_pos = (xy[0] + shadow_offset[0], xy[1] + shadow_offset[1])
    d.text(shadow_pos, text, font=font, fill=(shadow_color[0], shadow_color[1], shadow_color[2], shadow_alpha))
    # Text
    d.text(xy, text, font=font, fill=(fill[0], fill[1], fill[2], 255))
    return Image.alpha_composite(base_rgba, layer)


def main():
    width, height = WIDTH, HEIGHT

    # Full-size tile with rounded corners on transparent background
    tile_x = 0
    tile_y = 0
    tile_w = width
    tile_h = height
    corner_radius = int(min(tile_w, tile_h) * 0.08)

    tile = create_linear_gradient(tile_w, tile_h, (109, 139, 255), (154, 109, 255))
    tile = add_soft_glow(tile)
    tile = tile.convert("RGBA")

    # Transparent canvas and rounded mask
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    mask = Image.new("L", (tile_w, tile_h), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.rounded_rectangle([0, 0, tile_w, tile_h], radius=corner_radius, fill=255)
    img.paste(tile, (tile_x, tile_y), mask)

    # Layout and text on the tile area
    draw = ImageDraw.Draw(img)
    (
        left_font,
        right_font,
        margin_left,
        gap,
        margin_v,
        left_lines,
        right_lines,
        line_gap_right,
    ) = fit_fonts_vertical_layout(tile_w, tile_h, draw)

    # Measure for layout in canvas coordinates
    line_gap_left = max(4, int(left_font.size * 0.18))
    left_w, left_h, left_line_heights = measure_multiline_block(draw, left_lines, left_font, line_gap_left)
    right_w, right_h, right_line_heights = measure_multiline_block(draw, right_lines, right_font, line_gap_right)

    left_x = tile_x + margin_left
    left_y = tile_y + (tile_h - left_h) // 2
    right_x = left_x + left_w + gap
    right_y = tile_y + (tile_h - right_h) // 2

    current_y = left_y
    for idx, line in enumerate(left_lines):
        img = draw_text_with_shadow(img, (left_x, current_y), line, left_font)
        current_y += left_line_heights[idx] + (line_gap_left if idx < len(left_lines) - 1 else 0)

    # Draw right wrapped lines
    current_y = right_y
    for idx, line in enumerate(right_lines):
        img = draw_text_with_shadow(img, (right_x, current_y), line, right_font)
        current_y += right_line_heights[idx] + (line_gap_right if idx < len(right_lines) - 1 else 0)

    final = img.convert("RGBA")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    final.save(OUTPUT_PATH, format="PNG")
    print(f"Saved banner to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()



