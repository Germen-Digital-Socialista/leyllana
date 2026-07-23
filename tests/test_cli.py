import pytest

from leyllana.cli import _build_parser, main

SAMPLE = "Articulo 1. Esta ley regula la inteligencia artificial en Chile."


def test_parser_requires_a_source():
    with pytest.raises(SystemExit):
        _build_parser().parse_args([])


def test_parser_rejects_two_sources():
    with pytest.raises(SystemExit):
        _build_parser().parse_args(["--paste", "x", "--file", "y.txt"])


def test_cli_paste_unconfigured_local_reports_provider_error(capsys, tmp_path):
    # Sin server_path ni modelo configurados, el proveedor local falla ruidosamente
    # (codigo 5), no de forma cruda. --config apunta a un TOML inexistente para no
    # depender de un leyllana.toml en el cwd.
    code = main(["--paste", SAMPLE, "--config", str(tmp_path / "no-existe.toml")])
    assert code == 5
    assert "generar" in capsys.readouterr().err.lower()


def test_cli_empty_paste_reports_unusable(capsys):
    code = main(["--paste", "   "])
    assert code == 2
    assert "utilizable" in capsys.readouterr().err.lower()
