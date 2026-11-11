#!/usr/bin/env python3
"""Gera os ativos oficiais do Gaspar a partir de uma ilustracao em fundo magenta.

Uso:
    python tools/make_assets.py caminho/para/gaspar_original.png

O script remove o fundo magenta, recorta o mascote, grava:
    assets/gaspar.png              (512 px, transparencia real)
    assets/gaspar.ico              (16..256 px)
    assets/gaspar_flutuando.gif    (flutuacao suave, 220x220)
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"

PNG_SIZE = 512
GIF_SIDE = 220
GIF_BODY_HEIGHT = 176
GIF_FRAMES = 16
GIF_FRAME_MS = 110


def _remove_magenta(src: Image.Image) -> Image.Image:
    src = src.convert("RGBA")
    r, g, b, _ = src.split()

    high_r = r.point(lambda v: 255 if v > 140 else 0)
    high_b = b.point(lambda v: 255 if v > 140 else 0)
    low_g = g.point(lambda v: 255 if v < 120 else 0)
    magenta = ImageChops.multiply(high_r, ImageChops.multiply(high_b, low_g))

    # Remove apenas o fundo conectado as bordas; magenta interno (se houver) e preservado.
    flood = magenta.copy()
    width, height = flood.size
    for corner in ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)):
        if flood.getpixel(corner) == 255:
            ImageDraw.floodfill(flood, corner, 128, thresh=0)
    alpha = flood.point(lambda v: 0 if v == 128 else 255)
    alpha = alpha.filter(ImageFilter.MinFilter(3))       # tira o anel magenta
    alpha = alpha.filter(ImageFilter.GaussianBlur(0.8))  # suaviza a borda

    # Descontamina a franja magenta nas bordas, puxando para o verde do corpo.
    edge = alpha.point(lambda v: 255 if 0 < v < 250 else 0)
    r_clean = ImageChops.darker(r, g.point(lambda v: min(255, v + 25)))
    b_clean = ImageChops.darker(b, g.point(lambda v: min(255, v + 12)))
    rgb_clean = Image.merge("RGB", (r_clean, g, b_clean))
    rgb = Image.composite(rgb_clean, src.convert("RGB"), edge)

    out = rgb.convert("RGBA")
    out.putalpha(alpha)
    return out


def _square_crop(img: Image.Image, pad_ratio: float = 0.05) -> Image.Image:
    bbox = img.getchannel("A").getbbox()
    if bbox:
        img = img.crop(bbox)
    side = int(max(img.size) * (1 + 2 * pad_ratio))
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(img, ((side - img.width) // 2, (side - img.height) // 2), img)
    return canvas


def _resize_rgba(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Redimensiona com alpha, misturando as bordas no verde para nao escurecer."""
    flat = Image.alpha_composite(Image.new("RGBA", img.size, (127, 191, 0, 255)), img)
    flat = flat.convert("RGB").resize(size, Image.LANCZOS)
    alpha = img.getchannel("A").resize(size, Image.LANCZOS)
    out = flat.convert("RGBA")
    out.putalpha(alpha)
    return out


def _to_gif_frame(frame: Image.Image) -> Image.Image:
    rgba = frame.convert("RGBA")
    alpha = rgba.getchannel("A")
    rgb = rgba.convert("RGB")

    palette_img = rgb.quantize(
        colors=255,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.FLOYDSTEINBERG,
    )
    transparent_mask = alpha.point(lambda v: 255 if v < 128 else 0)
    palette_img.paste(255, mask=transparent_mask)
    palette = palette_img.getpalette()[: 255 * 3] + [0, 0, 0]
    palette_img.putpalette(palette)
    palette_img.info["transparency"] = 255
    return palette_img


def _build_gif(base: Image.Image, dest: Path) -> None:
    body_h = GIF_BODY_HEIGHT
    body_w = max(1, round(base.width * body_h / base.height))
    body = _resize_rgba(base, (body_w, body_h))
    center = GIF_SIDE // 2
    frames: list[Image.Image] = []

    for index in range(GIF_FRAMES):
        phase = 2 * math.pi * index / GIF_FRAMES
        bob = 5.0 * math.sin(phase)
        sway = 2.5 * math.sin(phase / 2)
        angle = 1.6 * math.sin(phase / 2)
        scale = 1.0 + 0.018 * math.sin(phase * 2)

        size = (max(1, round(body.width * scale)), max(1, round(body.height * scale)))
        sprite = body.resize(size, Image.LANCZOS)
        sprite = sprite.rotate(angle, resample=Image.BICUBIC, expand=True)

        canvas = Image.new("RGBA", (GIF_SIDE, GIF_SIDE), (0, 0, 0, 0))
        x = round(center + sway - sprite.width / 2)
        y = round(center + bob - sprite.height / 2)
        canvas.paste(sprite, (x, y), sprite)
        frames.append(_to_gif_frame(canvas))

    frames[0].save(
        dest,
        save_all=True,
        append_images=frames[1:],
        duration=GIF_FRAME_MS,
        loop=0,
        disposal=2,
        transparency=255,
        optimize=False,
    )


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2

    source = Path(sys.argv[1])
    if not source.exists():
        print(f"ERRO: imagem nao encontrada: {source}", file=sys.stderr)
        return 1

    ASSETS.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as raw:
        mascot = _square_crop(_remove_magenta(raw))

    png = _resize_rgba(mascot, (PNG_SIZE, PNG_SIZE))
    png_path = ASSETS / "gaspar.png"
    png.save(png_path, optimize=True)
    print(f"PNG: {png_path} ({png_path.stat().st_size / 1024:.1f} KB)")

    ico_path = ASSETS / "gaspar.ico"
    png.save(
        ico_path,
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
    )
    print(f"ICO: {ico_path} ({ico_path.stat().st_size / 1024:.1f} KB)")

    gif_path = ASSETS / "gaspar_flutuando.gif"
    _build_gif(png, gif_path)
    print(f"GIF: {gif_path} ({gif_path.stat().st_size / 1024:.1f} KB)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
