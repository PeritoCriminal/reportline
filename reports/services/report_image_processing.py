"""
Processamento de imagens para blocos de relatório.

Redimensiona uploads para que a maior dimensão corresponda a 14 cm
na referência de 96 DPI usada por CSS para unidades físicas.
"""

from __future__ import annotations

from io import BytesIO

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

MAX_IMAGE_SIDE_CM = 14
DISPLAY_DPI = 96
CM_PER_INCH = 2.54
MAX_IMAGE_SIDE_PX = round(MAX_IMAGE_SIDE_CM * DISPLAY_DPI / CM_PER_INCH)
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "GIF", "WEBP"}
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}


def resize_image_to_max_side(image: Image.Image, max_side_px: int) -> Image.Image:
    """
    Redimensiona imagem mantendo proporção com maior lado em ``max_side_px``.

    Imagens menores que o limite não são ampliadas.
    """
    width, height = image.size
    if width <= 0 or height <= 0:
        raise ValidationError("Imagem inválida ou corrompida.")

    longest_side = max(width, height)
    if longest_side <= max_side_px:
        return image.copy()

    scale = max_side_px / longest_side
    new_size = (
        max(1, round(width * scale)),
        max(1, round(height * scale)),
    )
    resized = image.copy()
    resized.thumbnail(new_size, Image.Resampling.LANCZOS)
    return resized


def process_uploaded_image(file_obj) -> tuple[bytes, str, int, int]:
    """
    Valida, redimensiona e serializa imagem para persistência.

    Retorna tupla ``(bytes, extensão, largura, altura)``.
    """
    if file_obj.size > MAX_UPLOAD_BYTES:
        raise ValidationError("A imagem excede o tamanho máximo de 15 MB.")

    content_type = getattr(file_obj, "content_type", "") or ""
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise ValidationError("Formato de imagem não suportado. Use JPEG, PNG, GIF ou WebP.")

    file_obj.seek(0)
    try:
        with Image.open(file_obj) as image:
            if image.mode in ("P", "LA", "RGBA"):
                image = image.convert("RGBA")
                save_format = "PNG"
                extension = "png"
            elif image.mode != "RGB":
                image = image.convert("RGB")
                save_format = "JPEG"
                extension = "jpg"
            else:
                save_format = "JPEG"
                extension = "jpg"

            if save_format not in ALLOWED_IMAGE_FORMATS:
                raise ValidationError("Formato de imagem não suportado.")

            resized = resize_image_to_max_side(image, MAX_IMAGE_SIDE_PX)
            buffer = BytesIO()
            save_kwargs = {"optimize": True}
            if save_format == "JPEG":
                save_kwargs["quality"] = 90
                if resized.mode == "RGBA":
                    resized = resized.convert("RGB")
            resized.save(buffer, format=save_format, **save_kwargs)
            return buffer.getvalue(), extension, resized.width, resized.height
    except UnidentifiedImageError as exc:
        raise ValidationError("Arquivo de imagem inválido ou corrompido.") from exc
