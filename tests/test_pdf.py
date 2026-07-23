"""Tests de extraccion de PDF con PyMuPDF (extra `pdf`, ADR 0011).

Gated con ``importorskip`` para que la suite pase sin el extra instalado; los PDF
de prueba se construyen en el momento con el propio PyMuPDF (fitz).
"""

import pytest

fitz = pytest.importorskip("fitz")

from leyllana.input import resolve  # noqa: E402
from leyllana.input.files import _extract_pdf  # noqa: E402
from leyllana.input.validation import ExtractionError, is_scanned_pdf  # noqa: E402

_FILLER = "palabra " * 20  # texto suficiente para que una pagina cuente como texto


def _make_pdf(path, pages):
    """Escribe un PDF con una lista de textos, uno por pagina, y lo devuelve."""
    doc = fitz.open()
    for body in pages:
        page = doc.new_page()
        if body:
            page.insert_text((72, 72), body)
    doc.save(str(path))
    doc.close()
    return path


def test_extract_pdf_reads_text_layer(tmp_path):
    pdf = _make_pdf(tmp_path / "ley.pdf", ["Articulo 1. Esta ley regula la IA."])
    text = _extract_pdf(pdf)
    assert "Articulo 1" in text
    assert "regula la IA" in text


def test_extract_pdf_joins_pages(tmp_path):
    pdf = _make_pdf(
        tmp_path / "multi.pdf", ["Pagina uno primera.", "Pagina dos segunda."]
    )
    text = _extract_pdf(pdf)
    assert "Pagina uno" in text
    assert "Pagina dos" in text


def test_resolve_pdf_with_text_layer(tmp_path):
    pdf = _make_pdf(
        tmp_path / "ok.pdf", ["Articulo 1. Contenido suficiente para validar."]
    )
    assert "Articulo 1" in resolve(str(pdf))


def test_resolve_scanned_pdf_raises_extraction_error(tmp_path):
    # PDF con paginas sin capa de texto: la extraccion queda vacia y el gate de
    # validacion lo marca para OCR en vez de pasar texto vacio al modelo.
    pdf = _make_pdf(tmp_path / "escaneado.pdf", ["", ""])
    with pytest.raises(ExtractionError):
        resolve(str(pdf))


def test_extract_corrupt_pdf_raises_extraction_error(tmp_path):
    pdf = tmp_path / "roto.pdf"
    pdf.write_bytes(b"%PDF-1.4 esto no es un PDF valido")
    with pytest.raises(ExtractionError):
        _extract_pdf(pdf)


def test_is_scanned_false_for_text_pdf(tmp_path):
    pdf = _make_pdf(tmp_path / "texto.pdf", [_FILLER, _FILLER])
    assert is_scanned_pdf(str(pdf)) is False


def test_is_scanned_true_for_pages_without_text_layer(tmp_path):
    pdf = _make_pdf(tmp_path / "sinTexto.pdf", ["", ""])
    assert is_scanned_pdf(str(pdf)) is True


def test_is_scanned_true_when_large_majority_of_pages_lack_text(tmp_path):
    # Una sola pagina con texto entre muchas sin capa de texto: se trata como
    # escaneado (la gran mayoria de las paginas no tiene texto, ADR 0011).
    pdf = _make_pdf(tmp_path / "mayoria.pdf", [_FILLER, "", "", "", "", ""])
    assert is_scanned_pdf(str(pdf)) is True


def test_clean_text_pdf_does_not_invoke_ocr(tmp_path, monkeypatch):
    # El OCR nunca corre sobre un PDF que ya tiene capa de texto (ADR 0011): si
    # se invocara, este test fallaria en vez de leer la capa de texto.
    import leyllana.input.ocr as ocr_mod

    def _fail(*args, **kwargs):
        raise AssertionError("El OCR no debe correr sobre un PDF con capa de texto")

    monkeypatch.setattr(ocr_mod, "ocr_pdf", _fail)
    pdf = _make_pdf(tmp_path / "limpio.pdf", [_FILLER, _FILLER])
    assert "palabra" in resolve(str(pdf))
