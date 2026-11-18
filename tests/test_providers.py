from core import providers


def test_openrouter_is_gone():
    assert "openrouter" not in providers.DRAFT_PROVIDERS
    assert "openrouter" not in providers.JEV_PROVIDERS
    assert "OPENROUTER_API_KEY" not in providers.ENV_VARS
    for spec in providers.DRAFT_PROVIDERS.values():
        assert "openrouter" not in (spec.base or "").lower()


def test_only_two_api_types():
    assert {spec.api_type for spec in providers.DRAFT_PROVIDERS.values()} == {
        "openai", "anthropic",
    }
    assert providers.API_TYPES == ("openai", "anthropic")


def test_domestic_presets_have_https_bases():
    for key in ("deepseek", "moonshot", "zhipu", "dashscope", "siliconflow",
                "stepfun", "baichuan", "anthropic"):
        assert providers.DRAFT_PROVIDERS[key].base.startswith("https://")


def test_custom_sources_need_base_url():
    for key in providers.CUSTOM:
        assert providers.DRAFT_PROVIDERS[key].base == ""
        assert providers.is_custom(key)


def test_default_and_fallback():
    assert next(iter(providers.DRAFT_PROVIDERS)) == providers.DEFAULT_DRAFT
    assert providers.get_draft("missing").name == providers.DRAFT_PROVIDERS[
        providers.DEFAULT_DRAFT
    ].name
