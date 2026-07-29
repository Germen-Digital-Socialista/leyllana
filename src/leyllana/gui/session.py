"""Estado que vive lo que dura la ventana: config y proveedor caliente.

Cargar un GGUF en CPU tarda minutos. La CLI construye un proveedor por corrida y
lo tira, que para un proceso que termina esta bien; en la GUI eso significaria
pagar la carga del modelo en cada boton Explicar. Aqui el proveedor se construye
una vez, se mantiene vivo entre corridas y se suelta cuando cambia la config o se
cierra la ventana. Esto es lo que el ROADMAP dejaba pendiente de la Fase 1 como
"un proveedor persistente para la GUI de la Fase 3".

Sin Qt a proposito: es estado, no interfaz, y asi se puede probar sin ventana.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from ..config import Config, GuiConfig, save
from ..engine.base import Provider
from ..engine.registry import get_provider


class Session:
    """Config vigente y proveedor asociado, compartidos por toda la ventana."""

    def __init__(self, config: Config, config_path: str | Path | None = None) -> None:
        self._config = config
        self._config_path = config_path
        self._provider: Provider | None = None

    @property
    def config(self) -> Config:
        return self._config

    @property
    def config_path(self) -> str | Path | None:
        """Archivo del que salio la config, para poder nombrarlo en Ajustes."""
        return self._config_path

    @property
    def provider(self) -> Provider:
        """Proveedor de la config actual, construido una sola vez.

        Construirlo es barato: el ``llama-server`` no arranca hasta la primera
        generacion. Lo caro es la carga del modelo, y eso es justo lo que se
        conserva de una corrida a la siguiente.
        """
        if self._provider is None:
            self._provider = get_provider(self._config)
        return self._provider

    @property
    def envia_a_la_nube(self) -> bool:
        """True si el proveedor configurado saca el documento del equipo (ADR 0013)."""
        return bool(getattr(self.provider, "sends_to_cloud", False))

    @property
    def destino(self) -> str:
        """A donde iria el documento, para nombrarlo en el aviso de consentimiento."""
        return str(getattr(self.provider, "destino", "un proveedor de nube"))

    def update_config(self, config: Config) -> None:
        """Cambia la config y descarta el proveedor viejo.

        Se suelta siempre, aunque el bloque ``engine`` parezca igual: comparar
        campo a campo para ahorrarse una recarga es la clase de atajo que deja la
        ventana usando un modelo que el usuario cree haber cambiado.
        """
        self.close()
        self._config = config

    def update_gui(self, gui: GuiConfig) -> None:
        """Cambia solo la apariencia, sin soltar el proveedor.

        Separado de ``update_config`` a proposito: agrandar la letra no tiene por
        que costar una recarga del modelo de varios minutos.
        """
        self._config = replace(self._config, gui=gui)

    def save(self) -> Path:
        """Guarda la config vigente en su archivo (ADR 0021)."""
        return save(self._config, self._config_path)

    def close(self) -> None:
        """Suelta el proveedor y con el la RAM del modelo, si lo soporta."""
        cerrar = getattr(self._provider, "close", None)
        if cerrar is not None:
            cerrar()
        self._provider = None


__all__ = ["Session"]
