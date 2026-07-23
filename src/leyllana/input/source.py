"""Identificacion de la fuente (PRD FR-7.1).

Devuelve solo los metadatos que se pueden extraer de la fuente; nunca inventa
(misma regla que el guardrail anti-invencion, ADR 0008). En el esqueleto de
Fase 1 no extrae metadatos todavia: devuelve un ``SourceInfo`` vacio. La
extraccion real (titulo, tipo de norma, organo emisor, fecha, version, URL,
fecha de consulta) desde BCN/Senado/Camara se implementa en Fase 1.
"""

from __future__ import annotations

from ..types import SourceInfo


def identify_source(source: str) -> SourceInfo:
    """Extrae los metadatos de identificacion disponibles para ``source``.

    Fase 1 (esqueleto): devuelve un ``SourceInfo`` vacio (nada identificado).
    Nunca inventa: un campo ausente queda en ``None``.
    """
    return SourceInfo()


__all__ = ["identify_source"]
