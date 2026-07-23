"""Tests del OCR de respaldo (extra `ocr` + binarios Tesseract/Poppler, ADR 0011).

Los tests de la logica de agregacion y de los umbrales (confianza / vacio) usan
``monkeypatch`` sobre las costuras ``_render_pages`` / ``_ocr_image`` y no
necesitan los binarios de sistema; solo el round-trip real los requiere y se
salta con ``skipif`` cuando faltan.
"""

import io
import shutil
from pathlib import Path

import pytest

pytest.importorskip("pytesseract")
pytest.importorskip("pdf2image")
fitz = pytest.importorskip("fitz")
pytest.importorskip("PIL")

from leyllana.input import ocr as ocr_mod  # noqa: E402
from leyllana.input.ocr import TESSERACT_EXE, ocr_pdf  # noqa: E402
from leyllana.input.validation import ExtractionError  # noqa: E402


def _binaries_available():
    tess = Path(TESSERACT_EXE).exists() or shutil.which("tesseract")
    poppler = shutil.which("pdftoppm")
    return bool(tess and poppler)


needs_binaries = pytest.mark.skipif(
    not _binaries_available(), reason="Requiere Tesseract y Poppler instalados"
)


def _make_scanned_pdf(path, lines):
    """PDF de una pagina cuyo contenido es una IMAGEN de texto (sin capa de texto).

    ``lines`` es una lista de renglones; se dibujan varios para que el OCR
    produzca texto de largo realista (por encima del piso de "vacio").
    """
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (1654, 600), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 56)
    except OSError:
        font = ImageFont.load_default()
    for i, line in enumerate(lines):
        draw.text((60, 80 + i * 90), line, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    doc = fitz.open()
    page = doc.new_page(width=img.width, height=img.height)
    page.insert_image(page.rect, stream=buf.getvalue())
    doc.save(str(path))
    doc.close()
    return path


@needs_binaries
def test_ocr_reads_scanned_page(tmp_path):
    pdf = _make_scanned_pdf(
        tmp_path / "escaneado.pdf",
        ["ARTICULO PRIMERO DE LA LEY", "REGULA LA INTELIGENCIA ARTIFICIAL"],
    )
    with fitz.open(str(pdf)) as d:  # el PDF no tiene capa de texto
        assert "".join(p.get_text() for p in d).strip() == ""
    text = ocr_pdf(str(pdf))
    assert "ARTICULO" in text.upper()
    assert "INTELIGENCIA" in text.upper()


def test_ocr_rasterization_failure_raises(monkeypatch, tmp_path):
    # Poppler ausente / PDF ilegible: se avisa como ExtractionError, no en silencio.
    def _boom(path, dpi):
        raise OSError("poppler no encontrado")

    monkeypatch.setattr(ocr_mod, "_render_pages", _boom)
    with pytest.raises(ExtractionError):
        ocr_pdf(str(tmp_path / "x.pdf"))


def test_ocr_low_confidence_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr_mod, "_render_pages", lambda path, dpi: [object()])
    monkeypatch.setattr(
        ocr_mod,
        "_ocr_image",
        lambda image, lang: ("texto ilegible basura", [12, 20, 8]),
    )
    with pytest.raises(ExtractionError):
        ocr_pdf(str(tmp_path / "x.pdf"))


def test_ocr_accepts_good_confidence(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr_mod, "_render_pages", lambda path, dpi: [object()])
    monkeypatch.setattr(
        ocr_mod,
        "_ocr_image",
        lambda image, lang: ("Articulo primero de la ley", [95, 92, 90]),
    )
    assert "Articulo" in ocr_pdf(str(tmp_path / "x.pdf"))


def test_ocr_empty_result_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr_mod, "_render_pages", lambda path, dpi: [object()])
    monkeypatch.setattr(ocr_mod, "_ocr_image", lambda image, lang: ("", []))
    with pytest.raises(ExtractionError):
        ocr_pdf(str(tmp_path / "x.pdf"))


@needs_binaries
def test_resolve_routes_scanned_pdf_to_ocr(tmp_path):
    # Extremo a extremo: un PDF sin capa de texto se enruta al OCR de respaldo y
    # resolve devuelve el texto leido (extract -> scanned-detect -> OCR, ADR 0011).
    from leyllana.input import resolve

    pdf = _make_scanned_pdf(
        tmp_path / "scan.pdf",
        ["ARTICULO PRIMERO DE LA LEY", "REGULA LA INTELIGENCIA ARTIFICIAL"],
    )
    text = resolve(str(pdf))
    assert "ARTICULO" in text.upper()
    assert "INTELIGENCIA" in text.upper()
