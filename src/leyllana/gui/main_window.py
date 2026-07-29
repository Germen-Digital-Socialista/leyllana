"""La ventana: fuente a la izquierda, resultado a la derecha, terminal abajo.

El splitter es deliberado. Comprobar una explicacion contra su fuente (FR-6.1) es
mirar las dos cosas a la vez; en pestanas separadas habria que ir y volver de
memoria, que es justo lo que la cita verbatim de ADR 0014 trata de evitar.

Esta clase es el unico lugar que orquesta: reune sesion, hilo, consentimiento y
paneles. La logica que se puede probar sin ventana no vive aqui.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThread, Signal
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDockWidget,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
)

from ..config import Config
from ..engine.trace import TraceEvent
from ..types import Explanation, SourceInfo
from . import assets, theme
from .consent_dialog import pedir_consentimiento
from .errors import mensaje
from .result_panel import ResultPanel
from .session import Session
from .settings_dialog import SettingsDialog
from .source_panel import SourcePanel
from .terminal_panel import TerminalPanel
from .worker import ExplainWorker

TITULO = "leyllana"


class MainWindow(QMainWindow):
    """Ventana principal de leyllana."""

    # La traza la emite el proveedor desde el hilo de trabajo (ADR 0022). Pasa por
    # una senal para que Qt la entregue en cola al hilo de la interfaz: el panel
    # de terminal es un widget y no se toca desde otro hilo.
    traza = Signal(TraceEvent)

    def __init__(self, session: Session) -> None:
        super().__init__()
        self._session = session
        self._hilo: QThread | None = None
        self._worker: ExplainWorker | None = None

        self.setWindowTitle(TITULO)
        self.resize(1180, 760)

        self.source_panel = SourcePanel()
        self.result_panel = ResultPanel()
        self.source_panel.explicar.connect(self.explicar)
        self.source_panel.cancelar.connect(self.cancelar)

        divisor = QSplitter(Qt.Orientation.Horizontal)
        divisor.addWidget(self.source_panel)
        divisor.addWidget(self.result_panel)
        divisor.setStretchFactor(0, 2)
        divisor.setStretchFactor(1, 3)
        divisor.setChildrenCollapsible(False)
        divisor.setHandleWidth(8)
        # El panel de fuente no necesita crecer; el de resultado si, porque ahi va
        # el texto que se lee. Arrancar al 40/60 y no a la mitad.
        divisor.setSizes([460, 700])
        self.setCentralWidget(divisor)

        self.terminal = TerminalPanel()
        self._dock = QDockWidget("Terminal", self)
        self._dock.setWidget(self.terminal)
        self._dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._dock)
        self._dock.hide()
        # Un tercio de la ventana es demasiado para un panel auxiliar: la
        # explicacion es lo que se lee. Alto suficiente para ver una invocacion
        # completa y su respuesta, y el usuario lo agranda si quiere.
        self.resizeDocks(
            [self._dock], [190], Qt.Orientation.Vertical
        )

        self.traza.connect(self.terminal.registrar)
        self._session.set_trace(self.traza.emit)

        self._menus()
        self._barra_estado()
        self._aplicar_gui_config()

    # ------------------------------------------------------------------ menus

    def _menus(self) -> None:
        archivo = self.menuBar().addMenu("&Archivo")
        exportar = QAction("&Exportar a Markdown...", self)
        exportar.setShortcut(QKeySequence.StandardKey.Save)
        exportar.triggered.connect(self.result_panel.exportar)
        archivo.addAction(exportar)
        archivo.addSeparator()
        salir = QAction("&Salir", self)
        salir.setShortcut(QKeySequence.StandardKey.Quit)
        salir.triggered.connect(self.close)
        archivo.addAction(salir)

        ver = self.menuBar().addMenu("&Ver")
        ver.addAction(self._dock.toggleViewAction())
        self._dock.toggleViewAction().setText("Panel de &terminal")
        ver.addSeparator()
        for etiqueta, delta in (("&Agrandar letra", 1), ("&Achicar letra", -1)):
            accion = QAction(etiqueta, self)
            accion.setShortcut(
                QKeySequence.StandardKey.ZoomIn
                if delta > 0
                else QKeySequence.StandardKey.ZoomOut
            )
            accion.triggered.connect(lambda _=False, d=delta: self._cambiar_cuerpo(d))
            ver.addAction(accion)

        herramientas = self.menuBar().addMenu("&Herramientas")
        ajustes = QAction("&Ajustes...", self)
        ajustes.triggered.connect(self.abrir_ajustes)
        herramientas.addAction(ajustes)

        ayuda = self.menuBar().addMenu("A&yuda")
        acerca = QAction("&Acerca de leyllana", self)
        acerca.triggered.connect(self._acerca_de)
        ayuda.addAction(acerca)

    # ------------------------------------------------------------ barra de estado

    def _barra_estado(self) -> None:
        """Motor vigente a la izquierda, interruptor del terminal a la derecha.

        El terminal estaba solo en el menu Ver, y ahi es donde no se encuentra. Ya
        que es donde se ve lo que sale del equipo (ADR 0022), tiene que estar a un
        clic de distancia.
        """
        barra = self.statusBar()
        self._etiqueta_motor = QLabel()
        barra.addWidget(self._etiqueta_motor)

        self._boton_terminal = QPushButton("Terminal")
        self._boton_terminal.setCheckable(True)
        self._boton_terminal.setFlat(True)
        self._boton_terminal.setToolTip(
            "Muestra el shell y, en una corrida de nube, el comando exacto que se "
            "ejecuto y cuanto texto salio de su equipo."
        )
        self._boton_terminal.toggled.connect(self._dock.setVisible)
        self._dock.visibilityChanged.connect(self._boton_terminal.setChecked)
        barra.addPermanentWidget(self._boton_terminal)

        self._describir_motor()

    def _describir_motor(self) -> None:
        """Escribe en la barra que motor esta configurado y si el envio sale."""
        engine = self._session.config.engine
        if engine.provider.lower() == "local":
            ruta = engine.default_model.path
            modelo = Path(ruta).name if ruta else "sin modelo configurado"
            texto = f"Local: {modelo}. Nada sale de su equipo."
        else:
            destino = engine.cli.preset or next(iter(engine.cli.command), "CLI")
            texto = (
                f"Nube ({destino}): se le pedira autorizacion en cada explicacion."
            )
        self._etiqueta_motor.setText(texto)

    def _acerca_de(self) -> None:
        caja = QMessageBox(self)
        caja.setWindowTitle("Acerca de leyllana")
        caja.setText(
            "<b>leyllana</b><br>La ley, en lenguaje llano."
        )
        caja.setInformativeText(
            "Explica leyes y boletines chilenos en lenguaje llano.\n\n"
            "Primera herramienta de Germen Digital Socialista. El brote es la "
            "marca de la organizacion; el libro es esta herramienta. Local por "
            "defecto: nada sale de su equipo salvo que usted lo autorice.\n\n"
            "No es asesoria legal ni una interpretacion oficial."
        )
        logo = assets.ruta(assets.LOGO)
        if logo is not None:
            caja.setIconPixmap(QIcon(str(logo)).pixmap(QSize(96, 96)))
        caja.exec()

    # ------------------------------------------------------------- apariencia

    def _aplicar_gui_config(self) -> None:
        gui = self._session.config.gui
        app = QApplication.instance()
        oscuro = theme.sistema_es_oscuro(app) if app is not None else False
        self.result_panel.aplicar_estilo(
            gui.font_size, theme.resolver(gui.theme, oscuro)
        )

    def _cambiar_cuerpo(self, delta: int) -> None:
        gui = self._session.config.gui
        nuevo = max(8, min(32, gui.font_size + delta))
        if nuevo == gui.font_size:
            return
        self._session.update_gui(replace(gui, font_size=nuevo))
        self._aplicar_gui_config()
        try:
            self._session.save()
        except OSError as exc:
            # No vale interrumpir la lectura por esto: se avisa y se sigue con el
            # tamano nuevo aplicado en pantalla.
            self.statusBar().showMessage(f"No se pudo guardar el tamano: {exc}", 8000)

    # ---------------------------------------------------------------- ajustes

    def abrir_ajustes(self) -> None:
        if self._hilo is not None:
            QMessageBox.information(
                self, "Ajustes", "Espere a que termine la explicacion en curso."
            )
            return
        dialogo = SettingsDialog(
            self._session.config, self._session.config_path or "leyllana.toml", self
        )
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        nueva = dialogo.a_config()
        try:
            self._session.update_config(nueva)
            ruta = self._session.save()
        except OSError as exc:
            QMessageBox.warning(self, "No se pudo guardar", f"Error: {exc}")
            return
        self._session.set_trace(self.traza.emit)
        self._aplicar_tema(nueva)
        self._aplicar_gui_config()
        self._describir_motor()
        self.statusBar().showMessage(f"Ajustes guardados en {ruta}.", 8000)

    def _aplicar_tema(self, config: Config) -> None:
        app = QApplication.instance()
        if app is not None:
            theme.aplicar(app, config.gui.theme)

    # --------------------------------------------------------------- corrida

    def explicar(self) -> None:
        if self._hilo is not None:
            return
        try:
            source = self.source_panel.source()
        except ValueError as exc:
            QMessageBox.information(self, "Falta la fuente", str(exc))
            return

        # El gate de consentimiento va antes de tocar nada (ADR 0013): si el
        # usuario dice que no, no se llego a construir ni el primer prompt.
        consent = False
        try:
            if self._session.envia_a_la_nube:
                if not pedir_consentimiento(self, self._session.destino):
                    return
                consent = True
                # Si el documento va a salir, el panel que lo muestra se abre
                # solo: una garantia que hay que ir a buscar al menu no sirve
                # de garantia (ADR 0022).
                self._dock.show()
        except Exception as exc:  # noqa: BLE001 - proveedor mal configurado
            QMessageBox.warning(self, "No se pudo preparar el motor", mensaje(exc))
            return

        self.result_panel.limpiar()
        self.source_panel.comenzar()

        self._worker = ExplainWorker(
            source,
            self.source_panel.nivel_elegido(),
            self._session.config,
            self._session.provider,
            consent,
        )
        self._hilo = QThread(self)
        self._worker.moveToThread(self._hilo)
        self._hilo.started.connect(self._worker.run)
        self._worker.progreso.connect(self.source_panel.avanzar)
        self._worker.terminado.connect(self._al_terminar)
        self._worker.fallo.connect(self._al_fallar)
        self._worker.cancelado.connect(self._al_cancelar)
        self._worker.finalizado.connect(self._cerrar_hilo)
        self._hilo.start()

    def cancelar(self) -> None:
        if self._worker is not None:
            self._worker.cancel.cancel()
            self.source_panel.etiqueta_estado.setText("Cancelando...")

    def _al_terminar(self, explicacion: Explanation, info: SourceInfo) -> None:
        self.result_panel.mostrar(explicacion, info)
        self.source_panel.terminar("Listo.")

    def _al_fallar(self, texto: str) -> None:
        self.source_panel.terminar("No se completo la explicacion.")
        QMessageBox.warning(self, "No se pudo explicar", texto)

    def _al_cancelar(self) -> None:
        self.source_panel.terminar("Cancelado.")

    def _cerrar_hilo(self) -> None:
        if self._hilo is not None:
            self._hilo.quit()
            self._hilo.wait()
            self._hilo.deleteLater()
        if self._worker is not None:
            self._worker.deleteLater()
        self._hilo = None
        self._worker = None

    # ----------------------------------------------------------------- cierre

    def closeEvent(self, event) -> None:  # noqa: N802 - lo nombra Qt
        """Corta la corrida y suelta el modelo antes de cerrar."""
        if self._worker is not None:
            self._worker.cancel.cancel()
        if self._hilo is not None:
            self._hilo.quit()
            self._hilo.wait(5000)
        self.terminal.cerrar()
        self._session.close()
        super().closeEvent(event)


__all__ = ["MainWindow"]
