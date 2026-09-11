"""Provider-neutral OpenAI client setup with optional Langfuse tracing.

Langfuse is deliberately isolated in this module. The application keeps using
the regular OpenAI client when tracing is disabled, unconfigured, or not
installed, so telemetry can never become a runtime dependency for AI features.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Mapping

from openai import AsyncOpenAI

from app.utils.config import Settings, get_settings


logger = logging.getLogger(__name__)
_langfuse_setup_attempted = False


def _mask_otel_spans(*, params: Any) -> Any:
    """Remove prompt/completion attributes before Langfuse export.

    The type imports stay inside this function so the application remains
    importable when the optional Langfuse package is not installed.
    """
    from langfuse.types import MaskOtelSpansResult, OtelSpanPatch

    patches: dict[Any, Any] = {}
    for identifier, span in params.spans.items():
        delete_attributes = tuple(
            attribute
            for attribute in span.attributes
            if attribute.startswith(("gen_ai.prompt", "gen_ai.completion"))
        )
        if delete_attributes:
            patches[identifier] = OtelSpanPatch(
                delete_attributes=delete_attributes,
                set_attributes={"diagrammatic.masking_applied": True},
            )
    return MaskOtelSpansResult(span_patches=patches) if patches else None


def is_langfuse_configured(settings: Settings) -> bool:
    """Return whether Langfuse has the minimum configuration to emit traces."""
    return bool(
        settings.langfuse_enabled
        and settings.langfuse_public_key
        and settings.langfuse_secret_key
    )


def _configure_langfuse_environment(settings: Settings) -> None:
    """Expose validated settings to the lazily imported Langfuse SDK."""
    os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key or ""
    os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key or ""
    os.environ["LANGFUSE_BASE_URL"] = settings.langfuse_base_url
    os.environ["LANGFUSE_TRACING_ENABLED"] = "true"
    os.environ["LANGFUSE_SAMPLE_RATE"] = str(settings.langfuse_sample_rate)
    os.environ["LANGFUSE_TRACING_ENVIRONMENT"] = settings.langfuse_environment
    if settings.langfuse_release:
        os.environ["LANGFUSE_TRACING_RELEASE"] = settings.langfuse_release


def create_llm_client(settings: Settings | None = None) -> AsyncOpenAI:
    """Create the configured LLM client without making telemetry mandatory."""
    resolved_settings = settings or get_settings()
    if not is_langfuse_configured(resolved_settings):
        return AsyncOpenAI(api_key=resolved_settings.openai_api_key)

    global _langfuse_setup_attempted
    _configure_langfuse_environment(resolved_settings)

    try:
        # Import only after environment variables have been loaded. This keeps
        # Langfuse optional and lets the SDK read Cloud or self-hosted settings.
        if not _langfuse_setup_attempted:
            from langfuse import Langfuse

            langfuse_options: dict[str, Any] = {
                "sample_rate": resolved_settings.langfuse_sample_rate,
            }
            if not resolved_settings.langfuse_capture_content:
                langfuse_options["mask_otel_spans"] = _mask_otel_spans
            Langfuse(**langfuse_options)

            logger.info(
                "Langfuse tracing enabled environment=%s sample_rate=%s capture_content=%s",
                resolved_settings.langfuse_environment,
                resolved_settings.langfuse_sample_rate,
                resolved_settings.langfuse_capture_content,
            )
            _langfuse_setup_attempted = True

        from langfuse.openai import AsyncOpenAI as LangfuseAsyncOpenAI
        return LangfuseAsyncOpenAI(api_key=resolved_settings.openai_api_key)
    except ImportError:
        logger.warning(
            "Langfuse is configured but the optional package is unavailable; "
            "continuing with OpenAI without telemetry"
        )
        return AsyncOpenAI(api_key=resolved_settings.openai_api_key)
    except Exception:
        # Observability must not take down an assessment request because of a
        # client initialization/configuration issue.
        logger.exception(
            "Langfuse client initialization failed; continuing without telemetry"
        )
        return AsyncOpenAI(api_key=resolved_settings.openai_api_key)


def langfuse_options(
    settings: Settings,
    *,
    name: str,
    tags: tuple[str, ...] = (),
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build Langfuse-only request attributes when tracing is enabled.

    The returned dictionary is empty for the native OpenAI client, avoiding
    unsupported provider arguments when telemetry is disabled.
    """
    if not is_langfuse_configured(settings):
        return {}

    trace_metadata: dict[str, Any] = {
        "langfuse_tags": ["diagrammatic", *tags],
        "feature": name,
    }
    if metadata:
        trace_metadata.update(metadata)
    return {"name": name, "metadata": trace_metadata}


def flush_langfuse(settings: Settings | None = None) -> None:
    """Flush queued traces during graceful application shutdown."""
    resolved_settings = settings or get_settings()
    if not is_langfuse_configured(resolved_settings) or not _langfuse_setup_attempted:
        return

    try:
        from langfuse import get_client

        get_client().flush()
    except Exception:
        logger.exception("Langfuse flush failed during application shutdown")
