"""Arranque de la aplicacion de escritorio (ADR 0002).

Carga la config, aplica el tema, abre la ventana y entrega el control al bucle de
eventos de Qt. Nada de red ni de modelo corre aqui: el ``llama-server`` no se
levanta hasta la primera explicacion.
"""

from __future__ import annotations

import argparse
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .. import __version__
from ..config import load, resolve_path
from . import assets, theme
from .main_window import MainWindow
from .session import Session


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="leyllana-gui",
        description=(
            "Explica leyes y boletines chilenos en lenguaje llano (local-first). "
            "Interfaz de escritorio."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"leyllana {__version__}"
    )
    parser.add_argument(
        "--config",
        metavar="RUTA",
        default=None,
        help="ruta a leyllana.toml (por defecto: ./leyllana.toml si existe)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada de la GUI. Devuelve el codigo de salida de Qt."""
    args = _parser().parse_args(argv)
    ruta = resolve_path(args.config)
    config = load(args.config)

    app = QApplication(sys.argv[:1])
    app.setApplicationName("leyllana")
    app.setApplicationDisplayName("leyllana")
    icono = assets.ruta(assets.ICONO)
    if icono is not None:
        app.setWindowIcon(QIcon(str(icono)))
    theme.aplicar(app, config.gui.theme)

    ventana = MainWindow(Session(config, ruta))
    ventana.show()
    return app.exec()


__all__ = ["main"]
