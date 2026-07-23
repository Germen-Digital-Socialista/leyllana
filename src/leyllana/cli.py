"""CLI headless de leyllana (ROADMAP Fase 1).

Resuelve una fuente (archivo/pegado/URL) a texto, la explica en el nivel elegido
e imprime las cuatro secciones en Markdown. Sin GUI. En el esqueleto de Fase 1 el
proveedor local es un stub, asi que una corrida completa termina avisando que la
generacion aun no esta implementada, en vez de fallar de forma cruda.
"""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .engine import ParseError, explain
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
    return parser


def _source_from_args(args: argparse.Namespace) -> str:
    if args.file is not None:
        return args.file
    if args.url is not None:
        return args.url
    return f"paste:{args.paste}"


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada de la CLI. Devuelve un codigo de salida (0 = ok)."""
    args = _build_parser().parse_args(argv)
    try:
        text = resolve(_source_from_args(args))
        explanation = explain(text, Nivel(args.nivel))
    except ExtractionError as exc:
        print(f"Entrada no utilizable: {exc}", file=sys.stderr)
        return 2
    except ParseError as exc:
        print(f"Respuesta del modelo no valida: {exc}", file=sys.stderr)
        return 3
    except NotImplementedError as exc:
        print(f"Funcionalidad de Fase 1 aun no implementada: {exc}", file=sys.stderr)
        return 4
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(explanation.to_markdown())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
