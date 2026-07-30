"""Registro de lo que hizo cada corrida, para poder explicarla despues.

Una corrida lenta o rara no se puede diagnosticar cuando ya termino. Hasta ahora
la aplicacion no guardaba nada: el log del ``llama-server`` iba a ``DEVNULL``
(``engine/server.py``), asi que ni los dispositivos que vio el binario, ni el
recuento real de tokens del prompt, ni un rechazo por contexto quedaban en ninguna
parte. Esto guarda esos hechos.

Dos piezas, con vidas distintas:

- **el log del ``llama-server``**, que es por sesion: el servidor se levanta una vez
  y sirve muchas corridas (ADR 0019), asi que su log tambien es uno por sesion;
- **el registro de la corrida**, uno por explicacion, con los tiempos por etapa y
  por fragmento y la configuracion que los produjo. Un numero sin su configuracion
  al lado no sirve para nada: es el error que hizo irreproducibles las primeras
  mediciones de este proyecto.

**Nunca se guarda el texto del documento**, solo su tamano y su recuento estimado de
tokens. La postura local-first (ADR 0005) no se dobla por instrumentar. Si se guarda
la fuente indicada (ruta o URL), que es dato del propio equipo y hace falta para
saber sobre que se corrio.

Todo es best-effort: si no se puede escribir el registro, la corrida sigue. Un
diagnostico que rompe la funcion que observa no sirve.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config
from .engine.progress import Progress

# Carpeta de los registros, fijada al arrancar. En ``None`` el diagnostico esta
# apagado y todo esto no hace nada, que es el comportamiento de siempre.
_carpeta: Path | None = None

# Log del ``llama-server`` de esta sesion. ``engine/server.py`` lo consulta al
# levantar el proceso; en ``None`` manda la salida a DEVNULL como hasta ahora.
_log_servidor: Path | None = None


def activar(carpeta: str | Path) -> Path:
    """Enciende el diagnostico y devuelve la carpeta donde va a escribir."""
    global _carpeta, _log_servidor
    destino = Path(carpeta)
    destino.mkdir(parents=True, exist_ok=True)
    _carpeta = destino
    _log_servidor = destino / "llama-server.log"
    return destino


def desactivar() -> None:
    """Apaga el diagnostico. Existe sobre todo para que los tests no dejen rastro."""
    global _carpeta, _log_servidor
    _carpeta = None
    _log_servidor = None


def activo() -> bool:
    return _carpeta is not None


def carpeta() -> Path | None:
    return _carpeta


def log_servidor() -> Path | None:
    """Archivo donde volcar la salida del ``llama-server``, o ``None`` si no hay."""
    return _log_servidor


@dataclass
class RunRecord:
    """Los hechos de una corrida. Se escribe al cerrarla, pase lo que pase."""

    fuente: str
    nivel: str
    config: Config
    inicio: float = field(default_factory=time.monotonic)
    eventos: list[dict] = field(default_factory=list)
    caracteres: int | None = None
    resultado: str = "en curso"

    def texto_resuelto(self, texto: str) -> None:
        """Anota el tamano del documento extraido. El texto no se guarda."""
        self.caracteres = len(texto)

    def anotar(self, progreso: Progress) -> None:
        """Anota un aviso de avance con su marca de tiempo."""
        self.eventos.append(
            {
                "t": round(time.monotonic() - self.inicio, 2),
                "stage": str(progreso.stage),
                "fragmento": progreso.fragmento,
                "total": progreso.total,
                "detalle": progreso.detalle,
            }
        )

    def cerrar(self, resultado: str, error: str | None = None) -> Path | None:
        """Escribe el registro y devuelve su ruta, o ``None`` si no habia carpeta."""
        if _carpeta is None:
            return None
        self.resultado = resultado
        total = time.monotonic() - self.inicio
        avisos = [e for e in self.eventos if e["fragmento"] is not None]
        engine = self.config.engine
        # ``estimate_tokens`` se importa aqui y no arriba para no arrastrar el
        # engine entero cuando el diagnostico esta apagado.
        from .engine.chunking import estimate_tokens

        registro = {
            "resultado": resultado,
            "error": error,
            "fuente": self.fuente,
            "nivel": self.nivel,
            "caracteres": self.caracteres,
            "tokens_estimados": (
                estimate_tokens("x" * self.caracteres)
                if self.caracteres is not None
                else None
            ),
            "total_s": round(total, 2),
            "llamadas_map": len(avisos),
            "fragmentos_primer_nivel": avisos[0]["total"] if avisos else None,
            "provider": engine.provider,
            "modelo": engine.default_model.path,
            "ctx": engine.default_model.ctx,
            "binario": engine.server_path,
            "gpu": engine.gpu,
            "max_tokens": engine.max_tokens,
            "threads": engine.threads,
            "eventos": self.eventos,
            "log_servidor": str(_log_servidor) if _log_servidor else None,
        }
        # El nombre lleva la hora para que dos corridas no se pisen. Se usa la hora
        # de pared solo para nombrar; los tiempos medidos son monotonicos.
        marca = time.strftime("%Y%m%d-%H%M%S")
        destino = _carpeta / f"corrida-{marca}.json"
        try:
            destino.write_text(
                json.dumps(registro, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except OSError:
            # Best-effort: no se pierde una explicacion por no poder escribir su log.
            return None
        return destino


__all__ = [
    "RunRecord",
    "activar",
    "desactivar",
    "activo",
    "carpeta",
    "log_servidor",
]
