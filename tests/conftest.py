import pytest


@pytest.fixture(autouse=True)
def isolated_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("TRAMAMIND_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("TRAMAMIND_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr("router.keystore.keyring_available", lambda: False)
    monkeypatch.setattr("router.runtime.detect_best_backend", lambda: "plain")
    yield
