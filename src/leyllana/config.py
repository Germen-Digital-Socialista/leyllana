"""Configuracion de leyllana, dirigida por archivo (ADR 0003).

La seleccion de proveedor y de modelo es config-driven, no hardcodeada: un modelo
por defecto mas un fallback de baja RAM, siguiendo el patron del bloque ``models``
de MuniGPT. Se lee de ``leyllana.toml`` con ``tomllib`` (stdlib, Python >=3.11);
si no existe, se usan los defaults de abajo. Ademas del modelo, la config lleva la
ejecucion del ``llama-server`` (binario, GPU) y los parametros de generacion
(ADR 0012, 0016).
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path

# Nombre por defecto del archivo de config, buscado en el cwd.
CONFIG_FILENAME = "leyllana.toml"


@dataclass(frozen=True)
class ModelConfig:
    """Un modelo local llama.cpp: ruta al .gguf y ventana de contexto."""

    path: str | None = None
    ctx: int = 4096


@dataclass(frozen=True)
class EngineConfig:
    """Seleccion de proveedor, modelos y ejecucion del llama-server (ADR 0016).

    ``server_path`` apunta al binario ``llama-server`` (externo, no es dependencia
    pip). ``gpu`` sigue ADR 0012: ``auto`` intenta GPU y cae a CPU, ``cpu`` fuerza
    CPU, ``gpu`` fuerza la descarga a GPU. La generacion es config-driven y
    conservadora: temperatura baja para no inventar (ADR 0008).
    """

    provider: str = "local"
    default_model: ModelConfig = field(default_factory=ModelConfig)
    fallback_model: ModelConfig = field(default_factory=lambda: ModelConfig(ctx=2048))
    server_path: str | None = None
    gpu: str = "auto"
    temperature: float = 0.2
    max_tokens: int = 1024
    threads: int = 0


@dataclass(frozen=True)
class Config:
    """Config raiz de la app."""

    engine: EngineConfig = field(default_factory=EngineConfig)


def _model_from_dict(data: dict) -> ModelConfig:
    return ModelConfig(path=data.get("path"), ctx=int(data.get("ctx", 4096)))


def load(path: str | Path | None = None) -> Config:
    """Carga la config desde TOML, o devuelve los defaults si no hay archivo.

    ``path`` explicito, o ``./leyllana.toml`` si existe, o defaults.
    """
    candidate = Path(path) if path is not None else Path(CONFIG_FILENAME)
    if not candidate.is_file():
        return Config()

    with candidate.open("rb") as fh:
        data = tomllib.load(fh)

    engine_data = data.get("engine", {})
    models_data = engine_data.get("models", {})
    engine = EngineConfig(
        provider=engine_data.get("provider", "local"),
        default_model=_model_from_dict(models_data.get("default", {})),
        fallback_model=_model_from_dict(models_data.get("fallback", {"ctx": 2048})),
        server_path=engine_data.get("server_path"),
        gpu=engine_data.get("gpu", "auto"),
        temperature=float(engine_data.get("temperature", 0.2)),
        max_tokens=int(engine_data.get("max_tokens", 1024)),
        threads=int(engine_data.get("threads", 0)),
    )
    return replace(Config(), engine=engine)
