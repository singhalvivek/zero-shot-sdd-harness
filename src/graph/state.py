from typing import TypedDict


class AgentState(TypedDict, total=False):
    # Identity
    run_id: str
    part_id: str
    version_number: int

    # Input (from the trigger)
    prompt: str
    previous_code: str | None
    model_id: str
    mode: str                       # "generate" | "modify" | "edit"

    # Pipeline data (populated progressively)
    generated_code: str | None
    attempt_count: int              # repair attempts used so far (0..MAX)
    repair_attempts: list           # [{attempt, error, change_summary}]
    safety_violation: str | None
    exec_error: str | None
    token_usage: dict               # {prompt_tokens, completion_tokens, total_tokens}
    cost_usd: float

    # Output
    stl_path: str | None
    step_path: str | None
    code_path: str | None

    # Control
    error: str | None               # fatal → handle_error
    llm_error: bool                 # Gemini unreachable/auth → HTTP 502
    status: str                     # "completed" | "failed"
