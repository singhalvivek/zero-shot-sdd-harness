'use client'

import { ComingSoonBadge } from './ComingSoon'

export interface Turn {
  id: string
  question: string
  answer: string
  status: 'streaming' | 'complete' | 'error'
  error?: string | null
}

export function ConversationThread({ turns, streamingStarted }: { turns: Turn[]; streamingStarted: boolean }) {
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

          {/* agent answer */}
          <div className="flex justify-start">
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
              ) : turn.status === 'streaming' && streamingStarted ? (
                <Spinner />
              ) : (
                <Spinner />
              )}
            </div>
          </div>

          {/* per-turn P2 stubs: token-usage badge + follow-up chips */}
          {turn.status === 'complete' && (
            <div className="flex flex-wrap items-center justify-start gap-2 pl-1">
              <span
                data-testid="token-usage-stub"
                aria-disabled="true"
                className="inline-flex cursor-not-allowed items-center gap-1.5 rounded-full border border-dashed border-gray-300 bg-gray-50 px-2 py-0.5 text-xs text-gray-400 opacity-70"
              >
                Token usage
                <ComingSoonBadge>Coming soon</ComingSoonBadge>
              </span>
              {['Show the breakdown', 'Why is that?', 'Plot it'].map(chip => (
                <button
                  key={chip}
                  type="button"
                  disabled
                  data-testid="followup-chip"
                  aria-disabled="true"
                  className="cursor-not-allowed rounded-full border border-dashed border-gray-300 bg-gray-50 px-3 py-0.5 text-xs text-gray-400 opacity-70"
                >
                  {chip}
                </button>
              ))}
              <ComingSoonBadge>Follow-ups — coming soon</ComingSoonBadge>
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
