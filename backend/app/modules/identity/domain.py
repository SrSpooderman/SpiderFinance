"""Identity rules independent of HTTP and database mappings."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Principal:
    id: int
    auth_version: int

DEFAULT_CATEGORIES = (
    "Alimentación", "Restaurantes", "Transporte", "Ocio", "Ropa", "Tecnología",
    "Estudios", "Salud", "Viajes", "Hogar", "Suscripciones", "Deporte",
    "Regalos", "Mascotas", "Impuestos", "Comisiones", "Otros",
)

MAX_PROFILE_PHOTO_BYTES = 2 * 1024 * 1024
def photo_type(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None
