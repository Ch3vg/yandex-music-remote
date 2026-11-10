from __future__ import annotations

import io

import qrcode
from PIL import Image, ImageDraw
from qrcode.constants import ERROR_CORRECT_M


def render_icon(size: int) -> bytes:
    image = Image.new("RGB", (size, size), "#000000")
    draw = ImageDraw.Draw(image)
    margin = max(8, size // 8)
    radius = max(12, size // 6)
    draw.rounded_rectangle(
        (margin, margin, size - margin - 1, size - margin - 1),
        radius=radius,
        fill="#ffcc00",
    )
    draw.polygon(
        (
            (0.36 * size, 0.30 * size),
            (0.36 * size, 0.70 * size),
            (0.74 * size, 0.50 * size),
        ),
        fill="#000000",
    )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def render_qr(url: str) -> bytes:
    image = _qr_image(url)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _qr_image(url: str):
    code = qrcode.QRCode(version=1, error_correction=ERROR_CORRECT_M, box_size=10, border=4)
    code.add_data(url)
    try:
        code.make(fit=False)
    except qrcode.exceptions.DataOverflowError:
        code = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_M, box_size=10, border=4)
        code.add_data(url)
        code.make(fit=True)
    return code.make_image(fill_color="black", back_color="white")
