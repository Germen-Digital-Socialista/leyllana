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


def test_resolve_url_not_implemented():
    with pytest.raises(NotImplementedError):
        resolve("https://www.bcn.cl/leychile/navegar?idNorma=1")


def test_validate_text_passes_usable():
    assert validate_text(SAMPLE) == SAMPLE
