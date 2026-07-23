"""Lectura de archivos locales: ``.txt`` directo, ``.pdf`` via PyMuPDF.

La extraccion de PDF replica el enfoque de MuniGPT (``fitz``). PyMuPDF se importa
de forma perezosa dentro de la funcion para que el esqueleto importe sin la
dependencia instalada.
"""

from __future__ import annotations

from pathlib import Path


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
    """Extrae texto de un PDF con PyMuPDF. (Fase 1: por implementar.)"""
    raise NotImplementedError("Extraccion de PDF con PyMuPDF: se implementa en Fase 1.")
