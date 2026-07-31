"""Tests de la escritura de leyllana.toml desde la GUI (ADR 0021).

Lo que importa es que sea una sola verdad: lo que la GUI guarda tiene que ser lo
mismo que la CLI vuelve a leer, sin campos perdidos ni valores inventados.
"""

import pytest

from leyllana.config import (
    CliConfig,
    Config,
    EngineConfig,
    GuiConfig,
    ModelConfig,
    dumps,
    load,
    save,
)


def _config_completa() -> Config:
    return Config(
        engine=EngineConfig(
            provider="cli",
            default_model=ModelConfig(path=r"C:\modelos\qwen3-4b.gguf", ctx=8192),
            fallback_model=ModelConfig(path="qwen3-1.7b.gguf", ctx=2048),
            reranker_model=ModelConfig(path="qwen3-reranker-0.6b.gguf", ctx=2048),
            cli=CliConfig(
                preset="claude",
                command=("otro", "--flag"),
                model="sonnet",
                timeout=120.0,
                ctx_tokens=200_000,
            ),
            server_path=r"C:\llama\llama-server.exe",
            gpu="cpu",
            kv_cache_type="q8_0",
            model_selection="fallback",
            temperature=0.1,
            max_tokens=2048,
            threads=4,
        ),
        gui=GuiConfig(theme="oscuro", font_size=18),
    )


def test_ida_y_vuelta_conserva_todo(tmp_path):
    original = _config_completa()
    destino = tmp_path / "leyllana.toml"
    assert save(original, destino) == destino
    assert load(destino) == original


def test_los_defaults_tambien_dan_la_vuelta(tmp_path):
    destino = tmp_path / "leyllana.toml"
    save(Config(), destino)
    assert load(destino) == Config()


def test_una_ruta_de_windows_no_se_rompe_al_escribirla(tmp_path):
    # Las contrabarras son escapes en TOML: sin escaparlas, la ruta vuelve mal o
    # el archivo ni siquiera carga.
    cfg = Config(engine=EngineConfig(server_path=r"C:\Program Files\llama\srv.exe"))
    destino = tmp_path / "leyllana.toml"
    save(cfg, destino)
    assert load(destino).engine.server_path == r"C:\Program Files\llama\srv.exe"


def test_un_campo_sin_determinar_no_se_escribe_vacio(tmp_path):
    # Igual que SourceInfo: None significa "no configurado", no cadena vacia.
    destino = tmp_path / "leyllana.toml"
    save(Config(), destino)
    texto = destino.read_text(encoding="utf-8")
    assert "server_path" not in texto
    assert "preset" not in texto


def test_guardar_no_deja_basura_al_lado(tmp_path):
    destino = tmp_path / "leyllana.toml"
    save(_config_completa(), destino)
    assert [p.name for p in tmp_path.iterdir()] == ["leyllana.toml"]


def test_un_fallo_al_escribir_no_destruye_la_config_anterior(tmp_path, monkeypatch):
    destino = tmp_path / "leyllana.toml"
    save(Config(), destino)
    antes = destino.read_text(encoding="utf-8")

    monkeypatch.setattr(
        "leyllana.config.dumps", lambda cfg: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    with pytest.raises(RuntimeError):
        save(_config_completa(), destino)

    assert destino.read_text(encoding="utf-8") == antes
    assert [p.name for p in tmp_path.iterdir()] == ["leyllana.toml"]


def test_claves_desconocidas_no_tumban_la_lectura(tmp_path):
    destino = tmp_path / "leyllana.toml"
    destino.write_text(
        '[engine]\nprovider = "local"\ninvento = 1\n\n[otra_cosa]\nx = 2\n',
        encoding="utf-8",
    )
    assert load(destino).engine.provider == "local"


def test_dumps_es_toml_valido_y_estable():
    cfg = _config_completa()
    assert dumps(cfg) == dumps(cfg)
    assert "[engine.models.default]" in dumps(cfg)
    assert "[gui]" in dumps(cfg)
