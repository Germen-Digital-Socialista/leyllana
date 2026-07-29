"""Panel de resultado: el bloque de Fuente, las cuatro secciones y el disclaimer.

El Markdown que se muestra y el que se exporta son el mismo, y es exactamente el
que ya produce la CLI: ``SourceInfo.to_markdown()`` seguido de
``Explanation.to_markdown()``. La ventana no tiene su propio formato de salida;
si lo tuviera, la GUI y la CLI dirian cosas distintas de la misma ley.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
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
from . import theme

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


# Jerarquia tipografica, en puntos relativos al cuerpo elegido por el usuario.
# Los encabezados de seccion tienen que ganarle al texto sin gritar, y el bloque
# de Fuente tiene que perder: son datos de procedencia, no la explicacion.
_SALTO_TITULO = 4
_SALTO_FUENTE = -2


def dar_formato(doc, cuerpo: int, tema: str) -> None:
    """Aplica la jerarquia tipografica al documento ya renderizado.

    Se hace recorriendo bloques y no con una hoja de estilo porque
    ``setDefaultStyleSheet`` **no tiene efecto sobre contenido puesto con**
    ``setMarkdown``: Qt solo la aplica a ``setHtml``. Un CSS ahi se ignora en
    silencio, que es peor que no tenerlo.

    Es puramente de presentacion: no toca el Markdown, asi que lo que se exporta
    sigue siendo carácter por carácter lo que imprime la CLI.

    El unico bloque de lista del documento es el de Fuente, asi que
    ``textList()`` alcanza para reconocerlo sin mirar el contenido.
    """
    cuerpo = max(8, min(32, cuerpo))
    tenue = QColor(theme.color(tema, "dim"))
    normal = QColor(theme.color(tema, "text"))

    enlace = QColor(theme.color(tema, "highlight"))

    bloque = doc.begin()
    while bloque.isValid():
        if bloque.blockFormat().headingLevel():
            titulo = cuerpo + _SALTO_TITULO
            _formatear(bloque, titulo, normal, enlace, True, (cuerpo, 2))
        elif bloque.textList() is not None:
            _formatear(bloque, cuerpo + _SALTO_FUENTE, tenue, enlace, False, (0, 0))
        else:
            _formatear(bloque, cuerpo, normal, enlace, False, (0, cuerpo // 2))
        bloque = bloque.next()


def _formatear(bloque, puntos, color, enlace, negrita, margenes) -> None:
    """Fija tamano, color, peso y margenes de un bloque.

    Se recorre fragmento a fragmento en vez de pintar el bloque de una sola vez
    porque un color plano sobre todo el bloque apaga los enlaces: la URL de la
    fuente quedaba del mismo gris que el resto y dejaba de verse como enlace,
    justo en el bloque que existe para poder ir a comprobar la norma.
    """
    puntos = max(7, puntos)
    iterador = bloque.begin()
    while not iterador.atEnd():
        fragmento = iterador.fragment()
        if fragmento.isValid() and fragmento.length():
            cursor = QTextCursor(bloque.document())
            cursor.setPosition(fragmento.position())
            cursor.setPosition(
                fragmento.position() + fragmento.length(),
                QTextCursor.MoveMode.KeepAnchor,
            )
            letra = QTextCharFormat()
            letra.setFontPointSize(puntos)
            letra.setForeground(enlace if fragmento.charFormat().isAnchor() else color)
            if negrita:
                letra.setFontWeight(QFont.Weight.Bold)
            cursor.mergeCharFormat(letra)
        iterador += 1

    arriba, abajo = margenes
    formato = bloque.blockFormat()
    formato.setTopMargin(arriba)
    formato.setBottomMargin(abajo)
    QTextCursor(bloque).setBlockFormat(formato)


class ResultPanel(QWidget):
    """Muestra la explicacion y la exporta a Markdown (FR-8)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._markdown = ""
        self._titulo_sugerido = "explicacion"
        self._cuerpo = 14
        self._tema = theme.CLARO

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(10)
        self.vista = QTextBrowser()
        self.vista.setOpenExternalLinks(True)
        self.vista.setFrameShape(QTextBrowser.Shape.NoFrame)
        # Margen interno propio: un texto legal pegado al borde de la ventana se
        # lee peor, y esto es lo que se mira durante minutos.
        self.vista.document().setDocumentMargin(20)
        raiz.addWidget(self.vista, 1)

        fila = QHBoxLayout()
        fila.addStretch(1)
        self.boton_exportar = QPushButton("Exportar a Markdown...")
        self.boton_exportar.setEnabled(False)
        self.boton_exportar.clicked.connect(self.exportar)
        fila.addWidget(self.boton_exportar)
        raiz.addLayout(fila)

        self.aplicar_estilo(self._cuerpo, self._tema)

    def mostrar(self, explicacion: Explanation, info: SourceInfo) -> None:
        self._markdown = componer(explicacion, info)
        self._titulo_sugerido = _nombre_archivo(info)
        self._repintar()
        self.boton_exportar.setEnabled(True)

    def limpiar(self) -> None:
        self._markdown = ""
        self._repintar()
        self.boton_exportar.setEnabled(False)

    def aplicar_estilo(self, puntos: int, tema: str) -> None:
        """Fija el cuerpo de letra y el tema, y repinta (accesibilidad visual).

        Hay que reponer el Markdown: Qt aplica la hoja de estilo al convertirlo,
        asi que cambiarla sin repintar no se nota.
        """
        self._cuerpo = max(8, min(32, puntos))
        self._tema = tema
        fuente = QFont(self.vista.font())
        fuente.setPointSize(self._cuerpo)
        self.vista.setFont(fuente)
        self._repintar()

    def aplicar_cuerpo(self, puntos: int) -> None:
        """Solo el tamano de letra, dejando el tema como esta."""
        self.aplicar_estilo(puntos, self._tema)

    def _repintar(self) -> None:
        self.vista.setMarkdown(self._markdown or _VACIO)
        dar_formato(self.vista.document(), self._cuerpo, self._tema)

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


__all__ = ["ResultPanel", "componer", "dar_formato"]
