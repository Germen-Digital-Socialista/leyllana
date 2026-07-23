"""Lectura de archivos locales: ``.txt`` directo, ``.pdf`` via PyMuPDF.

La extraccion de PDF replica el enfoque de MuniGPT (``fitz``). PyMuPDF se importa
de forma perezosa dentro de la funcion para que el esqueleto importe sin la
dependencia instalada.
"""

from __future__ import annotations

from pathlib import Path

from ..types import SourceInfo
from . import source
from .validation import ExtractionError


def read_file_with_source(path: str) -> tuple[str, SourceInfo]:
    """Lee un archivo y devuelve ``(texto, SourceInfo)`` (FR-7.1).

    Un ``.pdf`` aporta sus metadatos (titulo, fecha); un ``.txt`` pelado no tiene
    procedencia y devuelve un ``SourceInfo`` vacio. La apertura extra para leer los
    metadatos es de un archivo local (barata), no una segunda descarga de red.
    """
    text = read_file(path)
    if Path(path).suffix.lower() == ".pdf":
        return text, source.from_pdf_metadata(_pdf_metadata(path))
    return text, SourceInfo()


def _pdf_metadata(path: str) -> dict:
    """Metadatos de un PDF via PyMuPDF; ``{}`` si falta el extra o no se puede abrir."""
    try:
        import fitz
    except ImportError:
        return {}
    try:
        doc = fitz.open(str(path))
    except Exception:  # noqa: BLE001 - sin metadatos si el PDF no abre
        return {}
    try:
        return doc.metadata or {}
    finally:
        doc.close()


def read_file(path: str) -> str:
    """Lee un archivo local y devuelve su texto crudo.

    ``.txt`` se lee directo; ``.pdf`` se extrae con PyMuPDF.
    """
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".txt":
        return p.read_text(encoding="utf-8")
    if suffix == ".pdf":
        return _read_pdf(p)
    raise ValueError(f"Formato de archivo no soportado: {suffix!r} (use .txt o .pdf)")


def _read_pdf(path: Path) -> str:
    """Lee un PDF: capa de texto via PyMuPDF, con OCR de respaldo si esta escaneado.

    Se extrae primero (esto ya falla ruidosamente ante un PDF corrupto o protegido,
    ADR 0011). Si la deteccion por densidad marca el documento como escaneado, se
    enruta al OCR completo; el OCR nunca corre sobre un PDF que ya tiene capa de
    texto utilizable.
    """
    from .validation import is_scanned_pdf

    text = _extract_pdf(path)
    if is_scanned_pdf(str(path)):
        from .ocr import ocr_pdf

        return ocr_pdf(str(path))
    return text


def _extract_pdf(path: Path) -> str:
    """Extrae texto de un PDF con PyMuPDF (mismo enfoque que MuniGPT: ``fitz``).

    Un PDF corrupto o protegido por contrasena no se pasa en silencio al modelo:
    se levanta ``ExtractionError`` (fallar ruidosamente, ADR 0011). Un PDF
    escaneado sin capa de texto devuelve texto vacio; el gate de validacion en
    ``resolve`` lo marca para OCR, no se decide aqui.
    """
    try:
        import fitz  # PyMuPDF, importado de forma perezosa (extra `pdf`).
    except ImportError as exc:
        raise ExtractionError(
            "Para leer PDF instale el extra `pdf` (p. ej. `uv sync --extra pdf`)."
        ) from exc

    try:
        doc = fitz.open(str(path))
    except Exception as exc:  # PDF ilegible/corrupto: no alimentar texto malo.
        raise ExtractionError(f"No se pudo abrir el PDF: {path}") from exc

    try:
        if doc.needs_pass:
            raise ExtractionError(
                f"El PDF esta protegido por contrasena y no se puede leer: {path}"
            )
        return "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()
