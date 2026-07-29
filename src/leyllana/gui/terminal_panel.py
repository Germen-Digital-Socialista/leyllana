"""Panel de terminal empotrado (ADR 0004), sobre ``pywinpty`` en Windows.

Hace dos cosas.

La primera es un shell de verdad al lado de la aplicacion, para manejar a mano el
CLI de un proveedor: autenticarse, mirar cuota, probar un comando. La
autenticacion la resuelve el propio CLI contra la suscripcion del usuario y
leyllana no ve credenciales.

La segunda es mostrar **lo que de verdad salio del equipo** (ADR 0022). Cuando
una corrida usa el proveedor de nube, aqui aparece el comando exacto que se
ejecuto, cuanto texto se mando y que respondio. leyllana promete que nada sale
sin permiso; esto es lo que hace comprobable la promesa en vez de dejarla en
nuestra palabra. El texto del documento no se imprime: su tamano si.

**No es un emulador de terminal completo.** Interpreta lo justo para que una
sesion normal se lea: se descartan las secuencias de escape ANSI en vez de
pintarlas como color o mover el cursor. Un programa de pantalla completa (vim,
htop) se vera mal aqui, y eso es una limitacion asumida, no un error por
descubrir.

Fuera de Windows, o sin ``pywinpty`` instalado, el panel muestra el motivo y no
se cae: ADR 0004 deja el backend de Linux/macOS explicitamente diferido.
"""

from __future__ import annotations

import os
import re
import sys
from html import escape

from PySide6.QtCore import QEvent, QObject, Qt, QThread, Signal
from PySide6.QtGui import QFont, QKeyEvent, QKeySequence, QTextCursor
from PySide6.QtWidgets import QApplication, QPlainTextEdit, QVBoxLayout, QWidget

from ..engine.trace import Kind, TraceEvent
from . import theme

# CSI, OSC y los escapes de un solo caracter. Se borran; no se interpretan.
_ANSI = re.compile(
    r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"  # OSC ... BEL | ST
    r"|\x1b\[[0-9;?]*[ -/]*[@-~]"  # CSI
    r"|\x1b[@-Z\\-_]"  # escapes de un caracter
)
# Retroceso y campana: no aportan nada a una vista de solo texto.
_CONTROL = re.compile(r"[\x07\x08]")

_LECTURA = 4096


def limpiar_ansi(texto: str) -> str:
    """Quita las secuencias de escape para dejar texto legible."""
    limpio = _CONTROL.sub("", _ANSI.sub("", texto))
    return limpio.replace("\r\n", "\n").replace("\r", "\n")


def _shell() -> str:
    """El shell a levantar: el del entorno, o ``cmd.exe``."""
    return os.environ.get("COMSPEC") or "cmd.exe"


class _Lector(QObject):
    """Lee del pty en su propio hilo y emite lo que llega."""

    salida = Signal(str)
    terminado = Signal()

    def __init__(self, pty) -> None:
        super().__init__()
        self._pty = pty
        self._vivo = True

    def run(self) -> None:
        while self._vivo:
            try:
                datos = self._pty.read(_LECTURA)
            except EOFError:
                break
            except OSError:
                break
            if not datos:
                break
            self.salida.emit(datos if isinstance(datos, str) else datos.decode(
                "utf-8", "replace"
            ))
        self.terminado.emit()

    def detener(self) -> None:
        self._vivo = False


class TerminalPanel(QWidget):
    """Vista de texto conectada a un shell real, o el motivo de que no lo este."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pty = None
        self._hilo: QThread | None = None
        self._lector: _Lector | None = None

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        self.vista = QPlainTextEdit()
        self.vista.setReadOnly(True)
        self.vista.setUndoRedoEnabled(False)
        self.vista.setMaximumBlockCount(5000)
        self.vista.setFont(QFont("Consolas", 10))
        self.vista.installEventFilter(self)
        raiz.addWidget(self.vista)

        # El motivo se escribe DENTRO de la vista en vez de reemplazarla por una
        # etiqueta: sin shell el panel sigue sirviendo para lo otro que hace,
        # mostrar lo que sale del equipo (ADR 0022).
        motivo = self._arrancar()
        if motivo is not None:
            self._nota(motivo)

    # --------------------------------------------------------------- arranque

    def _arrancar(self) -> str | None:
        """Levanta el shell. Devuelve el motivo si no se pudo, o ``None``."""
        if sys.platform != "win32":
            return (
                "El panel de terminal usa pywinpty y por ahora solo funciona en "
                "Windows (ADR 0004). El resto de la aplicacion funciona igual."
            )
        try:
            import winpty
        except ImportError:
            return (
                "Falta pywinpty. Instale el extra de interfaz grafica para usar "
                "el panel de terminal:  uv sync --extra gui"
            )
        try:
            self._pty = winpty.PtyProcess.spawn(_shell())
        except Exception as exc:  # noqa: BLE001 - el panel no puede tumbar la app
            return f"No se pudo abrir la terminal: {exc}"

        self._lector = _Lector(self._pty)
        self._hilo = QThread(self)
        self._lector.moveToThread(self._hilo)
        self._hilo.started.connect(self._lector.run)
        self._lector.salida.connect(self._escribir)
        self._hilo.start()
        return None

    # ------------------------------------------------------------------- E/S

    def _escribir(self, texto: str) -> None:
        self.vista.moveCursor(QTextCursor.MoveOperation.End)
        self.vista.insertPlainText(limpiar_ansi(texto))
        self.vista.moveCursor(QTextCursor.MoveOperation.End)

    # ---------------------------------------------- lo que sale (ADR 0022)

    def _color(self, clave: str) -> str:
        app = QApplication.instance()
        oscuro = theme.sistema_es_oscuro(app) if app is not None else False
        return theme.color(theme.OSCURO if oscuro else theme.CLARO, clave)

    def _nota(self, texto: str, clave: str = "dim") -> None:
        """Escribe una linea de la aplicacion, distinguible de la del shell."""
        self.vista.moveCursor(QTextCursor.MoveOperation.End)
        self.vista.appendHtml(
            f'<span style="color:{self._color(clave)}">'
            f"{escape(texto).replace(chr(10), '<br>')}</span>"
        )
        self.vista.moveCursor(QTextCursor.MoveOperation.End)

    def registrar(self, evento: TraceEvent) -> None:
        """Muestra un aviso de lo que salio del equipo (ADR 0022).

        El prefijo ``leyllana>`` marca lo que hizo la aplicacion, para que no se
        confunda con lo que escribio el usuario en el shell.
        """
        if evento.kind is Kind.INVOCACION:
            self._nota(f"\nleyllana> {evento.detalle}", "highlight")
        elif evento.kind is Kind.ENVIO:
            self._nota(f"          [sale del equipo: {evento.detalle}]")
        elif evento.kind is Kind.RESPUESTA:
            self._nota(evento.detalle, "text")
        else:
            self._nota(f"          [{evento.detalle}]")

    def eventFilter(self, obj, event):  # noqa: N802 - lo nombra Qt
        """Manda las teclas al shell en vez de dejarlas en la vista de solo lectura."""
        if obj is self.vista and event.type() == QEvent.Type.KeyPress:
            if self._pty is None:
                return False
            if event.matches(QKeySequence.StandardKey.Copy):
                return False
            self._enviar(event)
            return True
        return super().eventFilter(obj, event)

    def _enviar(self, event: QKeyEvent) -> None:
        tecla = event.key()
        if tecla in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            texto = "\r"
        elif tecla == Qt.Key.Key_Backspace:
            texto = "\x7f"
        elif tecla == Qt.Key.Key_Tab:
            texto = "\t"
        elif tecla == Qt.Key.Key_Escape:
            texto = "\x1b"
        else:
            texto = event.text()
        if not texto:
            return
        try:
            self._pty.write(texto)
        except (OSError, EOFError):
            self._escribir("\n[la terminal se cerro]\n")
            self._pty = None

    # ---------------------------------------------------------------- cierre

    def cerrar(self) -> None:
        """Termina el shell y su hilo lector. Idempotente."""
        if self._lector is not None:
            self._lector.detener()
        if self._pty is not None:
            try:
                self._pty.terminate(force=True)
            except Exception:  # noqa: BLE001 - ya puede estar muerto
                pass
            self._pty = None
        if self._hilo is not None:
            self._hilo.quit()
            self._hilo.wait(2000)
            self._hilo = None


__all__ = ["TerminalPanel", "limpiar_ansi"]
