from router.keystore import delete_key, get_key, mask, store_key
from router.profile import fresh_profile, load_profile, save_profile
from router.runtime import redact


def test_plain_keystore_roundtrip_and_kimi_alias(monkeypatch):
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
    store_key("kimi", "sk-test-123456", "plain")
    key, storage = get_key("moonshot")
    assert key == "sk-test-123456"
    assert storage == "plain"
    assert mask(key).endswith("3456")
    assert "plain" in delete_key("kimi")
    assert get_key("kimi")[0] is None


def test_profile_roundtrip_uses_real_ollama_tags():
    save_profile(fresh_profile("gpu12"))
    loaded = load_profile()
    assert loaded.models.general == "qwen3:8b"
    assert loaded.models.summary == "gemma3:4b"
    assert loaded.omniroute_memory_mb == 1024
    assert "gemopus" not in loaded.models.general


def test_missing_ollama_is_a_failure(monkeypatch):
    from router.runtime import checks
    save_profile(fresh_profile("cpu16"))
    monkeypatch.setattr("router.runtime.shutil.which", lambda _name: None)
    items = checks()
    assert any(item.name == "ollama" and item.level == "fail" for item in items)


def test_redact_removes_the_secret():
    assert "sk-live" not in redact("errore sk-live nel log", ["sk-live"])
