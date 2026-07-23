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
