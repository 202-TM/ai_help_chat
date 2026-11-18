import json
import threading
import time

import pytest

from app import settings
from core.providers import LLM_ENV


def _fake_read(monkeypatch, config):
    monkeypatch.setattr(
        settings, "_read",
        lambda name, default=None: config.get(name, default),
    )


def _fake_env(monkeypatch, env):
    monkeypatch.setattr(settings, "_read_env", lambda name: env.get(name, ""))


def test_legacy_deepseek_key_is_owned_by_deepseek_only(monkeypatch):
    _fake_read(monkeypatch, {})
    _fake_env(monkeypatch, {"DEEPSEEK_API_KEY": "sk-legacy"})

    assert settings.key_owner() == "deepseek"
    assert settings.llm_key_for("deepseek") == "sk-legacy"
    assert settings.key_owner() == "deepseek"
    assert settings.llm_key_for("deepseek") == "sk-legacy"
    assert settings.llm_key_for("moonshot") == ""


def test_redaction_is_on_by_default(monkeypatch):
    _fake_read(monkeypatch, {})
    assert settings.redact_sensitive() is True


def test_unowned_llm_key_is_not_guessed_for_any_provider(monkeypatch):
    _fake_read(monkeypatch, {})
    _fake_env(monkeypatch, {LLM_ENV: "sk-unknown"})

    assert settings.key_owner() == ""
    assert settings.llm_key_for("deepseek") == ""
    assert settings.llm_key_for("moonshot") == ""


def test_legacy_key_does_not_cross_over_when_owner_is_another_provider(monkeypatch):
    _fake_read(monkeypatch, {"key_owner": "moonshot"})
    _fake_env(monkeypatch, {"DEEPSEEK_API_KEY": "sk-legacy"})

    assert settings.llm_key_for("moonshot") == ""
    assert settings.llm_key_for("deepseek") == ""


def test_custom_key_is_bound_to_the_base_url(monkeypatch):
    _fake_read(monkeypatch, {
        "draft_provider": "custom_openai",
        "draft_base_url": "https://old.example/v1",
        "key_owner": "custom_openai",
        "key_base_url": "https://old.example/v1",
        "key_fingerprint": settings.key_fingerprint("sk-custom"),
    })
    _fake_env(monkeypatch, {LLM_ENV: "sk-custom"})

    assert settings.llm_key_for("custom_openai", "https://old.example/v1/") == "sk-custom"
    assert settings.llm_key_for("custom_openai", "https://new.example/v1") == ""


def test_save_does_not_copy_legacy_key_to_new_env_for_another_provider(
        monkeypatch, tmp_path):
    config = {
        "relationship": "friends",
        "draft_provider": "moonshot",
        "key_owner": "moonshot",
    }
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps(config), encoding="utf-8")
    _fake_env(monkeypatch, {"DEEPSEEK_API_KEY": "sk-legacy"})
    monkeypatch.setattr(settings, "_CONFIG", str(cfg))
    written = []
    monkeypatch.setattr(settings, "_set_key", lambda env, value: written.append((env, value)))
    monkeypatch.setattr(settings, "_notify_env", lambda: None)

    settings.save()

    assert written == []
    saved = json.loads(cfg.read_text(encoding="utf-8"))
    assert saved["key_owner"] == "moonshot"


def test_save_typed_key_claims_the_selected_provider(monkeypatch, tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text("{}", encoding="utf-8")
    _fake_env(monkeypatch, {})
    monkeypatch.setattr(settings, "_CONFIG", str(cfg))
    written = []
    monkeypatch.setattr(settings, "_set_key", lambda env, value: written.append((env, value)))
    monkeypatch.setattr(settings, "_notify_env", lambda: None)

    settings.save(draft_provider_text="moonshot", llm_key_text="sk-new")

    assert written == [(LLM_ENV, "sk-new")]
    saved = json.loads(cfg.read_text(encoding="utf-8"))
    assert saved["key_owner"] == "moonshot"
    assert saved["draft_provider"] == "moonshot"
    assert saved["key_fingerprint"] == settings.key_fingerprint("sk-new")


def test_save_custom_key_records_its_base_url(monkeypatch, tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text("{}", encoding="utf-8")
    _fake_env(monkeypatch, {})
    monkeypatch.setattr(settings, "_CONFIG", str(cfg))
    monkeypatch.setattr(settings, "_set_key", lambda env, value: None)
    monkeypatch.setattr(settings, "_notify_env", lambda: None)

    settings.save(draft_provider_text="custom_openai", llm_key_text="sk-new",
                  draft_base_url_text="https://new.example/v1/")

    saved = json.loads(cfg.read_text(encoding="utf-8"))
    assert saved["key_owner"] == "custom_openai"
    assert saved["key_base_url"] == "https://new.example/v1"
    assert saved["key_fingerprint"] == settings.key_fingerprint("sk-new")


def test_save_can_disable_redaction(monkeypatch, tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings, "_CONFIG", str(cfg))

    settings.save(redact_sensitive_on=False)

    saved = json.loads(cfg.read_text(encoding="utf-8"))
    assert saved["redact_sensitive"] is False


def test_failed_config_write_does_not_replace_old_provider_key(monkeypatch, tmp_path):
    cfg = tmp_path / "config.json"
    cfg.mkdir()
    _fake_env(monkeypatch, {})
    monkeypatch.setattr(settings, "_CONFIG", str(cfg))
    written = []
    monkeypatch.setattr(settings, "_set_key", lambda env, value: written.append((env, value)))
    monkeypatch.setattr(settings, "_notify_env", lambda: None)

    with pytest.raises(OSError):
        settings.save(draft_provider_text="moonshot", llm_key_text="sk-new")

    assert written == []


def test_saved_key_must_match_its_fingerprint(monkeypatch):
    _fake_read(monkeypatch, {
        "draft_provider": "moonshot",
        "key_owner": "moonshot",
        "key_fingerprint": settings.key_fingerprint("sk-new"),
    })
    _fake_env(monkeypatch, {LLM_ENV: "sk-old"})

    assert settings.llm_key_for("moonshot") == ""
    assert settings.key_owner() == "moonshot"


def test_key_without_fingerprint_is_not_trusted(monkeypatch):
    _fake_read(monkeypatch, {
        "draft_provider": "moonshot",
        "key_owner": "moonshot",
    })
    _fake_env(monkeypatch, {LLM_ENV: "sk-old"})

    assert settings.llm_key_for("moonshot") == ""


def test_registry_failure_cannot_bind_old_key_to_new_provider(monkeypatch, tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({
        "draft_provider": "deepseek",
        "key_owner": "deepseek",
        "key_fingerprint": settings.key_fingerprint("sk-old"),
    }), encoding="utf-8")
    env = {LLM_ENV: "sk-old"}
    monkeypatch.setattr(settings, "_CONFIG", str(cfg))
    monkeypatch.setattr(settings, "_read_env", lambda name: env.get(name, ""))
    monkeypatch.setattr(settings, "_notify_env", lambda: None)

    def fail_set(name, value):
        raise OSError("registry denied")

    monkeypatch.setattr(settings, "_set_key", fail_set)

    with pytest.raises(OSError):
        settings.save(draft_provider_text="moonshot", llm_key_text="sk-new")

    saved = json.loads(cfg.read_text(encoding="utf-8"))
    assert saved["draft_provider"] == "moonshot"
    assert saved["key_owner"] == "moonshot"
    assert saved["key_fingerprint"] == settings.key_fingerprint("sk-new")
    assert env[LLM_ENV] == "sk-old"
    assert settings.llm_key_for("moonshot") == ""


def test_interrupted_save_cannot_reuse_old_key_after_restart(monkeypatch, tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({
        "draft_provider": "moonshot",
        "key_owner": "moonshot",
        "key_fingerprint": settings.key_fingerprint("sk-new"),
    }), encoding="utf-8")
    _fake_env(monkeypatch, {LLM_ENV: "sk-old"})
    monkeypatch.setattr(settings, "_CONFIG", str(cfg))

    assert settings.llm_key_for("moonshot") == ""


def test_flag_only_save_preserves_key_fingerprint(monkeypatch, tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({
        "draft_provider": "deepseek",
        "key_owner": "deepseek",
        "key_fingerprint": settings.key_fingerprint("sk-ok"),
    }), encoding="utf-8")
    env = {LLM_ENV: "sk-ok"}
    monkeypatch.setattr(settings, "_CONFIG", str(cfg))
    monkeypatch.setattr(settings, "_read_env", lambda name: env.get(name, ""))

    settings.save(redact_sensitive_on=False)

    saved = json.loads(cfg.read_text(encoding="utf-8"))
    assert saved["key_fingerprint"] == settings.key_fingerprint("sk-ok")
    assert settings.llm_key_for("deepseek") == "sk-ok"


def test_analysis_snapshot_waits_for_complete_key_and_config_save(monkeypatch, tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({
        "relationship": "friends",
        "draft_provider": "deepseek",
        "draft_model": "deepseek-flash",
        "key_owner": "deepseek",
        "key_fingerprint": settings.key_fingerprint("sk-old"),
    }), encoding="utf-8")
    env = {LLM_ENV: "sk-old"}
    started = threading.Event()
    release = threading.Event()
    errors = []
    snapshots = []

    monkeypatch.setattr(settings, "_CONFIG", str(cfg))
    monkeypatch.setattr(settings, "_read_env", lambda name: env.get(name, ""))

    def set_key(name, value):
        if name == LLM_ENV:
            started.set()
            assert release.wait(2)
            env[name] = value

    monkeypatch.setattr(settings, "_set_key", set_key)
    monkeypatch.setattr(settings, "_notify_env", lambda: None)

    def save_new_provider():
        try:
            settings.save(
                draft_provider_text="moonshot",
                llm_key_text="sk-new",
                draft_model_text="kimi-k3",
            )
        except Exception as exc:  # pragma: no cover - 只用于把线程异常带回主线程
            errors.append(exc)

    def take_snapshot():
        try:
            snapshots.append(settings.analysis_snapshot())
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    writer = threading.Thread(target=save_new_provider)
    writer.start()
    assert started.wait(2)
    reader = threading.Thread(target=take_snapshot)
    reader.start()
    time.sleep(0.1)
    assert reader.is_alive(), "快照在保存提交完成前不应读到半套配置"
    release.set()
    writer.join(2)
    reader.join(2)

    assert not writer.is_alive() and not reader.is_alive()
    assert errors == []
    assert snapshots[-1]["provider"] == "moonshot"
    assert snapshots[-1]["model"] == "kimi-k3"
    assert snapshots[-1]["api_key"] == "sk-new"
