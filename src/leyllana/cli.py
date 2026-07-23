"""CLI headless de leyllana (ROADMAP Fase 1).

Resuelve una fuente (archivo/pegado/URL) a texto, la explica en el nivel elegido
e imprime las cuatro secciones en Markdown. Sin GUI. La ejecucion del modelo local
(binario y ruta al GGUF) viene de la config (``leyllana.toml`` o ``--config``); si
no esta configurada, la corrida termina avisando de forma clara en vez de fallar de
forma cruda.
"""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .config import load
from .engine import ParseError, explain
from .engine.base import ProviderError
from .input import resolve
from .input.validation import ExtractionError
from .types import Nivel


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="leyllana",
        description=(
            "Explica leyes y boletines chilenos en lenguaje llano (local-first)."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"leyllana {__version__}"
    )
    fuente = parser.add_mutually_exclusive_group(required=True)
    fuente.add_argument("--file", metavar="RUTA", help="archivo local .txt o .pdf")
    fuente.add_argument("--paste", metavar="TEXTO", help="texto pegado directo")
    fuente.add_argument(
        "--url", metavar="URL", help="URL de fuente oficial (BCN/Senado/Camara)"
    )
    parser.add_argument(
        "--nivel",
        choices=[n.value for n in Nivel],
        default=Nivel.PUBLICO.value,
        help="registro de audiencia (por defecto: publico)",
    )
    parser.add_argument(
        "--config",
        metavar="RUTA",
        default=None,
        help="ruta a leyllana.toml (por defecto: ./leyllana.toml si existe)",
    )
    return parser


def _force_utf8_output() -> None:
    """Fuerza UTF-8 en stdout/stderr para que los acentos del espanol no se rompan.

    En consolas Windows con code page heredada (cp1252) el texto en UTF-8 se ve
    mal; reconfigurar la salida a UTF-8 lo corrige. Es best-effort: si el stream no
    soporta ``reconfigure``, se deja como esta.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def _source_from_args(args: argparse.Namespace) -> str:
    if args.file is not None:
        return args.file
    if args.url is not None:
        return args.url
    return f"paste:{args.paste}"


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada de la CLI. Devuelve un codigo de salida (0 = ok)."""
    _force_utf8_output()
    args = _build_parser().parse_args(argv)
    try:
        config = load(args.config)
        text = resolve(_source_from_args(args))
        explanation = explain(text, Nivel(args.nivel), config)
    except ExtractionError as exc:
        print(f"Entrada no utilizable: {exc}", file=sys.stderr)
        return 2
    except ParseError as exc:
        print(f"Respuesta del modelo no valida: {exc}", file=sys.stderr)
        return 3
    except NotImplementedError as exc:
        print(f"Funcionalidad aun no disponible: {exc}", file=sys.stderr)
        return 4
    except ProviderError as exc:
        print(f"No se pudo generar la explicacion: {exc}", file=sys.stderr)
        return 5
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(explanation.to_markdown())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
