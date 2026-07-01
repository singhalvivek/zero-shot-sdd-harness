from typing import TypedDict


class AgentState(TypedDict, total=False):
    # Identity
    run_id: str                          # audit_log row id, set at init
    session_id: str                      # conversation/session id

    # Input
    question: str                        # the user's natural-language question
    dataset_paths: dict[str, str]        # {df_name: local_file_path}
    schemas: dict[str, dict]             # per-df: columns, dtypes, row_count (NO cell values)
    messages: list                       # prior [{role, content}] turns

    # Pipeline data
    needs_clarification: bool            # triage (P2)
    clarifying_question: str | None      # triage (P2)
    plan: str                            # plan node
    code: str                            # write_code / refine
    exec_result: dict                    # sandbox output {ok, result_repr, stdout, error}
    refine_count: int                    # execute->refine loop counter

    # Output
    answer_text: str                     # answer node (streamed)
    suggestions: list                    # answer node follow-ups (P2)
    prompt_tokens: int                   # accumulated
    completion_tokens: int               # accumulated

    # Control
    error: str | None
    status: str                          # "completed" | "failed" | "needs_clarification"
