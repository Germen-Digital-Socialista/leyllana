"""Seleccion del modelo local segun la memoria de la maquina (ADR 0027).

El modelo por defecto (Qwen3-4B) es mas fiel que el fallback pero no cabe en toda
maquina; el fallback cabe donde el 4B no. En vez de correr siempre el 4B (que en
un equipo del piso de 8 GB se queda sin RAM al arrancar, porque llama.cpp
preasigna todo el KV cache), se elige el modelo mas grande cuya huella entra en
una fraccion segura de la memoria viva. Una eleccion explicita en la config gana
siempre; el auto solo rellena cuando no hay ninguna fijada (fill-only).

La huella se calcula, no se adivina: tamano del archivo GGUF mas el KV cache al
ctx configurado, con la misma formula que ``tools/inspect_model.py`` (que importa
el lector de aqui). La memoria viva es la VRAM del dispositivo cuando la GPU esta
activa (ADR 0023) o la RAM total del sistema en el camino CPU.
"""

from __future__ import annotations

import os
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

from ..config import EngineConfig, ModelConfig

# Fraccion segura de la memoria viva que la huella de un modelo puede ocupar para
# ser elegible (ADR 0027). En el piso de 8 GB son ~4,8 GB, cerca de los ~5 GB
# utiles tras el SO que registra ADR 0015.
SAFE_FRACTION = 0.60

# Factor de la huella del KV frente a f16 (2 bytes/elemento, la base de la formula).
# Solo f16 y q8_0 se usan en la practica (ADR 0023); el resto va por aproximacion.
_KV_FACTOR = {
    "f32": 2.0,
    "bf16": 1.0,
    "f16": 1.0,
    "q8_0": 0.5,
    "q5_0": 0.3125,
    "q5_1": 0.3125,
    "q4_0": 0.25,
    "q4_1": 0.25,
    "iq4_nl": 0.25,
}


# --- Lector de metadatos del GGUF (compartido con tools/inspect_model.py) ----

# Tipos de valor del formato GGUF, en su orden numerico.
(_U8, _I8, _U16, _I16, _U32, _I32, _F32, _BOOL, _STRING, _ARRAY, _U64, _I64,
 _F64) = range(13)
_FIXED = {
    _U8: ("<B", 1),
    _I8: ("<b", 1),
    _U16: ("<H", 2),
    _I16: ("<h", 2),
    _U32: ("<I", 4),
    _I32: ("<i", 4),
    _F32: ("<f", 4),
    _BOOL: ("<?", 1),
    _U64: ("<Q", 8),
    _I64: ("<q", 8),
    _F64: ("<d", 8),
}


class _Reader:
    """Lectura secuencial de los tipos primitivos del GGUF."""

    def __init__(self, fh) -> None:
        self.fh = fh

    def raw(self, n: int) -> bytes:
        b = self.fh.read(n)
        if len(b) != n:
            raise EOFError("el archivo termino antes de lo esperado")
        return b

    def u32(self) -> int:
        return struct.unpack("<I", self.raw(4))[0]

    def u64(self) -> int:
        return struct.unpack("<Q", self.raw(8))[0]

    def string(self) -> str:
        return self.raw(self.u64()).decode("utf-8", "replace")

    def value(self, tipo: int):
        if tipo in _FIXED:
            fmt, tam = _FIXED[tipo]
            return struct.unpack(fmt, self.raw(tam))[0]
        if tipo == _STRING:
            return self.string()
        if tipo == _ARRAY:
            inner = self.u32()
            count = self.u64()
            # El vocabulario es un array enorme y no interesa: se salta y se resume.
            if count > 64:
                for _ in range(count):
                    self.value(inner)
                return f"<array de {count}>"
            return [self.value(inner) for _ in range(count)]
        raise ValueError(f"tipo de valor desconocido en el GGUF: {tipo}")


def read_gguf_metadata(path: str | Path) -> dict:
    """Devuelve el diccionario de metadatos del GGUF, sin leer los tensores.

    Solo lee el bloque de metadatos del principio del archivo, asi que no toca RAM
    ni VRAM. Lanza ``ValueError`` si el archivo no empieza con la marca ``GGUF``.
    """
    with Path(path).open("rb") as fh:
        r = _Reader(fh)
        if r.raw(4) != b"GGUF":
            raise ValueError(f"no es un archivo GGUF: {path}")
        r.u32()  # version
        r.u64()  # cantidad de tensores
        count = r.u64()
        return {r.string(): r.value(r.u32()) for _ in range(count)}


def _scalar(value):
    """Algunos modelos guardan estos campos como lista de una posicion."""
    return value[0] if isinstance(value, list) and value else value


def kv_bytes_per_token(meta: dict) -> int | None:
    """Bytes de KV cache por token en f16, o ``None`` si faltan metadatos.

    Misma formula que ``tools/inspect_model.py``: K y V en cada capa, 2 bytes por
    elemento. Con ``-ctk/-ctv q8_0`` (ADR 0023) se reduce a la mitad; ese factor lo
    aplica ``model_footprint_bytes``, no esta funcion.
    """
    arch = meta.get("general.architecture", "")
    block = _scalar(meta.get(f"{arch}.block_count"))
    heads_kv = _scalar(meta.get(f"{arch}.attention.head_count_kv"))
    key_len = _scalar(meta.get(f"{arch}.attention.key_length"))
    val_len = _scalar(meta.get(f"{arch}.attention.value_length"))
    if None in (block, heads_kv, key_len, val_len):
        return None
    return block * heads_kv * (key_len + val_len) * 2


# --- Huella del modelo y memoria de la maquina ------------------------------

def model_footprint_bytes(
    model_path: str | Path, ctx: int, kv_cache_type: str
) -> int | None:
    """Huella en RAM/VRAM: archivo GGUF mas el KV cache preasignado al ``ctx``.

    Devuelve ``None`` cuando no se puede determinar (archivo ausente o metadatos de
    atencion ilegibles): un modelo cuya huella no se conoce no se puede confirmar
    que cabe, asi que queda fuera de los candidatos por ajuste (ADR 0027).
    """
    try:
        size = Path(model_path).stat().st_size
    except OSError:
        return None
    try:
        per_token = kv_bytes_per_token(read_gguf_metadata(model_path))
    except (OSError, ValueError, EOFError):
        per_token = None
    if per_token is None:
        return None
    factor = _KV_FACTOR.get(kv_cache_type, 1.0)
    return size + int(per_token * ctx * factor)


def total_ram_bytes() -> int | None:
    """RAM fisica total del sistema, o ``None`` si no se puede medir.

    Sin dependencias: ``GlobalMemoryStatusEx`` por ctypes en Windows, ``sysconf``
    en POSIX. Una medicion fallida (``None``) lleva al piso: correr el modelo mas
    chico con aviso, en vez de fiarse de un modelo que no se pudo justificar.
    """
    try:
        if sys.platform == "win32":
            import ctypes

            class _MemStatus(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = _MemStatus()
            stat.dwLength = ctypes.sizeof(_MemStatus)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return int(stat.ullTotalPhys)
            return None
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return int(pages) * int(page_size)
    except (OSError, ValueError, AttributeError):
        return None


def live_memory_bytes(device_total_mib: int | None) -> int | None:
    """La memoria contra la que medir: VRAM del dispositivo si la GPU esta activa
    (ADR 0023), o la RAM total del sistema en el camino CPU (ADR 0027)."""
    if device_total_mib is not None:
        return device_total_mib * 1024 * 1024
    return total_ram_bytes()


# --- Decision de seleccion --------------------------------------------------

@dataclass(frozen=True)
class Candidate:
    """Un slot de modelo configurado, con su huella medida (o ``None``)."""

    slot: str
    model: ModelConfig
    footprint: int | None
    file_size: int | None


@dataclass(frozen=True)
class ModelChoice:
    """Que modelo correr, de que slot salio, por que, y si va sobre presupuesto."""

    model: ModelConfig
    slot: str
    report: str
    over_budget: bool


def _size_key(c: Candidate) -> float:
    if c.footprint is not None:
        return c.footprint
    if c.file_size is not None:
        return c.file_size
    return float("inf")


def choose_fitting(
    candidates: list[Candidate], budget: int | None
) -> tuple[Candidate | None, bool]:
    """Elige el candidato mas grande cuya huella entra en ``budget``.

    Si ninguno entra (o el presupuesto es desconocido, o ninguna huella se pudo
    medir), cae al mas chico configurado y marca ``over_budget`` (ADR 0027: nunca se
    niega a correr; corre el mas chico con aviso). Devuelve ``(None, True)`` si no
    hay candidatos.
    """
    if not candidates:
        return None, True
    known = [c for c in candidates if c.footprint is not None]
    if budget is not None and known:
        fits = [c for c in known if c.footprint <= budget]
        if fits:
            return max(fits, key=lambda c: c.footprint), False
    return min(candidates, key=_size_key), True


def _gib(n: int | None) -> str:
    return "?" if n is None else f"{n / 1024**3:.2f}"


def select_model(engine: EngineConfig, live_memory: int | None) -> ModelChoice:
    """Elige el modelo local a correr (ADR 0027).

    Una eleccion explicita (``model_selection`` = ``default`` o ``fallback``) gana
    sin medir nada. En ``auto``, se mide la huella de cada slot configurado y se
    toma el mas grande que entra en ``SAFE_FRACTION`` de ``live_memory``.
    """
    slots = {"default": engine.default_model, "fallback": engine.fallback_model}
    sel = (engine.model_selection or "auto").lower()
    if sel in slots:
        return ModelChoice(slots[sel], sel, f"Modelo fijado por config: {sel}.", False)

    candidates: list[Candidate] = []
    for name in ("default", "fallback"):
        model = slots[name]
        if not model.path:
            continue
        footprint = model_footprint_bytes(model.path, model.ctx, engine.kv_cache_type)
        try:
            file_size = Path(model.path).stat().st_size
        except OSError:
            file_size = None
        candidates.append(Candidate(name, model, footprint, file_size))

    if not candidates:
        # Sin ninguna ruta configurada; el proveedor lanza el error de siempre.
        return ModelChoice(engine.default_model, "default", "Sin modelo configurado.", False)

    budget = int(live_memory * SAFE_FRACTION) if live_memory else None
    chosen, over = choose_fitting(candidates, budget)
    assert chosen is not None  # candidates no vacio

    if not over:
        report = (
            f"Modelo (auto): '{chosen.slot}' ({_gib(chosen.footprint)} GiB) en el "
            f"{int(SAFE_FRACTION * 100)}% de {_gib(live_memory)} GiB."
        )
    elif budget is None:
        report = (
            f"ADVERTENCIA: no se pudo medir la memoria; se corre el modelo mas chico "
            f"('{chosen.slot}')."
        )
    else:
        report = (
            f"ADVERTENCIA: ningun modelo entra en el {int(SAFE_FRACTION * 100)}% de "
            f"{_gib(live_memory)} GiB; se corre el mas chico ('{chosen.slot}')."
        )
    return ModelChoice(chosen.model, chosen.slot, report, over)


__all__ = [
    "SAFE_FRACTION",
    "Candidate",
    "ModelChoice",
    "choose_fitting",
    "kv_bytes_per_token",
    "live_memory_bytes",
    "model_footprint_bytes",
    "read_gguf_metadata",
    "select_model",
    "total_ram_bytes",
]
