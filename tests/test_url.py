"""Tests del fetch de URL (ADR 0006, patron corpus_fetcher de MuniGPT).

Hermeticos: se monkeypatchea la unica funcion de red (``_http_get``), asi que no
hay trafico real. Se cubren el camino XML de BCN/leychile, el stripping de HTML,
texto plano, PDF por URL, y la deteccion de paginas de error (BCN devuelve HTML
con HTTP 200 cuando limita el ritmo).
"""

import pytest

from leyllana.input import url as url_mod
from leyllana.input.url import fetch
from leyllana.input.validation import ExtractionError

_LEYCHILE_XML = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<Norma xmlns="http://www.leychile.cl/esquemas">'
    b"<Identificador><TipoNumero>Ley 21000</TipoNumero></Identificador>"
    b"<EstructurasFuncionales>"
    b"<Texto>Articulo 1. Esta ley regula la inteligencia artificial.</Texto>"
    b"<Texto>Articulo 2. Los organismos publicos deben transparencia.</Texto>"
    b"</EstructurasFuncionales></Norma>"
)


def _patch_get(monkeypatch, payload: bytes, content_type: str):
    def _get(url, *, timeout=None):
        return payload, content_type

    monkeypatch.setattr(url_mod, "_http_get", _get)


def test_bcn_id_norma_from_url():
    bcn = "https://www.bcn.cl/leychile/navegar?idNorma=1234"
    leychile = "https://www.leychile.cl/Navegar?idNorma=99&x=1"
    assert url_mod._bcn_id_norma(bcn) == "1234"
    assert url_mod._bcn_id_norma(leychile) == "99"


def test_bcn_id_norma_none_for_other_hosts():
    assert url_mod._bcn_id_norma("https://www.senado.cl/boletin/12345") is None
    assert url_mod._bcn_id_norma("https://example.com/?idNorma=1") is None


def test_fetch_bcn_norma_extracts_texto(monkeypatch):
    _patch_get(monkeypatch, _LEYCHILE_XML, "text/xml")
    text = fetch("https://www.bcn.cl/leychile/navegar?idNorma=1234")
    assert "Articulo 1" in text
    assert "inteligencia artificial" in text
    assert "Articulo 2" in text


def test_fetch_bcn_rate_limited_html_raises(monkeypatch):
    # BCN limita el ritmo devolviendo una pagina HTML con HTTP 200, no el XML.
    html = b"<html><body>Demasiadas solicitudes</body></html>"
    _patch_get(monkeypatch, html, "text/html")
    with pytest.raises(ExtractionError):
        fetch("https://www.bcn.cl/leychile/navegar?idNorma=1234")


def test_fetch_generic_html_strips_tags(monkeypatch):
    html = (
        b"<html><head><style>.x{color:red}</style>"
        b"<script>var a=1;</script></head>"
        b"<body><h1>Boletin 12345</h1>"
        b"<p>Crea un nuevo organismo de datos.</p></body></html>"
    )
    _patch_get(monkeypatch, html, "text/html; charset=utf-8")
    text = fetch("https://www.senado.cl/boletin/12345")
    assert "Boletin 12345" in text
    assert "nuevo organismo de datos" in text
    assert "var a=1" not in text  # script no debe filtrarse
    assert "color:red" not in text  # style tampoco


def test_fetch_plain_text_returned(monkeypatch):
    body = b"Articulo unico. Texto plano de una norma."
    _patch_get(monkeypatch, body, "text/plain; charset=utf-8")
    assert "Texto plano" in fetch("https://example.org/norma.txt")


def test_fetch_pdf_routes_through_pdf_pipeline(monkeypatch):
    _patch_get(monkeypatch, b"%PDF-1.5 ...", "application/pdf")
    monkeypatch.setattr(url_mod, "_pdf_bytes_to_text", lambda data: "TEXTO DESDE PDF")
    assert fetch("https://example.org/ley.pdf") == "TEXTO DESDE PDF"
