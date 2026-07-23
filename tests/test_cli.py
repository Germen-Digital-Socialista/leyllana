import pytest

from leyllana.cli import _build_parser, main

SAMPLE = "Articulo 1. Esta ley regula la inteligencia artificial en Chile."


def test_parser_requires_a_source():
    with pytest.raises(SystemExit):
        _build_parser().parse_args([])


def test_parser_rejects_two_sources():
    with pytest.raises(SystemExit):
        _build_parser().parse_args(["--paste", "x", "--file", "y.txt"])


def test_cli_paste_hits_phase1_stub(capsys):
    # El proveedor local es un stub: la corrida termina en codigo 4 con un aviso.
    code = main(["--paste", SAMPLE])
    assert code == 4
    assert "Fase 1" in capsys.readouterr().err


def test_cli_empty_paste_reports_unusable(capsys):
    code = main(["--paste", "   "])
    assert code == 2
    assert "utilizable" in capsys.readouterr().err.lower()
