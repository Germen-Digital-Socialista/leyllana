"""Smoke test real del proveedor local: arranca un ``llama-server`` de verdad.

Se salta salvo que ``LEYLLANA_SMOKE_SERVER`` y ``LEYLLANA_SMOKE_MODEL`` apunten a
un binario ``llama-server`` y a un GGUF existentes. Asi la suite normal no depende
de binarios ni modelos, pero se puede correr una verificacion extremo a extremo
real (input -> prompt -> modelo local -> cuatro secciones parseadas).
"""

import os
from pathlib import Path

import pytest

_SERVER = os.environ.get("LEYLLANA_SMOKE_SERVER")
_MODEL = os.environ.get("LEYLLANA_SMOKE_MODEL")
_READY = bool(
    _SERVER and _MODEL and Path(_SERVER).exists() and Path(_MODEL).exists()
)

pytestmark = pytest.mark.skipif(
    not _READY,
    reason="defina LEYLLANA_SMOKE_SERVER y LEYLLANA_SMOKE_MODEL con rutas validas",
)


def test_local_provider_real_generation():
    from leyllana.config import Config, EngineConfig, ModelConfig
    from leyllana.engine import explain
    from leyllana.types import Explanation, Nivel

    cfg = Config(
        engine=EngineConfig(
            server_path=_SERVER,
            default_model=ModelConfig(path=_MODEL, ctx=4096),
            gpu="cpu",
            max_tokens=700,
        )
    )
    text = (
        "Articulo 1. La presente ley regula el uso de sistemas de inteligencia "
        "artificial por los organos del Estado y establece principios de "
        "transparencia, no discriminacion y supervision humana."
    )
    exp = explain(text, Nivel.PUBLICO, cfg)
    assert isinstance(exp, Explanation)
    assert exp.que_hace.strip()
    assert exp.a_quien_afecta.strip()
    assert exp.articulos_clave.strip()
    assert exp.en_una_frase.strip()
