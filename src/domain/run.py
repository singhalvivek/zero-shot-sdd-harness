from pydantic import BaseModel

from config.settings import DEFAULT_MODEL_ID


class RunRequest(BaseModel):
    prompt: str
    model_id: str = DEFAULT_MODEL_ID
    mode: str = "generate"


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class RepairAttempt(BaseModel):
    attempt: int
    error: str | None = None
    change_summary: str | None = None


class RunResponse(BaseModel):
    run_id: str
    part_id: str | None = None
    version_number: int | None = None
    status: str
    generated_code: str | None = None
    repair_attempts: list = []
    safety_violation: str | None = None
    token_usage: dict = {}
    cost_usd: float = 0.0
    stl_url: str | None = None
    step_url: str | None = None
    code_url: str | None = None
    error: str | None = None
