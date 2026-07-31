"""Configuracion de leyllana, dirigida por archivo (ADR 0003).

La seleccion de proveedor y de modelo es config-driven, no hardcodeada: un modelo
por defecto mas un fallback de baja RAM, siguiendo el patron del bloque ``models``
de MuniGPT. Se lee de ``leyllana.toml`` con ``tomllib`` (stdlib, Python >=3.11);
si no existe, se usan los defaults de abajo. Ademas del modelo, la config lleva la
ejecucion del ``llama-server`` (binario, GPU) y los parametros de generacion
(ADR 0012, 0016).

Desde la GUI (ADR 0021) este archivo tambien se **escribe**: lo que se ajusta en
la ventana de Ajustes es lo mismo que lee la CLI, para que no haya dos verdades
sobre que proveedor esta configurado. ``tomllib`` solo sabe leer, asi que la
escritura es un emisor propio, acotado a los campos que estas dataclasses
declaran.
"""

from __future__ import annotations

import os
import tempfile
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
class CliConfig:
    """Un agente CLI de suscripcion manejado como subproceso (ADR 0018).

    ``preset`` nombra un CLI ya verificado; ``command`` da el argv completo para
    cualquier otro y gana si vienen los dos. ``ctx_tokens`` es el presupuesto de
    contexto del modelo detras del CLI, para que el map-reduce (ADR 0017) no
    trocee un documento que entra entero.
    """

    preset: str | None = None
    command: tuple[str, ...] = ()
    model: str | None = None
    timeout: float = 600.0
    ctx_tokens: int = 100_000


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
    reranker_model: ModelConfig = field(default_factory=lambda: ModelConfig(ctx=2048))
    cli: CliConfig = field(default_factory=CliConfig)
    server_path: str | None = None
    gpu: str = "auto"
    kv_cache_type: str = "f16"
    model_selection: str = "auto"
    temperature: float = 0.2
    max_tokens: int = 1024
    threads: int = 0


@dataclass(frozen=True)
class GuiConfig:
    """Preferencias visuales de la ventana (PRD, accesibilidad visual).

    ``theme`` vale ``sistema`` (sigue al de Windows), ``claro`` u ``oscuro``.
    ``font_size`` es el cuerpo del panel de resultado en puntos: un texto legal se
    lee de corrido y por largo rato, asi que poder agrandarlo no es un adorno.
    """

    theme: str = "sistema"
    font_size: int = 14


@dataclass(frozen=True)
class Config:
    """Config raiz de la app."""

    engine: EngineConfig = field(default_factory=EngineConfig)
    gui: GuiConfig = field(default_factory=GuiConfig)


def _model_from_dict(data: dict) -> ModelConfig:
    return ModelConfig(path=data.get("path"), ctx=int(data.get("ctx", 4096)))


def _cli_from_dict(data: dict) -> CliConfig:
    return CliConfig(
        preset=data.get("preset"),
        command=tuple(data.get("command", ())),
        model=data.get("model"),
        timeout=float(data.get("timeout", 600.0)),
        ctx_tokens=int(data.get("ctx_tokens", 100_000)),
    )


def _gui_from_dict(data: dict) -> GuiConfig:
    return GuiConfig(
        theme=data.get("theme", "sistema"),
        font_size=int(data.get("font_size", 14)),
    )


def resolve_path(path: str | Path | None = None) -> Path:
    """Ruta del archivo de config: la explicita, o ``./leyllana.toml``.

    Existe para que la GUI pueda decirle al usuario que archivo esta editando y
    escribir en ese mismo, en vez de adivinarlo por su cuenta.
    """
    return Path(path) if path is not None else Path(CONFIG_FILENAME)


def load(path: str | Path | None = None) -> Config:
    """Carga la config desde TOML, o devuelve los defaults si no hay archivo.

    ``path`` explicito, o ``./leyllana.toml`` si existe, o defaults.
    """
    candidate = resolve_path(path)
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
        reranker_model=_model_from_dict(models_data.get("reranker", {"ctx": 2048})),
        cli=_cli_from_dict(engine_data.get("cli", {})),
        server_path=engine_data.get("server_path"),
        gpu=engine_data.get("gpu", "auto"),
        kv_cache_type=engine_data.get("kv_cache_type", "f16"),
        model_selection=engine_data.get("model_selection", "auto"),
        temperature=float(engine_data.get("temperature", 0.2)),
        max_tokens=int(engine_data.get("max_tokens", 1024)),
        threads=int(engine_data.get("threads", 0)),
    )
    return replace(Config(), engine=engine, gui=_gui_from_dict(data.get("gui", {})))


def _toml_value(value) -> str:
    """Serializa un escalar o una lista de cadenas a TOML."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, (tuple, list)):
        return "[" + ", ".join(_toml_value(str(v)) for v in value) + "]"
    escapado = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escapado}"'


def _table(nombre: str, pares: list[tuple[str, object]]) -> list[str]:
    """Una tabla TOML. Los valores en ``None`` se omiten, no se escriben vacios."""
    filas = [f"{k} = {_toml_value(v)}" for k, v in pares if v is not None]
    if not filas:
        return []
    return [f"[{nombre}]", *filas, ""]


def dumps(config: Config) -> str:
    """Devuelve el TOML de ``config``, solo con los campos que la app declara."""
    e = config.engine
    lineas: list[str] = [
        "# Escrito por leyllana. Los comentarios que agregue a mano se pierden al",
        "# guardar desde la aplicacion; la referencia comentada es",
        "# leyllana.example.toml.",
        "",
    ]
    lineas += _table(
        "engine",
        [
            ("provider", e.provider),
            ("server_path", e.server_path),
            ("gpu", e.gpu),
            ("kv_cache_type", e.kv_cache_type),
            ("model_selection", e.model_selection),
            ("temperature", e.temperature),
            ("max_tokens", e.max_tokens),
            ("threads", e.threads),
        ],
    )
    lineas += _table(
        "engine.models.default",
        [("path", e.default_model.path), ("ctx", e.default_model.ctx)],
    )
    lineas += _table(
        "engine.models.fallback",
        [("path", e.fallback_model.path), ("ctx", e.fallback_model.ctx)],
    )
    lineas += _table(
        "engine.models.reranker",
        [("path", e.reranker_model.path), ("ctx", e.reranker_model.ctx)],
    )
    lineas += _table(
        "engine.cli",
        [
            ("preset", e.cli.preset),
            ("command", list(e.cli.command) or None),
            ("model", e.cli.model),
            ("timeout", e.cli.timeout),
            ("ctx_tokens", e.cli.ctx_tokens),
        ],
    )
    lineas += _table(
        "gui", [("theme", config.gui.theme), ("font_size", config.gui.font_size)]
    )
    return "\n".join(lineas)


def save(config: Config, path: str | Path | None = None) -> Path:
    """Escribe ``config`` en el archivo TOML y devuelve la ruta escrita.

    La escritura es atomica (archivo temporal en la misma carpeta y luego
    ``os.replace``): si algo falla a medio guardar, el usuario se queda con su
    config anterior intacta y no con un archivo truncado que ya no carga.
    """
    destino = resolve_path(path)
    destino.parent.mkdir(parents=True, exist_ok=True)
    fd, temporal = tempfile.mkstemp(
        dir=str(destino.parent), prefix=destino.name, suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(dumps(config))
        os.replace(temporal, destino)
    except BaseException:
        Path(temporal).unlink(missing_ok=True)
        raise
    return destino
