"""Identificacion de la fuente (PRD FR-7.1).

Mapea artefactos ya obtenidos (el XML de leychile, los metadatos de un PDF) a un
``SourceInfo``. Nunca inventa: la misma regla del guardrail anti-invencion
(ADR 0008); un campo que no se puede determinar queda en ``None``. Estas funciones
son puras (reciben el artefacto, no tocan la red ni abren el archivo dos veces): el
XML y los metadatos vienen del mismo fetch/apertura que ya hizo la capa de entrada.
"""

from __future__ import annotations

import datetime
import re
import xml.etree.ElementTree as ET

from ..types import SourceInfo

_BCN_NS = "{http://www.leychile.cl/esquemas}"


def _today() -> str:
    return datetime.date.today().isoformat()


def _pdf_date(value: str | None) -> str | None:
    """Convierte una fecha PDF (``D:YYYYMMDD...``) a ``YYYY-MM-DD``; si no, None."""
    if not value:
        return None
    match = re.search(r"(\d{4})(\d{2})(\d{2})", value)
    if not match:
        return None
    return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"


def from_bcn_xml(body: bytes, url: str) -> SourceInfo:
    """``SourceInfo`` desde el XML de leychile. Campo ausente -> ``None``."""
    base = SourceInfo(url=url, fecha_consulta=_today())
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return base

    def text_at(path: str) -> str | None:
        el = root.find(path)
        if el is None or not el.text:
            return None
        return el.text.strip() or None

    titulo = text_at(f"{_BCN_NS}Metadatos/{_BCN_NS}TituloNorma")
    tipo = text_at(
        f"{_BCN_NS}Identificador/{_BCN_NS}TiposNumeros/{_BCN_NS}TipoNumero/{_BCN_NS}Tipo"
    )
    numero = text_at(
        f"{_BCN_NS}Identificador/{_BCN_NS}TiposNumeros/{_BCN_NS}TipoNumero/{_BCN_NS}Numero"
    )
    tipo_norma = f"{tipo} {numero}" if tipo and numero else tipo
    organo = text_at(f"{_BCN_NS}Identificador/{_BCN_NS}Organismos/{_BCN_NS}Organismo")

    identificador = root.find(f"{_BCN_NS}Identificador")
    fecha = (
        identificador.get("fechaPublicacion") if identificador is not None else None
    ) or None
    version = root.get("fechaVersion") or None

    return SourceInfo(
        titulo=titulo,
        tipo_norma=tipo_norma,
        organo_emisor=organo,
        fecha=fecha,
        version=version,
        url=url,
        fecha_consulta=_today(),
    )


def from_pdf_metadata(meta: dict) -> SourceInfo:
    """``SourceInfo`` desde los metadatos de un PDF (dict de PyMuPDF).

    Solo usa titulo y fecha si vienen; si no hay ninguno, devuelve un ``SourceInfo``
    vacio (sin bloque de fuente). Nunca inventa.
    """
    titulo = (meta.get("title") or "").strip() or None
    fecha = _pdf_date(meta.get("creationDate") or meta.get("modDate"))
    if titulo is None and fecha is None:
        return SourceInfo()
    return SourceInfo(titulo=titulo, fecha=fecha, fecha_consulta=_today())


__all__ = ["from_bcn_xml", "from_pdf_metadata"]
