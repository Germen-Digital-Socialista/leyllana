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

from pathlib import Path

from .validation import ExtractionError

# Idioma y resolucion del OCR (mismos valores que chilecompracl).
TESSERACT_LANG = "spa"
DEFAULT_DPI = 300

# Ruta del binario de Tesseract en Windows (build UB-Mannheim, mismo enfoque que
# chilecompracl). Si no existe se cae al PATH.
TESSERACT_EXE = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Umbrales del gate de confianza (ADR 0011: no pasar texto malo al modelo).
_MIN_MEAN_CONFIDENCE = 50.0  # confianza media de palabra (0-100) de Tesseract
_MIN_OCR_CHARS = 20  # caracteres no-espacio minimos para aceptar el OCR


def _render_pages(path: str, dpi: int):
    """Rasteriza el PDF a una lista de imagenes PIL (pdf2image/Poppler)."""
    from pdf2image import convert_from_path

    return convert_from_path(str(path), dpi=dpi)


def _ocr_image(image, lang: str) -> tuple[str, list[int]]:
    """OCR de una imagen: devuelve ``(texto, confianzas_por_palabra)``.

    El texto se reconstruye por lineas (bloque/parrafo/linea de Tesseract) para
    conservar los saltos; las confianzas alimentan el gate de baja confianza.
    """
    import pytesseract

    if Path(TESSERACT_EXE).exists():
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE

    data = pytesseract.image_to_data(
        image, lang=lang, output_type=pytesseract.Output.DICT
    )
    lines: dict[tuple[int, int, int], list[str]] = {}
    confidences: list[int] = []
    for i, word in enumerate(data["text"]):
        if not word.strip():
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines.setdefault(key, []).append(word)
        conf = int(float(data["conf"][i]))
        if conf >= 0:
            confidences.append(conf)
    text = "\n".join(" ".join(words) for _, words in sorted(lines.items()))
    return text, confidences


def ocr_pdf(path: str, *, dpi: int = DEFAULT_DPI, lang: str = TESSERACT_LANG) -> str:
    """Extrae texto de un PDF escaneado via Tesseract (ADR 0011).

    Solo se llama como fallback cuando el PDF no tiene capa de texto utilizable.
    Falla ruidosamente (``ExtractionError``) si faltan las dependencias Python
    (extra `ocr`), si falla la rasterizacion (Poppler ausente o PDF ilegible), si
    Tesseract no esta instalado, o si el resultado es vacio o de baja confianza,
    en vez de entregar texto malo al modelo.
    """
    try:
        import pdf2image  # noqa: F401
        import pytesseract  # noqa: F401  (para referenciar TesseractNotFoundError)
    except ImportError as exc:
        raise ExtractionError(
            "Para OCR instale el extra `ocr` (p. ej. `uv sync --extra ocr`) y los "
            "binarios de sistema Tesseract y Poppler."
        ) from exc

    try:
        images = _render_pages(path, dpi)
    except Exception as exc:  # Poppler ausente o PDF ilegible.
        raise ExtractionError(
            f"No se pudo rasterizar el PDF para OCR (falta Poppler?): {path}"
        ) from exc

    if not images:
        raise ExtractionError(f"El PDF no produjo paginas para OCR: {path}")

    page_texts: list[str] = []
    all_confidences: list[int] = []
    for image in images:
        try:
            text, confidences = _ocr_image(image, lang)
        except pytesseract.TesseractNotFoundError as exc:
            raise ExtractionError(
                "Tesseract no esta instalado o no se encuentra "
                f"(revisada la ruta {TESSERACT_EXE} y el PATH)."
            ) from exc
        page_texts.append(text)
        all_confidences.extend(confidences)

    full = "\n".join(t for t in page_texts if t).strip()
    if len("".join(full.split())) < _MIN_OCR_CHARS:
        raise ExtractionError(
            f"El OCR no produjo texto utilizable del PDF escaneado: {path}"
        )

    mean_confidence = (
        sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
    )
    if mean_confidence < _MIN_MEAN_CONFIDENCE:
        raise ExtractionError(
            f"OCR de baja confianza ({mean_confidence:.0f}%) en {path}: el texto "
            "extraido no es fiable y no se usa (ADR 0011)."
        )

    return full


__all__ = ["ocr_pdf", "TESSERACT_LANG", "DEFAULT_DPI", "TESSERACT_EXE"]
