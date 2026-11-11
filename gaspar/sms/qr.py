"""Geracao do QR de pareamento do celular."""

from __future__ import annotations


def make_qr(payload: str, box_size: int = 6, border: int = 2):
    """Devolve uma imagem PIL pronta para o Tk."""
    try:
        import qrcode
    except ImportError as exc:
        raise RuntimeError("Instale a dependencia 'qrcode' para exibir o QR.") from exc
    code = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=max(2, int(box_size)),
        border=max(1, int(border)),
    )
    code.add_data(payload)
    code.make(fit=True)
    image = code.make_image(fill_color="black", back_color="white")
    if hasattr(image, "get_image"):
        image = image.get_image()
    return image.convert("RGB")
