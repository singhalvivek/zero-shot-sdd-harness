from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# --- Model policy ---------------------------------------------------------
# Verified against the live Gemini API with the .env key (2026-07-14). Other
# ids (gemini-2.5-*, *-pro) 404/429 with this free-tier key. See architecture.md.
ALLOWED_MODEL_IDS: frozenset[str] = frozenset(
    {"gemini-3.5-flash", "gemini-3.1-flash-lite"}
)
DEFAULT_MODEL_ID: str = "gemini-3.5-flash"

# --- Cost estimation ------------------------------------------------------
# NOTE: these are ESTIMATES for display only (USD per 1,000,000 tokens), NOT
# billed figures — Gemini pricing may differ and free-tier usage is $0. Shown
# in the UI so the user has a rough sense of spend.
COST_RATES: dict[str, dict[str, float]] = {
    "gemini-3.5-flash": {"input_per_1m": 0.30, "output_per_1m": 2.50},
    "gemini-3.1-flash-lite": {"input_per_1m": 0.10, "output_per_1m": 0.40},
}


def estimate_cost(token_usage: dict, model_id: str) -> float:
    """Estimate USD cost from token usage and the per-model rate table."""
    rates = COST_RATES.get(model_id)
    if not rates:
        return 0.0
    prompt_tokens = token_usage.get("prompt_tokens", 0) or 0
    completion_tokens = token_usage.get("completion_tokens", 0) or 0
    cost = (
        prompt_tokens / 1_000_000 * rates["input_per_1m"]
        + completion_tokens / 1_000_000 * rates["output_per_1m"]
    )
    return round(cost, 6)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = Field(default="sqlite:///./data/agent.db")
    log_level: str = Field(default="INFO")

    # LLM provider — auto-detected from whichever key is set if left blank
    llm_provider: str = Field(default="")   # "anthropic" | "gemini"
    llm_model: str = Field(default="")      # uses provider default when blank

    # Provider keys — set exactly one
    anthropic_api_key: str = Field(default="")
    gemini_api_key: str = Field(default="")

    # CAD sandbox tuning (env-overridable: AGENT_EXEC_TIMEOUT_SECONDS, ...)
    exec_timeout_seconds: int = Field(default=20)
    max_repair_attempts: int = Field(default=3)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
