"""Panel de fuente: de donde sale el documento, y como va la corrida.

Los tres caminos de entrada son los de ADR 0006 y se arman aqui en la misma forma
que espera ``resolve_with_source``: una ruta, una URL, o el texto con el prefijo
``paste:``. La ventana no reimplementa nada de esa capa; solo le entrega la
cadena que corresponde.

La mitad de abajo es FR-10: etapa, fragmento de cuantos, tiempo transcurrido y
Cancelar.
"""

from __future__ import annotations

from PySide6.QtCore import QElapsedTimer, Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..engine.progress import Progress
from ..input import PASTE_PREFIX
from ..types import Nivel

# Etiquetas de nivel para la persona que lee, no los valores internos (ADR 0007).
_NIVELES = (
    ("Publico general", Nivel.PUBLICO),
    ("Tecnico (legisladores y asesores)", Nivel.TECNICO),
)

_FILTRO_ARCHIVOS = "Documentos (*.txt *.pdf);;Todos los archivos (*)"


class SourcePanel(QWidget):
    """Elegir la fuente y el nivel, lanzar la corrida y seguir su avance."""

    explicar = Signal()
    cancelar = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._reloj = QElapsedTimer()
        self._tic = QTimer(self)
        self._tic.setInterval(1000)
        self._tic.timeout.connect(self._actualizar_tiempo)
        self._ultimo_estado = ""
        self._armar()

    # ---------------------------------------------------------------- montaje

    def _armar(self) -> None:
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(12, 12, 6, 12)
        raiz.setSpacing(14)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._pestana_archivo(), "Archivo")
        self.tabs.addTab(self._pestana_pegar(), "Pegar texto")
        self.tabs.addTab(self._pestana_url(), "URL oficial")
        raiz.addWidget(self.tabs, 1)

        opciones = QFormLayout()
        opciones.setContentsMargins(0, 0, 0, 0)
        opciones.setHorizontalSpacing(10)
        self.nivel = QComboBox()
        for etiqueta, valor in _NIVELES:
            self.nivel.addItem(etiqueta, valor)
        self.nivel.setToolTip(
            "Cambia el registro y la profundidad de la explicacion, nunca los hechos."
        )
        opciones.addRow("Nivel de lectura:", self.nivel)
        raiz.addLayout(opciones)

        botones = QHBoxLayout()
        botones.setSpacing(8)
        self.boton_explicar = QPushButton("Explicar")
        self.boton_explicar.setDefault(True)
        # Explicar es la unica accion que importa en este panel; Cancelar solo
        # existe mientras hay algo que cancelar, asi que no compiten en peso.
        self.boton_explicar.setMinimumHeight(38)
        fuerte = QFont(self.boton_explicar.font())
        fuerte.setBold(True)
        self.boton_explicar.setFont(fuerte)
        self.boton_explicar.clicked.connect(self.explicar)
        self.boton_cancelar = QPushButton("Cancelar")
        self.boton_cancelar.setEnabled(False)
        self.boton_cancelar.setMinimumHeight(38)
        self.boton_cancelar.clicked.connect(self.cancelar)
        botones.addWidget(self.boton_explicar, 2)
        botones.addWidget(self.boton_cancelar, 1)
        raiz.addLayout(botones)

        raiz.addWidget(self._caja_estado())

    def _pestana_archivo(self) -> QWidget:
        w = QWidget()
        caja = QVBoxLayout(w)
        fila = QHBoxLayout()
        self.ruta = QLineEdit()
        self.ruta.setPlaceholderText("Ruta a un .txt o .pdf")
        boton = QPushButton("Examinar...")
        boton.clicked.connect(self._elegir_archivo)
        fila.addWidget(self.ruta, 1)
        fila.addWidget(boton)
        caja.addLayout(fila)
        nota = QLabel(
            "Un PDF escaneado se pasa por OCR automaticamente. La explicacion es "
            "tan fiel como el texto que se logre extraer."
        )
        nota.setWordWrap(True)
        caja.addWidget(nota)
        caja.addStretch(1)
        return w

    def _pestana_pegar(self) -> QWidget:
        w = QWidget()
        caja = QVBoxLayout(w)
        self.pegado = QTextEdit()
        self.pegado.setAcceptRichText(False)
        self.pegado.setPlaceholderText("Pegue aqui el texto de la ley o el boletin")
        caja.addWidget(self.pegado)
        return w

    def _pestana_url(self) -> QWidget:
        w = QWidget()
        caja = QVBoxLayout(w)
        self.url = QLineEdit()
        self.url.setPlaceholderText("https://www.bcn.cl/leychile/navegar?idNorma=...")
        caja.addWidget(self.url)
        nota = QLabel("Fuentes oficiales: BCN / LeyChile, Senado y Camara.")
        nota.setWordWrap(True)
        caja.addWidget(nota)
        caja.addStretch(1)
        return w

    def _caja_estado(self) -> QGroupBox:
        caja = QGroupBox("Estado")
        v = QVBoxLayout(caja)
        v.setSpacing(8)
        self.barra = QProgressBar()
        self.barra.setTextVisible(False)
        self.barra.setRange(0, 1)
        self.barra.setValue(0)
        self.barra.setFixedHeight(6)  # una linea, no un bloque: es un dato, no el tema
        v.addWidget(self.barra)
        fila = QHBoxLayout()
        self.etiqueta_estado = QLabel("Listo.")
        self.etiqueta_estado.setWordWrap(True)
        self.etiqueta_tiempo = QLabel("")
        self.etiqueta_tiempo.setAlignment(Qt.AlignmentFlag.AlignRight)
        # El cronometro en monoespaciada para que no baile al cambiar de digito.
        reloj = QFont("Consolas")
        reloj.setStyleHint(QFont.StyleHint.Monospace)
        self.etiqueta_tiempo.setFont(reloj)
        fila.addWidget(self.etiqueta_estado, 1)
        fila.addWidget(self.etiqueta_tiempo)
        v.addLayout(fila)
        return caja

    # ------------------------------------------------------------------ datos

    def source(self) -> str:
        """La fuente en la forma que entiende ``resolve_with_source`` (ADR 0006).

        Levanta ``ValueError`` si el campo de la pestana activa esta vacio, en vez
        de mandar una cadena vacia al engine para que falle mas adentro.
        """
        indice = self.tabs.currentIndex()
        if indice == 0:
            ruta = self.ruta.text().strip()
            if not ruta:
                raise ValueError("Elija un archivo .txt o .pdf.")
            return ruta
        if indice == 1:
            texto = self.pegado.toPlainText().strip()
            if not texto:
                raise ValueError("Pegue el texto de la norma o boletin.")
            return f"{PASTE_PREFIX}{texto}"
        url = self.url.text().strip()
        if not url:
            raise ValueError("Escriba la URL de una fuente oficial.")
        return url

    def nivel_elegido(self) -> Nivel:
        """El nivel como objeto de dominio, no como la cadena que devuelve Qt.

        ``currentData`` convierte el ``StrEnum`` a un ``str`` plano al pasar por
        ``QVariant``. Hoy eso funcionaria igual aguas abajo porque un ``StrEnum``
        compara y hashea como su valor, pero el engine declara ``Nivel`` y aqui
        se le entrega ``Nivel``.
        """
        return Nivel(self.nivel.currentData())

    # ---------------------------------------------------------------- estado

    def _elegir_archivo(self) -> None:
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Abrir ley o boletin", "", _FILTRO_ARCHIVOS
        )
        if ruta:
            self.ruta.setText(ruta)

    def comenzar(self) -> None:
        """Pone la interfaz en modo corrida y arranca el cronometro."""
        self.boton_explicar.setEnabled(False)
        self.boton_cancelar.setEnabled(True)
        self.barra.setRange(0, 0)  # indeterminada hasta saber si hay fragmentos
        self.etiqueta_estado.setText("Preparando...")
        self._ultimo_estado = ""
        self._reloj.start()
        self._actualizar_tiempo()
        self._tic.start()

    def avanzar(self, progreso: Progress) -> None:
        """Refleja un aviso de avance. El porcentaje solo aparece si es real."""
        texto = progreso.texto()
        self._ultimo_estado = texto
        self.etiqueta_estado.setText(texto[:1].upper() + texto[1:])
        if progreso.fragmento is not None and progreso.total:
            self.barra.setRange(0, progreso.total)
            self.barra.setValue(progreso.fragmento)
        else:
            self.barra.setRange(0, 0)

    def terminar(self, resumen: str) -> None:
        """Devuelve la interfaz al reposo y deja escrito como termino."""
        self._tic.stop()
        self.boton_explicar.setEnabled(True)
        self.boton_cancelar.setEnabled(False)
        self.barra.setRange(0, 1)
        self.barra.setValue(1 if resumen.startswith("Listo") else 0)
        self.etiqueta_estado.setText(resumen)

    def _actualizar_tiempo(self) -> None:
        segundos = self._reloj.elapsed() // 1000
        self.etiqueta_tiempo.setText(f"{segundos // 60:02d}:{segundos % 60:02d}")


__all__ = ["SourcePanel"]
