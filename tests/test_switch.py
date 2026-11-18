from app import provider_state
from core import providers


TABLE = providers.DRAFT_PROVIDERS


def test_switch_to_new_provider_resets_model_and_base():
    state = provider_state.switch_state(
        "draft", "moonshot", "deepseek", "deepseek-flash", "", TABLE,
    )
    assert state == {"model": "", "base": "", "clear_key": True}


def test_switch_back_restores_saved_model():
    state = provider_state.switch_state(
        "draft", "deepseek", "deepseek", "deepseek-flash", "", TABLE,
    )
    assert state["model"] == "deepseek-flash"
    assert state["clear_key"] is True


def test_custom_base_is_not_carried_to_another_provider():
    state = provider_state.switch_state(
        "draft", "custom_anthropic", "custom_openai",
        "model-a", "https://old.example/v1", TABLE,
    )
    assert state["base"] == ""


def test_custom_base_returns_when_switching_back():
    state = provider_state.switch_state(
        "draft", "custom_openai", "custom_openai",
        "model-a", "https://old.example/v1", TABLE,
    )
    assert state["base"] == "https://old.example/v1"


def test_key_owner_mismatch_is_not_configured():
    assert provider_state.key_state("moonshot", "deepseek", True) == {
        "mismatch": True, "configured": False,
    }
    assert provider_state.key_state("deepseek", "deepseek", True) == {
        "mismatch": False, "configured": True,
    }
    assert provider_state.key_state("deepseek", "", True) == {
        "mismatch": False, "configured": True,
    }


def test_key_for_another_scope_needs_reentry():
    assert provider_state.key_state("custom_openai", "custom_openai", False, True) == {
        "mismatch": True, "configured": False,
    }


def test_model_fetch_result_is_only_accepted_by_current_request():
    ticket = ("custom_openai", "https://a.example/v1", 1)
    assert provider_state.fetch_is_current(
        ticket, ("custom_openai", "https://a.example/v1", 1))
    assert not provider_state.fetch_is_current(
        ticket, ("custom_openai", "https://b.example/v1", 1))
    assert not provider_state.fetch_is_current(
        ticket, ("moonshot", "https://a.example/v1", 1))
    assert not provider_state.fetch_is_current(
        ticket, ("custom_openai", "https://a.example/v1", 2))
    assert not provider_state.fetch_is_current(ticket, None)
