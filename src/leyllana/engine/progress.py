"""Avance y cancelacion de una explicacion en curso (PRD FR-10).

Una corrida local sobre una norma larga tarda decenas de minutos (medido en la
Fase 1: 50 min para una ley de 55 articulos). Sin nada que informe donde va ni
como detenerla, la GUI solo puede mostrar un reloj de arena. Este modulo define
el vocabulario minimo para las dos cosas:

- ``Progress``: en que etapa esta y, cuando el documento se troceo, que fragmento
  de cuantos va. La GUI lo pinta; la CLI lo ignora.
- ``CancelToken``: una senal que el que llama levanta desde otro hilo y que el
  engine consulta entre llamadas al proveedor.

Puro y sin dependencias de Qt: el engine no sabe que existe una GUI.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum


class Stage(StrEnum):
    """Etapas visibles de una corrida, con los nombres que fija PRD FR-10."""

    CARGANDO = "cargando"
    EXTRAYENDO = "extrayendo texto"
    ANALIZANDO = "analizando"
    VERIFICANDO = "verificando"
    GENERANDO = "generando resultado"


@dataclass(frozen=True)
class Progress:
    """Un aviso de avance.

    ``fragmento`` y ``total`` solo vienen cuando hay un trabajo contable (el map
    de ADR 0017, un fragmento por llamada). En una pasada unica van en ``None``:
    no hay nada que contar y la GUI muestra una barra indeterminada en vez de
    inventar un porcentaje.
    """

    stage: Stage
    fragmento: int | None = None
    total: int | None = None
    detalle: str | None = None

    def texto(self) -> str:
        """Linea en espanol lista para mostrar, sin porcentaje inventado."""
        base = str(self.stage)
        if self.fragmento is not None and self.total:
            base = f"{base} (fragmento {self.fragmento} de {self.total})"
        if self.detalle:
            base = f"{base}: {self.detalle}"
        return base


# El que llama recibe cada aviso. Puede correr en cualquier hilo; en la GUI el
# callback solo emite una senal de Qt y vuelve enseguida.
ProgressFn = Callable[[Progress], None]


class Cancelled(RuntimeError):
    """El usuario detuvo la corrida (PRD FR-10).

    No es un error del sistema: es la respuesta a una accion deliberada. Quien la
    atrapa deja la interfaz lista para otra corrida, sin mostrar un fallo.
    """


class CancelToken:
    """Senal de cancelacion compartida entre el hilo que pide y el que trabaja.

    Envuelve un ``threading.Event`` para no exponer un objeto de la stdlib con
    mas superficie de la que hace falta, y para que el nombre diga que es.
    """

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        """Pide detener la corrida. Idempotente."""
        self._event.set()

    def is_cancelled(self) -> bool:
        """True si ya se pidio detener."""
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        """Levanta ``Cancelled`` si ya se pidio detener; si no, no hace nada."""
        if self._event.is_set():
            raise Cancelled("La explicacion fue cancelada por el usuario.")


def report(progress: ProgressFn | None, stage: Stage, **kwargs) -> None:
    """Envia un aviso si hay quien lo escuche.

    Existe para que el engine no repita el ``if progress is not None`` en cada
    punto de avance.
    """
    if progress is not None:
        progress(Progress(stage, **kwargs))


def check(cancel: CancelToken | None) -> None:
    """Corta la corrida si se pidio cancelar; si no hay token, no hace nada."""
    if cancel is not None:
        cancel.raise_if_cancelled()


__all__ = [
    "Stage",
    "Progress",
    "ProgressFn",
    "Cancelled",
    "CancelToken",
    "report",
    "check",
]
