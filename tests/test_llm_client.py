from app.services.llm_client import is_langfuse_configured, langfuse_options
from app.utils.config import Settings


def make_settings(**overrides: object) -> Settings:
    values = {
        "openai_api_key": "test-openai-key",
        "langfuse_enabled": True,
        "langfuse_public_key": "pk-lf-test",
        "langfuse_secret_key": "sk-lf-test",
        "langfuse_base_url": "https://cloud.langfuse.com",
        "langfuse_environment": "test",
        "langfuse_release": None,
        "langfuse_sample_rate": 1.0,
        "langfuse_capture_content": False,
    }
    values.update(overrides)
    return Settings.model_construct(**values)


def test_langfuse_is_disabled_without_both_keys() -> None:
    settings = make_settings(langfuse_secret_key=None)

    assert is_langfuse_configured(settings) is False
    assert langfuse_options(settings, name="assessment.evaluate-design") == {}


def test_langfuse_options_include_stable_name_tags_and_safe_metadata() -> None:
    settings = make_settings()

    options = langfuse_options(
        settings,
        name="assessment.evaluate-design",
        tags=("assessment", "design"),
        metadata={"component_count": 4, "connection_count": 3},
    )

    assert options["name"] == "assessment.evaluate-design"
    assert options["metadata"]["langfuse_tags"] == [
        "diagrammatic",
        "assessment",
        "design",
    ]
    assert options["metadata"]["feature"] == "assessment.evaluate-design"
    assert options["metadata"]["component_count"] == 4
    assert options["metadata"]["connection_count"] == 3
    assert options["metadata"]["langfuse_session_id"].startswith("llm-")


def test_langfuse_options_preserve_explicit_session_id() -> None:
    settings = make_settings()

    options = langfuse_options(
        settings,
        name="interview.generate-questions",
        metadata={"langfuse_session_id": "browser-session-123"},
    )

    assert options["metadata"]["langfuse_session_id"] == "browser-session-123"


def test_langfuse_enabled_flag_can_turn_tracing_off() -> None:
    settings = make_settings(langfuse_enabled=False)

    assert is_langfuse_configured(settings) is False
    assert langfuse_options(settings, name="recommendations.generate") == {}
