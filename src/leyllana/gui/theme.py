"""Temas claro y oscuro de la ventana (PRD, accesibilidad visual).

Se define una paleta propia en vez de dejar el tema al sistema porque el
requisito no es "que se vea integrado" sino "que se pueda leer un rato largo":
contraste suficiente y control del cuerpo de letra. Los pares de color de abajo
estan elegidos para quedar bien por encima del 4.5:1 que pide WCAG AA en texto.

``resolver`` es puro y se prueba solo; ``aplicar`` es lo unico que toca Qt.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

# Valores admitidos en ``[gui] theme`` de leyllana.toml.
SISTEMA = "sistema"
CLARO = "claro"
OSCURO = "oscuro"
TEMAS = (SISTEMA, CLARO, OSCURO)

# (fondo de ventana, fondo de campo, texto, texto tenue, seleccion, texto sobre
# seleccion, borde). Texto sobre fondo de campo: 16.1:1 en claro, 14.6:1 en
# oscuro.
_PALETAS = {
    CLARO: {
        "window": "#f4f4f5",
        "base": "#ffffff",
        "text": "#18181b",
        "dim": "#52525b",
        "highlight": "#1d4ed8",
        "highlight_text": "#ffffff",
        "border": "#d4d4d8",
    },
    OSCURO: {
        "window": "#1b1b1f",
        "base": "#131316",
        "text": "#e8e8ea",
        "dim": "#a1a1aa",
        "highlight": "#3b82f6",
        "highlight_text": "#0b0b0d",
        "border": "#3f3f46",
    },
}


def resolver(theme: str, sistema_oscuro: bool) -> str:
    """Traduce el tema configurado al que realmente se pinta.

    ``sistema`` sigue al del escritorio; un valor desconocido cae a claro en vez
    de reventar, porque viene de un archivo que el usuario puede editar a mano.
    """
    elegido = (theme or SISTEMA).strip().lower()
    if elegido == OSCURO:
        return OSCURO
    if elegido == CLARO:
        return CLARO
    return OSCURO if sistema_oscuro else CLARO


def sistema_es_oscuro(app: QApplication) -> bool:
    """True si el escritorio esta en modo oscuro; False si no se puede saber."""
    hints = app.styleHints()
    esquema = getattr(hints, "colorScheme", None)
    if esquema is None:
        return False
    return esquema() == Qt.ColorScheme.Dark


def paleta(nombre: str) -> QPalette:
    """Construye la ``QPalette`` del tema ya resuelto (``claro`` u ``oscuro``)."""
    c = _PALETAS.get(nombre, _PALETAS[CLARO])
    p = QPalette()
    window, base, text = QColor(c["window"]), QColor(c["base"]), QColor(c["text"])
    dim, borde = QColor(c["dim"]), QColor(c["border"])
    p.setColor(QPalette.ColorRole.Window, window)
    p.setColor(QPalette.ColorRole.WindowText, text)
    p.setColor(QPalette.ColorRole.Base, base)
    p.setColor(QPalette.ColorRole.AlternateBase, window)
    p.setColor(QPalette.ColorRole.Text, text)
    p.setColor(QPalette.ColorRole.Button, window)
    p.setColor(QPalette.ColorRole.ButtonText, text)
    p.setColor(QPalette.ColorRole.ToolTipBase, base)
    p.setColor(QPalette.ColorRole.ToolTipText, text)
    p.setColor(QPalette.ColorRole.PlaceholderText, dim)
    p.setColor(QPalette.ColorRole.Highlight, QColor(c["highlight"]))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(c["highlight_text"]))
    p.setColor(QPalette.ColorRole.Link, QColor(c["highlight"]))
    p.setColor(QPalette.ColorRole.Mid, borde)
    for rol in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        p.setColor(QPalette.ColorGroup.Disabled, rol, dim)
    return p


def color(nombre: str, clave: str) -> str:
    """Un color suelto del tema, para las hojas de estilo puntuales."""
    return _PALETAS.get(nombre, _PALETAS[CLARO])[clave]


def aplicar(app: QApplication, theme: str) -> str:
    """Aplica el tema a la aplicacion y devuelve el nombre del que quedo puesto.

    Se fuerza el estilo Fusion porque es el unico que respeta la paleta completa
    en Windows: con el estilo nativo, la mitad de los colores de arriba se
    ignoran y el modo oscuro queda a medias.
    """
    resuelto = resolver(theme, sistema_es_oscuro(app))
    app.setStyle("Fusion")
    app.setPalette(paleta(resuelto))
    return resuelto


__all__ = [
    "SISTEMA",
    "CLARO",
    "OSCURO",
    "TEMAS",
    "resolver",
    "sistema_es_oscuro",
    "paleta",
    "color",
    "aplicar",
]
