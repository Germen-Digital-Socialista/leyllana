"""Capa de interfaz grafica: la aplicacion de escritorio PySide6 (ADR 0002).

Sabe de las capas ``input``, ``engine`` y ``config``; ninguna de ellas sabe de
esta. Todo lo que se puede probar sin abrir una ventana (temas, composicion del
Markdown, traduccion de errores, sesion) vive en modulos aparte y no importa
nada de la ventana.

``main`` se importa de forma perezosa para que ``import leyllana.gui`` no exija
tener PySide6 instalado: el paquete base no lo lleva, es el extra ``gui``.
"""

from __future__ import annotations


def main(argv: list[str] | None = None) -> int:
    """Arranca la aplicacion de escritorio. Ver ``leyllana.gui.app.main``."""
    try:
        from .app import main as _main
    except ImportError as exc:  # pragma: no cover - depende de la instalacion
        raise SystemExit(
            "Falta PySide6. Instale el extra de interfaz grafica:\n"
            "    uv sync --extra gui\n"
            f"(detalle: {exc})"
        ) from exc
    return _main(argv)


__all__ = ["main"]
