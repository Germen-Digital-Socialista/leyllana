from leyllana.config import Config, load


def test_load_defaults_when_no_file(tmp_path):
    cfg = load(tmp_path / "no-existe.toml")
    assert isinstance(cfg, Config)
    assert cfg.engine.provider == "local"


def test_load_reads_toml(tmp_path):
    toml = tmp_path / "leyllana.toml"
    toml.write_text(
        '[engine]\n'
        'provider = "local"\n'
        '[engine.models.default]\n'
        'path = "m.gguf"\n'
        "ctx = 8192\n",
        encoding="utf-8",
    )
    cfg = load(toml)
    assert cfg.engine.provider == "local"
    assert cfg.engine.default_model.path == "m.gguf"
    assert cfg.engine.default_model.ctx == 8192


def test_engine_generation_defaults():
    cfg = Config()
    assert cfg.engine.server_path is None
    assert cfg.engine.gpu == "auto"
    assert cfg.engine.temperature == 0.2
    assert cfg.engine.max_tokens == 1024
    assert cfg.engine.threads == 0


def test_load_reads_server_and_generation_fields(tmp_path):
    toml = tmp_path / "leyllana.toml"
    toml.write_text(
        "[engine]\n"
        'provider = "local"\n'
        'server_path = "C:/bin/llama-server.exe"\n'
        'gpu = "cpu"\n'
        "temperature = 0.35\n"
        "max_tokens = 2048\n"
        "threads = 4\n",
        encoding="utf-8",
    )
    cfg = load(toml)
    assert cfg.engine.server_path == "C:/bin/llama-server.exe"
    assert cfg.engine.gpu == "cpu"
    assert cfg.engine.temperature == 0.35
    assert cfg.engine.max_tokens == 2048
    assert cfg.engine.threads == 4
