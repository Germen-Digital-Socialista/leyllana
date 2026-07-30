"""El trabajo pesado, fuera del hilo de la interfaz.

Resolver la fuente y explicarla puede tardar decenas de minutos. Corriendo en el
hilo de Qt, la ventana quedaria congelada todo ese rato: sin repintar, sin barra
de avance y sin boton de Cancelar, que es exactamente lo que FR-10 no acepta.

El ``ExplainWorker`` es un ``QObject`` que se mueve a un ``QThread``. Los avisos
de avance llegan desde ese hilo y se reemiten como senales de Qt, que Qt entrega
en cola al hilo de la interfaz: los widgets solo se tocan desde donde se deben
tocar.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from .. import diagnostics
from ..config import Config
from ..engine import explain
from ..engine.base import Provider
from ..engine.progress import Cancelled, CancelToken, Progress, Stage
from ..input import resolve_with_source
from ..types import Explanation, Nivel, SourceInfo
from .errors import mensaje


class ExplainWorker(QObject):
    """Una corrida completa: fuente -> texto -> explicacion."""

    progreso = Signal(Progress)
    terminado = Signal(Explanation, SourceInfo)
    fallo = Signal(str)
    cancelado = Signal()
    finalizado = Signal()

    def __init__(
        self,
        source: str,
        nivel: Nivel,
        config: Config,
        provider: Provider | None = None,
        consent: bool = False,
    ) -> None:
        super().__init__()
        self._source = source
        self._nivel = nivel
        self._config = config
        self._provider = provider
        self._consent = consent
        self.cancel = CancelToken()

    @Slot()
    def run(self) -> None:
        """Corre la explicacion. Termina siempre emitiendo ``finalizado``."""
        registro = diagnostics.RunRecord(
            fuente=self._source, nivel=str(self._nivel), config=self._config
        )

        def avisar(progreso: Progress) -> None:
            # El registro se alimenta del mismo aviso que pinta la ventana, para que
            # lo anotado sea exactamente lo que el usuario vio y no otra cuenta.
            registro.anotar(progreso)
            self.progreso.emit(progreso)

        try:
            avisar(Progress(Stage.CARGANDO))
            self.cancel.raise_if_cancelled()
            avisar(Progress(Stage.EXTRAYENDO))
            texto, info = resolve_with_source(self._source)
            registro.texto_resuelto(texto)
            explicacion = explain(
                texto,
                self._nivel,
                self._config,
                self._consent,
                progress=avisar,
                cancel=self.cancel,
                provider=self._provider,
            )
        except Cancelled:
            # No es un fallo: es lo que el usuario pidio.
            registro.cerrar("cancelada")
            self.cancelado.emit()
        except BaseException as exc:  # noqa: BLE001 - la ventana no puede morirse
            # Una corrida que fallo es justo la que hay que poder revisar despues.
            registro.cerrar("fallo", error=f"{type(exc).__name__}: {exc}")
            self.fallo.emit(mensaje(exc))
        else:
            registro.cerrar("ok")
            self.terminado.emit(explicacion, info)
        finally:
            self.finalizado.emit()


__all__ = ["ExplainWorker"]
