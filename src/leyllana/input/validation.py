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

# Umbrales para la deteccion de PDF escaneado por densidad de texto (ADR 0011).
# Una pagina "tiene capa de texto" si supera este minimo de caracteres no-espacio;
# el PDF se considera escaneado si menos de este ratio de paginas la tiene.
_MIN_CHARS_PER_PAGE = 50
_MIN_TEXT_PAGE_RATIO = 0.2


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

    Deteccion por densidad de texto por pagina (ADR 0011): se cuenta cuantas
    paginas superan ``_MIN_CHARS_PER_PAGE`` caracteres no-espacio. Si menos de
    ``_MIN_TEXT_PAGE_RATIO`` de las paginas tiene capa de texto, el documento se
    trata como escaneado y se enruta al OCR completo. Un documento vacio no es
    "escaneado" (no hay imagen que leer): lo marca ``validate_text``.
    """
    import fitz  # PyMuPDF, importado de forma perezosa (extra `pdf`).

    try:
        doc = fitz.open(str(path))
    except Exception as exc:  # PDF ilegible/corrupto: no alimentar texto malo.
        raise ExtractionError(f"No se pudo abrir el PDF: {path}") from exc

    try:
        total = doc.page_count
        if total == 0:
            return False
        text_pages = sum(
            1
            for page in doc
            if len("".join(page.get_text().split())) >= _MIN_CHARS_PER_PAGE
        )
    finally:
        doc.close()

    return (text_pages / total) < _MIN_TEXT_PAGE_RATIO


__all__ = ["ExtractionError", "validate_text", "is_scanned_pdf"]
