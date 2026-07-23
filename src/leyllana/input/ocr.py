"""OCR de respaldo para PDF escaneados (ADR 0011).

Tesseract via ``pytesseract`` (``-l spa``), rasterizando paginas con
pdf2image/Poppler a 300 DPI. Ningun modelo de vision corre en el camino por
defecto (mismo enfoque no-alucinacion que ``chilecompracl``). El OCR corre SOLO
como fallback cuando el PDF no tiene capa de texto utilizable.

Las dependencias Python (``pytesseract``, ``pdf2image``, ``pillow``) viven en el
extra ``ocr`` y se importan de forma perezosa; los binarios de sistema
(Tesseract, Poppler) son una instalacion aparte y su ausencia se avisa en vez de
fallar en silencio.
"""

from __future__ import annotations

# Idioma y resolucion del OCR (mismos valores que chilecompracl).
TESSERACT_LANG = "spa"
DEFAULT_DPI = 300


def ocr_pdf(path: str, *, dpi: int = DEFAULT_DPI, lang: str = TESSERACT_LANG) -> str:
    """Extrae texto de un PDF escaneado via Tesseract. (Fase 1: por implementar.)

    Debe fallar ruidosamente si faltan los binarios (Tesseract/Poppler) o si la
    confianza es baja, en vez de entregar texto malo al modelo (ADR 0011).
    """
    raise NotImplementedError(
        "OCR con Tesseract/Poppler (extra `ocr`): se implementa en Fase 1."
    )


__all__ = ["ocr_pdf", "TESSERACT_LANG", "DEFAULT_DPI"]
