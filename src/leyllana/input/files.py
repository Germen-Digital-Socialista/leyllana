"""Lectura de archivos locales: ``.txt`` directo, ``.pdf`` via PyMuPDF.

La extraccion de PDF replica el enfoque de MuniGPT (``fitz``). PyMuPDF se importa
de forma perezosa dentro de la funcion para que el esqueleto importe sin la
dependencia instalada.
"""

from __future__ import annotations

from pathlib import Path

from .validation import ExtractionError


def read_file(path: str) -> str:
    """Lee un archivo local y devuelve su texto crudo.

    ``.txt`` se lee directo; ``.pdf`` se extrae con PyMuPDF.
    """
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".txt":
        return p.read_text(encoding="utf-8")
    if suffix == ".pdf":
        return _extract_pdf(p)
    raise ValueError(f"Formato de archivo no soportado: {suffix!r} (use .txt o .pdf)")


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
