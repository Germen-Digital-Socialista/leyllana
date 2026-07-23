import pytest

from leyllana.input import resolve
from leyllana.input.validation import ExtractionError, validate_text

SAMPLE = "Articulo 1. Esta ley regula el uso de sistemas de inteligencia artificial."


def test_resolve_paste_returns_text():
    assert resolve(f"paste:{SAMPLE}") == SAMPLE


def test_resolve_paste_empty_raises():
    with pytest.raises(ExtractionError):
        resolve("paste:   ")


def test_resolve_unknown_suffix_raises_value_error():
    with pytest.raises(ValueError):
        resolve("archivo.docx")


def test_resolve_corrupt_pdf_raises_extraction_error(tmp_path):
    # Bytes que no son un PDF valido: se marca como extraccion fallida (ADR 0011),
    # nunca se pasa texto malo al modelo. Sin el extra `pdf` instalado el mismo
    # error avisa que falta la dependencia; en ambos casos es ExtractionError.
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    with pytest.raises(ExtractionError):
        resolve(str(pdf))


def test_resolve_url_dispatches_to_fetch(monkeypatch):
    # resolve enruta http(s) a url.fetch; se monkeypatchea la red (sin trafico real)
    # y se valida que el texto descargado pase por el gate de validacion.
    from leyllana.input import url as url_mod

    xml = (
        b'<Norma xmlns="http://www.leychile.cl/esquemas">'
        b"<Texto>Articulo 1. Regula la inteligencia artificial en el Estado.</Texto>"
        b"</Norma>"
    )
    monkeypatch.setattr(
        url_mod, "_http_get", lambda u, *, timeout=None: (xml, "text/xml")
    )
    text = resolve("https://www.bcn.cl/leychile/navegar?idNorma=1")
    assert "inteligencia artificial" in text


def test_validate_text_passes_usable():
    assert validate_text(SAMPLE) == SAMPLE


def test_resolve_with_source_paste_has_empty_info():
    from leyllana.input import resolve_with_source

    text, info = resolve_with_source(f"paste:{SAMPLE}")
    assert text == SAMPLE
    assert info.is_empty()  # texto pegado: sin procedencia


def test_resolve_with_source_txt_has_empty_info(tmp_path):
    from leyllana.input import resolve_with_source

    p = tmp_path / "ley.txt"
    p.write_text(
        "Articulo 1. Texto suficiente para pasar la validacion.", encoding="utf-8"
    )
    text, info = resolve_with_source(str(p))
    assert "Articulo 1" in text
    assert info.is_empty()  # .txt pelado: sin metadatos


def test_resolve_with_source_bcn_url_has_metadata(monkeypatch):
    from leyllana.input import resolve_with_source
    from leyllana.input import url as url_mod

    xml = (
        b'<Norma xmlns="http://www.leychile.cl/esquemas" fechaVersion="2026-02-05">'
        b'<Identificador fechaPublicacion="2003-05-29"><TiposNumeros><TipoNumero>'
        b"<Tipo>Ley</Tipo><Numero>19880</Numero></TipoNumero></TiposNumeros>"
        b"</Identificador>"
        b"<Metadatos><TituloNorma>ESTABLECE BASES</TituloNorma></Metadatos>"
        b"<Texto>Articulo 1. Contenido suficiente para validar.</Texto></Norma>"
    )
    monkeypatch.setattr(
        url_mod, "_http_get", lambda u, *, timeout=None: (xml, "text/xml")
    )
    text, info = resolve_with_source(
        "https://www.bcn.cl/leychile/navegar?idNorma=210676"
    )
    assert "Articulo 1" in text
    assert info.titulo == "ESTABLECE BASES"
    assert info.tipo_norma == "Ley 19880"
    assert info.url.endswith("210676")
