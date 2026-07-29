"""Panel de resultado: el bloque de Fuente, las cuatro secciones y el disclaimer.

El Markdown que se muestra y el que se exporta son el mismo, y es exactamente el
que ya produce la CLI: ``SourceInfo.to_markdown()`` seguido de
``Explanation.to_markdown()``. La ventana no tiene su propio formato de salida;
si lo tuviera, la GUI y la CLI dirian cosas distintas de la misma ley.
"""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..types import Explanation, SourceInfo

_VACIO = (
    "Cargue una ley o un boletin en el panel de la izquierda y presione "
    "**Explicar**.\n\n"
    "leyllana solo explica lo que dice el texto que usted entrega. No consulta "
    "otras fuentes ni completa lo que falte."
)


def componer(explicacion: Explanation, info: SourceInfo) -> str:
    """Arma el Markdown completo, igual que hace la CLI al imprimir."""
    salida = explicacion.to_markdown()
    if not info.is_empty():
        salida = info.to_markdown() + "\n" + salida
    return salida


class ResultPanel(QWidget):
    """Muestra la explicacion y la exporta a Markdown (FR-8)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._markdown = ""
        self._titulo_sugerido = "explicacion"

        raiz = QVBoxLayout(self)
        self.vista = QTextBrowser()
        self.vista.setOpenExternalLinks(True)
        self.vista.setMarkdown(_VACIO)
        raiz.addWidget(self.vista, 1)

        fila = QHBoxLayout()
        fila.addStretch(1)
        self.boton_exportar = QPushButton("Exportar a Markdown...")
        self.boton_exportar.setEnabled(False)
        self.boton_exportar.clicked.connect(self.exportar)
        fila.addWidget(self.boton_exportar)
        raiz.addLayout(fila)

    def mostrar(self, explicacion: Explanation, info: SourceInfo) -> None:
        self._markdown = componer(explicacion, info)
        self._titulo_sugerido = _nombre_archivo(info)
        self.vista.setMarkdown(self._markdown)
        self.boton_exportar.setEnabled(True)

    def limpiar(self) -> None:
        self._markdown = ""
        self.vista.setMarkdown(_VACIO)
        self.boton_exportar.setEnabled(False)

    def aplicar_cuerpo(self, puntos: int) -> None:
        """Cambia el tamano de letra del texto (accesibilidad visual)."""
        fuente = QFont(self.vista.font())
        fuente.setPointSize(max(8, min(32, puntos)))
        self.vista.setFont(fuente)
        self.vista.setMarkdown(self._markdown or _VACIO)

    def exportar(self) -> None:
        if not self._markdown:
            return
        ruta, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar explicacion",
            f"{self._titulo_sugerido}.md",
            "Markdown (*.md);;Todos los archivos (*)",
        )
        if not ruta:
            return
        try:
            with open(ruta, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(self._markdown)
        except OSError as exc:
            QMessageBox.warning(self, "No se pudo guardar", f"Error: {exc}")


def _nombre_archivo(info: SourceInfo) -> str:
    """Nombre sugerido a partir del titulo de la fuente, si lo hay."""
    if not info.titulo:
        return "explicacion"
    limpio = "".join(c if c.isalnum() or c in " -_" else " " for c in info.titulo)
    return " ".join(limpio.split())[:60] or "explicacion"


__all__ = ["ResultPanel", "componer"]
