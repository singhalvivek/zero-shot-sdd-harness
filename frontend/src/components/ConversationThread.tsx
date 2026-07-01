'use client'

import type { Usage } from '@/lib/api'

export interface Turn {
  id: string
  question: string
  answer: string
  status: 'streaming' | 'complete' | 'error' | 'clarifying'
  error?: string | null
  clarify?: string | null
  suggestions?: string[]
  usage?: Usage | null
}

export function ConversationThread({
  turns,
  streamingStarted,
  onAskSuggestion,
  disabled,
}: {
  turns: Turn[]
  streamingStarted: boolean
  onAskSuggestion: (question: string) => void
  disabled: boolean
}) {
  if (turns.length === 0) {
    return (
      <div data-testid="thread-empty" className="rounded-xl border border-dashed border-gray-200 bg-white p-8 text-center">
        <p className="text-sm text-gray-400">Upload a CSV, then ask a question about your data.</p>
      </div>
    )
  }

  return (
    <div data-testid="conversation-thread" className="space-y-4">
      {turns.map(turn => (
        <div key={turn.id} data-testid="conversation-turn" className="space-y-2">
          {/* user question */}
          <div className="flex justify-end">
            <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-blue-600 px-4 py-2 text-sm text-white">
              {turn.question}
            </div>
          </div>

          {/* agent response: clarifying question, answer, or error */}
          <div className="flex justify-start">
            {turn.status === 'clarifying' || turn.clarify ? (
              <div
                data-testid="clarify-bubble"
                className="max-w-[85%] rounded-2xl rounded-bl-sm border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900"
              >
                <div className="mb-1 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-amber-700">
                  <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10" />
                    <path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3" strokeLinecap="round" />
                    <path d="M12 17h.01" strokeLinecap="round" />
                  </svg>
                  I need a bit more detail
                </div>
                <span data-testid="clarify-text" className="whitespace-pre-wrap">
                  {turn.clarify}
                </span>
                <p className="mt-2 text-xs text-amber-600">Reply in the box below to continue.</p>
              </div>
            ) : (
              <div
                data-testid="answer-bubble"
                className={`max-w-[85%] rounded-2xl rounded-bl-sm border px-4 py-3 text-sm whitespace-pre-wrap ${
                  turn.status === 'error'
                    ? 'border-red-200 bg-red-50 text-red-700'
                    : 'border-gray-200 bg-white text-gray-800'
                }`}
              >
                {turn.status === 'error' ? (
                  <span data-testid="answer-error">{turn.error}</span>
                ) : turn.answer ? (
                  <span data-testid="answer-text">{turn.answer}</span>
                ) : (
                  <Spinner />
                )}
              </div>
            )}
          </div>

          {/* per-turn: real token-usage badge + follow-up chips (live in P2) */}
          {turn.status === 'complete' && (
            <div className="flex flex-wrap items-center justify-start gap-2 pl-1">
              {turn.usage && (
                <span
                  data-testid="token-usage-badge"
                  title="Token usage for this query"
                  className="inline-flex items-center gap-1.5 rounded-full border border-gray-200 bg-gray-50 px-2.5 py-0.5 text-xs font-medium text-gray-600"
                >
                  <svg className="h-3 w-3 text-gray-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M3 12h4l3 8 4-16 3 8h4" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  {(turn.usage.prompt_tokens ?? 0).toLocaleString()} prompt + {(turn.usage.completion_tokens ?? 0).toLocaleString()} completion tokens
                </span>
              )}
              {turn.suggestions && turn.suggestions.length > 0 && (
                <div data-testid="followup-chips" className="flex flex-wrap items-center gap-2">
                  {turn.suggestions.map(chip => (
                    <button
                      key={chip}
                      type="button"
                      data-testid="followup-chip"
                      disabled={disabled}
                      onClick={() => onAskSuggestion(chip)}
                      className="rounded-full border border-blue-200 bg-blue-50 px-3 py-0.5 text-xs font-medium text-blue-700 transition-colors hover:border-blue-300 hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {chip}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

function Spinner() {
  return (
    <span data-testid="answer-spinner" className="inline-flex items-center gap-2 text-gray-400">
      <svg className="h-4 w-4 animate-spin text-blue-500" viewBox="0 0 24 24" fill="none">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
      </svg>
      Analysing your data…
    </span>
  )
}
