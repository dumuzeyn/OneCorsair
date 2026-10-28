"""Create the SVG source and export a crisp, multi-resolution Windows icon."""

from pathlib import Path
import io
import struct

from PIL import Image, ImageDraw


ICON_SIZES = (16, 20, 24, 28, 32, 40, 48, 64, 96, 128, 256)


SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <title>OneCorsair — sail and sea</title>
  <rect x="12" y="12" width="232" height="232" rx="60" fill="#1d4e89"/>
  <path d="M147 46 C115 80 92 113 76 153 C100 143 124 142 147 146 Z" fill="#ffffff"/>
  <path d="M62 184 C86 168 109 168 132 184 C155 200 177 200 198 184" fill="none" stroke="#f06585" stroke-width="16" stroke-linecap="round"/>
</svg>'''


def save_windows_ico(path, frames):
    """Use native 32-bit DIB frames below 256px, plus a large PNG frame."""
    chunks = []
    for size, frame in sorted(frames.items()):
        if size == 256:
            buffer = io.BytesIO()
            frame.save(buffer, format="PNG")
            chunks.append((size, buffer.getvalue()))
            continue
        rgba = frame.convert("RGBA")
        pixels = rgba.transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes("raw", "BGRA")
        mask_stride = ((size + 31) // 32) * 4
        mask = bytearray(mask_stride * size)
        alpha = rgba.getchannel("A")
        for y in range(size):
            for x in range(size):
                if alpha.getpixel((x, y)) == 0:
                    mask[(size - 1 - y) * mask_stride + x // 8] |= 0x80 >> (x % 8)
        header = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0, len(pixels), 0, 0, 0, 0)
        chunks.append((size, header + pixels + mask))
    directory = bytearray(struct.pack("<HHH", 0, 1, len(chunks)))
    offset = 6 + len(chunks) * 16
    for size, data in chunks:
        directory.extend(struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset))
        offset += len(data)
    path.write_bytes(directory + b"".join(data for _size, data in chunks))


def main():
    assets = Path(__file__).resolve().parent / "assets"
    assets.mkdir(exist_ok=True)
    (assets / "download_icon.svg").write_text(SVG, encoding="utf-8")
    # Export the same simple geometry directly; Pillow is a build-only dependency.
    scale = 4
    image = Image.new("RGBA", (256 * scale, 256 * scale))
    draw = ImageDraw.Draw(image)

    def box(values):
        return tuple(round(v * scale) for v in values)

    def curve(start, control1, control2, end, steps=64):
        points = []
        for index in range(steps + 1):
            t = index / steps
            u = 1 - t
            points.append(tuple(u**3 * start[axis] + 3 * u**2 * t * control1[axis]
                                + 3 * u * t**2 * control2[axis] + t**3 * end[axis]
                                for axis in (0, 1)))
        return points

    draw.rounded_rectangle(box((12, 12, 244, 244)), radius=60 * scale, fill="#1d4e89")
    sail = curve((147, 46), (115, 80), (92, 113), (76, 153))
    sail += curve((76, 153), (100, 143), (124, 142), (147, 146))[1:]
    draw.polygon([box(point) for point in sail], fill="#ffffff")
    wave = curve((62, 184), (86, 168), (109, 168), (132, 184))
    wave += curve((132, 184), (155, 200), (177, 200), (198, 184))[1:]
    draw.line([box(point) for point in wave], fill="#f06585", width=16 * scale, joint="curve")
    for x, y in (wave[0], wave[-1]):
        draw.ellipse(box((x - 8, y - 8, x + 8, y + 8)), fill="#f06585")
    # Resize each frame directly from the supersampled drawing, preserving smooth
    # edges at the exact pixel sizes Windows uses for different display scales.
    frames = {size: image.resize((size, size), Image.Resampling.LANCZOS) for size in ICON_SIZES}
    icon_directory = assets / "window-icons"
    icon_directory.mkdir(exist_ok=True)
    for size, frame in frames.items():
        frame.save(icon_directory / f"icon-{size}.png")
    frames[256].save(assets / "download_icon.png")
    save_windows_ico(assets / "download_icon.ico", frames)
    wizard_icon = image.resize((55, 55), Image.Resampling.LANCZOS)
    wizard_image = Image.new("RGB", (55, 55), "white")
    wizard_image.paste(wizard_icon, (0, 0), wizard_icon)
    wizard_image.save(assets / "setup-small.bmp")
    print("Created SVG, PNG and ICO, plus 11 smooth window icon sizes")


if __name__ == "__main__":
    main()
