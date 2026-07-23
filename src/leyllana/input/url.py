"""Fetch de una fuente oficial por URL (BCN/leychile, Senado/Camara, ADR 0006).

Reutiliza el patron de ``corpus_fetcher`` de MuniGPT:

- Para una norma de BCN/leychile (URL con ``idNorma``) se usa la API XML
  ``obtxml?opt=7``, que devuelve el texto estructurado; se extraen los elementos
  ``<Texto>``. BCN exige un ``User-Agent`` de navegador y limita el ritmo
  devolviendo HTML con HTTP 200, lo que se detecta y se marca (ADR 0011).
- Para otras paginas HTML (Senado/Camara, genericas) se extrae el texto visible
  con el ``html.parser`` de la biblioteca estandar (best-effort).
- Un PDF servido por URL se enruta al pipeline de PDF de Fase 1 (extraccion,
  deteccion de escaneo, OCR de respaldo).

Todo con la biblioteca estandar (``urllib``): sin dependencias pip para el fetch.
Es el unico toque de red del camino por defecto (ADR 0005), solo hacia una fuente
publica que el usuario nombro explicitamente.
"""

from __future__ import annotations

import os
import tempfile
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse

from ..types import SourceInfo
from . import source
from .validation import ExtractionError

# API XML de leychile: texto estructurado de cualquier norma (MuniGPT, opt=7).
_BCN_XML_URL = "https://www.bcn.cl/leychile/consulta/obtxml?opt=7&idNorma={id}"
_BCN_NS = "{http://www.leychile.cl/esquemas}"
_BCN_HOSTS = ("bcn.cl", "leychile.cl")

# BCN devuelve vacio sin un User-Agent de navegador.
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_TIMEOUT = 60.0
_MAX_BYTES = 25 * 1024 * 1024  # tope de descarga para no traer algo enorme


def _bcn_id_norma(url: str) -> str | None:
    """Devuelve el ``idNorma`` si ``url`` es una norma de BCN/leychile, si no None."""
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if not any(host == h or host.endswith("." + h) for h in _BCN_HOSTS):
        return None
    # parse de query case-insensitive para la clave idNorma.
    for key, values in parse_qs(parsed.query).items():
        if key.lower() == "idnorma" and values:
            return values[0]
    return None


def _http_get(url: str, *, timeout: float = _TIMEOUT) -> tuple[bytes, str]:
    """GET con ``urllib`` (User-Agent de navegador). Devuelve ``(cuerpo, ctype)``.

    Sigue redirecciones (comportamiento por defecto de ``urlopen``) y limita el
    tamano. Los fallos de red se marcan como ``ExtractionError`` (ADR 0011).
    """
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            content_type = resp.headers.get("Content-Type", "").lower()
            body = resp.read(_MAX_BYTES + 1)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ExtractionError(f"No se pudo descargar la URL: {url} ({exc})") from exc
    if len(body) > _MAX_BYTES:
        raise ExtractionError(
            f"La descarga supera el tope de {_MAX_BYTES} bytes: {url}"
        )
    return body, content_type


def _charset(content_type: str) -> str:
    for part in content_type.split(";"):
        part = part.strip()
        if part.startswith("charset="):
            return part[len("charset=") :].strip() or "utf-8"
    return "utf-8"


def _decode(body: bytes, content_type: str) -> str:
    try:
        return body.decode(_charset(content_type))
    except (LookupError, UnicodeDecodeError):
        return body.decode("utf-8", errors="replace")


class _TextExtractor(HTMLParser):
    """Extrae texto visible de HTML, saltando script/style/head."""

    _SKIP = frozenset({"script", "style", "head", "noscript"})

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in self._SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self.parts.append(text)


def _html_to_text(body: bytes, content_type: str) -> str:
    parser = _TextExtractor()
    parser.feed(_decode(body, content_type))
    return "\n".join(parser.parts)


def _xml_to_text(body: bytes) -> str:
    """Extrae y une los elementos ``<Texto>`` del XML de leychile."""
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise ExtractionError(f"XML de leychile no valido: {exc}") from exc
    textos = [(el.text or "").strip() for el in root.iter(f"{_BCN_NS}Texto")]
    return "\n".join(t for t in textos if t)


def _pdf_bytes_to_text(data: bytes) -> str:
    """Guarda el PDF en un temporal y lo pasa por el pipeline de PDF de Fase 1."""
    from .files import read_file

    fd, tmp = tempfile.mkstemp(suffix=".pdf")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        return read_file(tmp)
    finally:
        os.unlink(tmp)


def _fetch_bcn_norma(id_norma: str, url: str) -> tuple[str, SourceInfo]:
    body, content_type = _http_get(_BCN_XML_URL.format(id=id_norma))
    if "html" in content_type:
        raise ExtractionError(
            "BCN devolvio HTML en vez del XML de la norma (posible limite de ritmo "
            f"o idNorma inexistente): idNorma={id_norma}."
        )
    text = _xml_to_text(body)
    if not text:
        raise ExtractionError(
            f"El XML de leychile no trajo texto para idNorma={id_norma}."
        )
    return text, source.from_bcn_xml(body, url)


def fetch_with_source(url: str) -> tuple[str, SourceInfo]:
    """Descarga una fuente y devuelve ``(texto, SourceInfo)`` (ADR 0006, FR-7.1).

    Norma de BCN/leychile -> API XML (texto + metadatos del mismo fetch); PDF ->
    pipeline de PDF; HTML -> texto visible; texto plano -> tal cual. Para una URL no
    BCN la procedencia es la propia URL y la fecha de consulta. Fallos ->
    ``ExtractionError``.
    """
    id_norma = _bcn_id_norma(url)
    if id_norma is not None:
        return _fetch_bcn_norma(id_norma, url)

    body, content_type = _http_get(url)
    info = SourceInfo(url=url, fecha_consulta=source._today())
    if "application/pdf" in content_type or body[:5] == b"%PDF-":
        return _pdf_bytes_to_text(body), info
    if "html" in content_type:
        return _html_to_text(body, content_type), info
    if "xml" in content_type:
        return _xml_to_text(body), info
    return _decode(body, content_type), info


def fetch(url: str) -> str:
    """Descarga una fuente oficial y devuelve su texto crudo (ADR 0006)."""
    return fetch_with_source(url)[0]


__all__ = ["fetch", "fetch_with_source"]
