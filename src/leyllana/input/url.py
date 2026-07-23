"""Fetch de una fuente oficial por URL (BCN/leychile, Senado/Camara).

Reutiliza el patron de ``corpus_fetcher`` de MuniGPT: sniffing de content-type y
tamano, porque BCN devuelve paginas de error HTML con HTTP 200. Este es el unico
toque de red del camino por defecto (ADR 0005), y solo trae una fuente publica
que el usuario nombro explicitamente. ``requests`` se importa de forma perezosa.
"""

from __future__ import annotations


def fetch(url: str) -> str:
    """Descarga una fuente oficial y devuelve su texto crudo. (Fase 1: por implementar.)"""
    raise NotImplementedError(
        "Fetch de URL (BCN/Senado/Camara) con sniffing de content-type: se implementa en Fase 1."
    )
