"""Validacion de la entrada antes de explicarla (ADR 0011).

Detecta texto vacio o inutilizable y lo marca en vez de pasar texto malo al
modelo. El OCR corre solo como fallback cuando un PDF no tiene capa de texto
utilizable, nunca sobre un documento que ya extrae bien.

En el esqueleto de Fase 1 la comprobacion de vacio/casi-vacio es real; la
deteccion fina de PDF escaneado (densidad de texto por pagina) que dispara el
OCR queda por implementar.
"""

from __future__ import annotations


class ExtractionError(RuntimeError):
    """La extraccion no produjo texto utilizable.

    Cubre entrada vacia, PDF protegido, PDF escaneado sin capa de texto, o un OCR
    de baja confianza. Se muestra al usuario en vez de alimentar al modelo con
    texto malo (ADR 0011).
    """


# Minimo de caracteres no-espacio para considerar la extraccion utilizable.
_MIN_USABLE_CHARS = 20


def validate_text(text: str, *, source: str | None = None) -> str:
    """Valida el texto extraido y lo devuelve si es utilizable.

    Comprobacion real de vacio/casi-vacio. La deteccion de PDF escaneado por
    densidad de texto (que enruta al OCR) se implementa en Fase 1.
    """
    if len(text.strip()) < _MIN_USABLE_CHARS:
        detalle = f" Fuente: {source}" if source else ""
        raise ExtractionError(
            "La fuente no entrego texto utilizable (vacia, protegida o escaneada). "
            "Si es un PDF escaneado, se requiere OCR (Tesseract/Poppler)." + detalle
        )
    return text


def is_scanned_pdf(path: str) -> bool:
    """Decide si un PDF carece de capa de texto utilizable y debe ir a OCR.

    Deteccion por densidad de texto por pagina (ADR 0011). Fase 1: por implementar.
    """
    raise NotImplementedError(
        "Deteccion de PDF escaneado por densidad de texto: se implementa en Fase 1."
    )


__all__ = ["ExtractionError", "validate_text", "is_scanned_pdf"]
