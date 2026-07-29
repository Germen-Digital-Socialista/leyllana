"""Qué salió realmente del equipo, para poder mostrarlo (ADR 0022).

leyllana promete que nada sale sin permiso. El dialogo de consentimiento
(ADR 0013) pide ese permiso, pero despues no se ve nada: el proveedor de nube
corre su CLI como subproceso invisible (ADR 0018) y al usuario solo le queda
nuestra palabra sobre lo que se envio.

Este modulo es el canal para que deje de ser nuestra palabra. El proveedor emite
eventos con lo que invoco, cuanto texto mando y que le respondieron; quien
escucha decide como mostrarlos. Los eventos no llevan formato ni colores: el
engine no sabe que existe un panel.

Solo se traza el camino de nube. El proveedor local habla con ``127.0.0.1`` y su
trafico no sale de la maquina, asi que no hay nada que revelar.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum


class Kind(StrEnum):
    """Que clase de aviso es."""

    INVOCACION = "invocacion"
    ENVIO = "envio"
    RESPUESTA = "respuesta"
    FIN = "fin"


@dataclass(frozen=True)
class TraceEvent:
    """Un aviso sobre una llamada que sale del equipo.

    ``detalle`` ya viene en espanol y listo para mostrar, pero sin formato: es
    texto, no marcado.
    """

    kind: Kind
    detalle: str


# Quien escucha. Puede correr en cualquier hilo.
TraceFn = Callable[[TraceEvent], None]


def emit(trace: TraceFn | None, kind: Kind, detalle: str) -> None:
    """Manda un aviso si hay quien lo escuche.

    El texto del documento nunca se manda por aqui. Volcar una ley de 99.468
    caracteres en un panel que se desplaza es ruido, no transparencia, y el
    usuario ya tiene el documento abierto al lado.
    """
    if trace is not None:
        trace(TraceEvent(kind, detalle))


__all__ = ["Kind", "TraceEvent", "TraceFn", "emit"]
