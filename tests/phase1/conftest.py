import pytest


@pytest.fixture
def _require_gemini_key():
    """Skip only if the Gemini key is genuinely absent from .env."""
    from config.settings import get_settings

    if not get_settings().gemini_api_key:
        pytest.skip("AGENT_GEMINI_API_KEY not set in .env")
