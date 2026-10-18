#!/usr/bin/env python3
"""Build a macOS app icon and a menu-bar template icon with the standard library."""

from __future__ import annotations

import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT_DIR / "assets"

# iconutil accepts only these iconset filenames.
ICONSET_SIZES = (16, 32, 128, 256, 512)


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def generate_squircle_png(size: int = 512, is_template: bool = False) -> bytes:
    """Return a PNG: teal squircle with a white cross-and-dumbbell, or a menu-bar template."""
    if size < 8:
        raise ValueError("icon size must be at least 8")
    raw = bytearray()
    cx = cy = size / 2.0
    radius = size * 0.43
    for y in range(size):
        raw.append(0)
        for x in range(size):
            nx = abs(x - cx) / radius
            ny = abs(y - cy) / radius
            inside = (nx ** 4 + ny ** 4) <= 1.0
            in_h_bar = abs(x - cx) < size * 0.20 and abs(y - cy) < size * 0.055
            in_v_bar = abs(x - cx) < size * 0.055 and abs(y - cy) < size * 0.20
            in_left_bell = abs(x - (cx - size * 0.22)) < size * 0.045 and abs(y - cy) < size * 0.13
            in_right_bell = abs(x - (cx + size * 0.22)) < size * 0.045 and abs(y - cy) < size * 0.13
            in_symbol = in_h_bar or in_v_bar or in_left_bell or in_right_bell
            if is_template:
                if in_symbol:
                    raw.extend((30, 30, 30, 255))
                elif inside and (nx ** 4 + ny ** 4) > 0.72:
                    raw.extend((30, 30, 30, 220))
                else:
                    raw.extend((0, 0, 0, 0))
            elif not inside:
                raw.extend((0, 0, 0, 0))
            elif in_symbol:
                raw.extend((255, 255, 255, 255))
            else:
                raw.extend(
                    (
                        int(16 + 28 * (y / size)),
                        int(175 - 45 * (y / size)),
                        int(135 + 65 * (x / size)),
                        255,
                    )
                )
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    compressed = zlib.compress(bytes(raw), 9)
    return b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", compressed) + _png_chunk(b"IEND", b"")


def _resize_png(source: Path, size: int, dest: Path) -> None:
    subprocess.run(
        ["sips", "-z", str(size), str(size), str(source), "--out", str(dest)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def build_assets() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    app_png = ASSETS_DIR / "AppIcon.png"
    menubar_png = ASSETS_DIR / "menubar_icon.png"
    app_png.write_bytes(generate_squircle_png(512, is_template=False))
    menubar_png.write_bytes(generate_squircle_png(44, is_template=True))
    print(f"[OK] PNG icons: {app_png}, {menubar_png}")

    if sys.platform != "darwin" or not shutil.which("sips") or not shutil.which("iconutil"):
        print("[SKIP] sips or iconutil is unavailable, so AppIcon.icns was not built.")
        return
    iconset_dir = ASSETS_DIR / "AppIcon.iconset"
    if iconset_dir.exists():
        shutil.rmtree(iconset_dir)
    iconset_dir.mkdir(parents=True)
    for size in ICONSET_SIZES:
        _resize_png(app_png, size, iconset_dir / f"icon_{size}x{size}.png")
        _resize_png(app_png, size * 2, iconset_dir / f"icon_{size}x{size}@2x.png")
    icns_path = ASSETS_DIR / "AppIcon.icns"
    completed = subprocess.run(
        ["iconutil", "-c", "icns", str(iconset_dir), "-o", str(icns_path)],
        check=False,
    )
    shutil.rmtree(iconset_dir, ignore_errors=True)
    if completed.returncode != 0 or not icns_path.is_file():
        raise SystemExit("iconutil could not build assets/AppIcon.icns")
    print(f"[OK] macOS icon: {icns_path}")


if __name__ == "__main__":
    build_assets()
