"""Tests de la seleccion de modelo por memoria (ADR 0027).

El nucleo de la decision (``choose_fitting``, ``kv_bytes_per_token``) es puro y se
prueba sin modelo ni red. ``model_footprint_bytes`` y ``select_model`` leen el
tamano del archivo real, asi que usan ficheros temporales y un
``read_gguf_metadata`` monkeypatcheado (parsear un GGUF de verdad no hace falta
para probar la aritmetica).
"""

import pytest

from leyllana.config import EngineConfig, ModelConfig
from leyllana.engine import model_fit as mf


# --- KV cache por token, desde los metadatos del GGUF -----------------------

def _meta(block=28, heads_kv=8, key_len=128, val_len=128, arch="qwen3"):
    return {
        "general.architecture": arch,
        f"{arch}.block_count": block,
        f"{arch}.attention.head_count_kv": heads_kv,
        f"{arch}.attention.key_length": key_len,
        f"{arch}.attention.value_length": val_len,
    }


def test_kv_bytes_per_token_matches_formula():
    # 28 capas * 8 cabezas_kv * (128 + 128) * 2 bytes (f16) = 114688 bytes/token.
    assert mf.kv_bytes_per_token(_meta()) == 28 * 8 * (128 + 128) * 2


def test_kv_bytes_per_token_handles_scalar_in_list():
    # Algunos modelos guardan estos campos como lista de una posicion.
    meta = _meta()
    meta["qwen3.block_count"] = [28]
    assert mf.kv_bytes_per_token(meta) == 28 * 8 * (128 + 128) * 2


def test_kv_bytes_per_token_missing_field_returns_none():
    meta = _meta()
    del meta["qwen3.attention.head_count_kv"]
    assert mf.kv_bytes_per_token(meta) is None


# --- Huella del modelo: archivo + KV al ctx configurado ---------------------

def test_model_footprint_file_plus_kv_f16(tmp_path, monkeypatch):
    model = tmp_path / "m.gguf"
    model.write_bytes(b"x" * 1000)
    monkeypatch.setattr(mf, "read_gguf_metadata", lambda p: _meta())
    per_tok = 28 * 8 * (128 + 128) * 2
    fp = mf.model_footprint_bytes(str(model), ctx=4096, kv_cache_type="f16")
    assert fp == 1000 + per_tok * 4096


def test_model_footprint_q8_0_halves_kv(tmp_path, monkeypatch):
    model = tmp_path / "m.gguf"
    model.write_bytes(b"x" * 1000)
    monkeypatch.setattr(mf, "read_gguf_metadata", lambda p: _meta())
    per_tok = 28 * 8 * (128 + 128) * 2
    fp = mf.model_footprint_bytes(str(model), ctx=4096, kv_cache_type="q8_0")
    assert fp == 1000 + int(per_tok * 4096 * 0.5)


def test_model_footprint_none_when_metadata_unreadable(tmp_path, monkeypatch):
    model = tmp_path / "m.gguf"
    model.write_bytes(b"x" * 1000)

    def boom(p):
        raise ValueError("no es GGUF")

    monkeypatch.setattr(mf, "read_gguf_metadata", boom)
    assert mf.model_footprint_bytes(str(model), ctx=4096, kv_cache_type="f16") is None


def test_model_footprint_none_when_file_missing(monkeypatch):
    monkeypatch.setattr(mf, "read_gguf_metadata", lambda p: _meta())
    assert mf.model_footprint_bytes("no-existe.gguf", ctx=4096, kv_cache_type="f16") is None


# --- choose_fitting: el mas grande que cabe, o el mas chico con aviso -------

def _cand(slot, footprint, file_size=None):
    return mf.Candidate(slot, ModelConfig(path=f"{slot}.gguf"), footprint, file_size)


def test_choose_fitting_picks_largest_that_fits():
    cands = [_cand("default", 3_000), _cand("fallback", 1_000)]
    chosen, over = mf.choose_fitting(cands, budget=2_500)
    assert chosen.slot == "fallback"  # 3000 no cabe, 1000 si
    assert over is False


def test_choose_fitting_picks_the_bigger_when_both_fit():
    cands = [_cand("default", 3_000), _cand("fallback", 1_000)]
    chosen, over = mf.choose_fitting(cands, budget=4_000)
    assert chosen.slot == "default"
    assert over is False


def test_choose_fitting_floor_when_nothing_fits():
    cands = [_cand("default", 3_000), _cand("fallback", 1_000)]
    chosen, over = mf.choose_fitting(cands, budget=500)
    assert chosen.slot == "fallback"  # el mas chico
    assert over is True


def test_choose_fitting_floor_when_budget_unknown():
    cands = [_cand("default", 3_000), _cand("fallback", 1_000)]
    chosen, over = mf.choose_fitting(cands, budget=None)
    assert chosen.slot == "fallback"
    assert over is True


def test_choose_fitting_unknown_footprint_excluded_from_fit_but_usable_as_floor():
    # default con huella desconocida no se puede confirmar que cabe: no se elige por
    # ajuste, pero sirve de piso si es lo unico configurado.
    cands = [_cand("default", None, file_size=3_000), _cand("fallback", 1_000, 1_000)]
    chosen, over = mf.choose_fitting(cands, budget=10_000)
    assert chosen.slot == "fallback"
    assert over is False


def test_choose_fitting_empty_returns_none():
    chosen, over = mf.choose_fitting([], budget=1000)
    assert chosen is None
    assert over is True


# --- select_model: fijado gana; auto rellena --------------------------------

def _engine(model_selection="auto", default_path="d.gguf", fallback_path="f.gguf"):
    return EngineConfig(
        model_selection=model_selection,
        default_model=ModelConfig(path=default_path, ctx=4096),
        fallback_model=ModelConfig(path=fallback_path, ctx=2048),
    )


def test_select_model_pin_default_wins_without_measuring(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("un modelo fijado no mide memoria")

    monkeypatch.setattr(mf, "model_footprint_bytes", boom)
    choice = mf.select_model(_engine(model_selection="default"), live_memory=None)
    assert choice.slot == "default"
    assert choice.over_budget is False


def test_select_model_pin_fallback_wins(monkeypatch):
    monkeypatch.setattr(mf, "model_footprint_bytes", lambda *a, **k: 1)
    choice = mf.select_model(_engine(model_selection="fallback"), live_memory=10**12)
    assert choice.slot == "fallback"


def test_select_model_auto_picks_largest_that_fits(monkeypatch, tmp_path):
    d = tmp_path / "d.gguf"
    d.write_bytes(b"x")
    f = tmp_path / "f.gguf"
    f.write_bytes(b"x")
    fps = {str(d): 3 * 1024**3, str(f): 1 * 1024**3}
    monkeypatch.setattr(mf, "model_footprint_bytes", lambda path, ctx, kv: fps[str(path)])
    eng = _engine(default_path=str(d), fallback_path=str(f))
    # 8 GiB * 0.60 = 4.8 GiB: el de 3 GiB cabe, se prefiere.
    choice = mf.select_model(eng, live_memory=8 * 1024**3)
    assert choice.slot == "default"
    assert choice.over_budget is False


def test_select_model_auto_falls_back_on_tight_memory(monkeypatch, tmp_path):
    d = tmp_path / "d.gguf"
    d.write_bytes(b"x")
    f = tmp_path / "f.gguf"
    f.write_bytes(b"x")
    fps = {str(d): 3 * 1024**3, str(f): 1 * 1024**3}
    monkeypatch.setattr(mf, "model_footprint_bytes", lambda path, ctx, kv: fps[str(path)])
    eng = _engine(default_path=str(d), fallback_path=str(f))
    # 4 GiB * 0.60 = 2.4 GiB: el de 3 GiB no cabe, el de 1 GiB si.
    choice = mf.select_model(eng, live_memory=4 * 1024**3)
    assert choice.slot == "fallback"
    assert choice.over_budget is False


def test_select_model_auto_warns_when_nothing_fits(monkeypatch, tmp_path):
    d = tmp_path / "d.gguf"
    d.write_bytes(b"x")
    monkeypatch.setattr(mf, "model_footprint_bytes", lambda path, ctx, kv: 9 * 1024**3)
    eng = _engine(default_path=str(d), fallback_path=None)
    choice = mf.select_model(eng, live_memory=4 * 1024**3)
    assert choice.slot == "default"
    assert choice.over_budget is True
    assert "ADVERTENCIA" in choice.report


# --- Memoria viva: VRAM del dispositivo, o RAM total ------------------------

def test_live_memory_uses_device_vram_when_present():
    assert mf.live_memory_bytes(8192) == 8192 * 1024 * 1024


def test_live_memory_falls_back_to_total_ram(monkeypatch):
    monkeypatch.setattr(mf, "total_ram_bytes", lambda: 16 * 1024**3)
    assert mf.live_memory_bytes(None) == 16 * 1024**3


def test_total_ram_bytes_is_positive_or_none():
    # En esta maquina devuelve la RAM real; en un entorno raro puede ser None. Nunca
    # cero ni negativo.
    ram = mf.total_ram_bytes()
    assert ram is None or ram > 0
