'use client'

import { useCallback, useEffect, useState } from 'react'
import { listSessions, type SessionSummary } from '@/lib/api'

function formatTimestamp(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function SessionSwitcher({
  activeSessionId,
  onResume,
  onNewSession,
  reloadToken,
}: {
  activeSessionId: string | null
  onResume: (sessionId: string) => void
  onNewSession: () => void
  /** Bump to force a reload (e.g. after an upload/ask creates or updates a session). */
  reloadToken: number
}) {
  const [open, setOpen] = useState(false)
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setSessions(await listSessions())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load your sessions.')
    } finally {
      setLoading(false)
    }
  }, [])

  // Refresh the list whenever opened or when the parent signals a change.
  useEffect(() => {
    if (open) void load()
  }, [open, reloadToken, load])

  return (
    <div className="relative">
      <button
        type="button"
        data-testid="session-switcher-toggle"
        onClick={() => setOpen(o => !o)}
        className="inline-flex items-center gap-1.5 rounded-md border border-gray-300 px-3 py-1 text-xs font-medium text-gray-600 hover:bg-gray-50"
      >
        <svg className="h-3.5 w-3.5 text-gray-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M3 12h18M3 6h18M3 18h18" strokeLinecap="round" />
        </svg>
        Sessions
      </button>

      {open && (
        <div
          data-testid="session-switcher-panel"
          className="absolute right-0 z-20 mt-2 w-80 rounded-xl border border-gray-200 bg-white p-2 shadow-lg"
        >
          <div className="flex items-center justify-between px-2 py-1">
            <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">Sessions</span>
            <button
              type="button"
              data-testid="new-session"
              onClick={() => {
                onNewSession()
                setOpen(false)
              }}
              className="rounded-md bg-blue-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-blue-700"
            >
              + New session
            </button>
          </div>

          <div className="mt-1 max-h-96 overflow-y-auto">
            {loading ? (
              <div data-testid="session-loading" className="py-8 text-center text-xs text-gray-400">
                Loading sessions…
              </div>
            ) : error ? (
              <div
                data-testid="session-error"
                className="m-1 rounded-lg border border-red-200 bg-red-50 p-2 text-xs text-red-700"
              >
                {error}
              </div>
            ) : sessions.length === 0 ? (
              <div data-testid="session-empty" className="py-8 text-center text-xs text-gray-400">
                No prior sessions yet. Upload a file to start one.
              </div>
            ) : (
              <ul data-testid="session-list" className="space-y-1">
                {sessions.map(s => {
                  const active = s.session_id === activeSessionId
                  return (
                    <li key={s.session_id}>
                      <button
                        type="button"
                        data-testid="session-item"
                        onClick={() => {
                          onResume(s.session_id)
                          setOpen(false)
                        }}
                        className={`w-full rounded-lg border p-2.5 text-left transition-colors ${
                          active
                            ? 'border-blue-300 bg-blue-50'
                            : 'border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <span className="truncate text-sm font-medium text-gray-800" title={s.title}>
                            {s.title || 'Untitled session'}
                          </span>
                          {active && (
                            <span className="shrink-0 text-[10px] font-semibold uppercase text-blue-600">Active</span>
                          )}
                        </div>
                        {s.last_question && (
                          <p className="mt-0.5 line-clamp-1 text-xs text-gray-500">{s.last_question}</p>
                        )}
                        <div className="mt-1 flex flex-wrap items-center gap-x-2 text-[11px] text-gray-400">
                          <span data-testid="session-dataset-count">
                            {s.dataset_count} {s.dataset_count === 1 ? 'dataset' : 'datasets'}
                          </span>
                          <span>·</span>
                          <span>{s.message_count} msgs</span>
                          <span>·</span>
                          <span data-testid="session-timestamp">{formatTimestamp(s.updated_at)}</span>
                        </div>
                      </button>
                    </li>
                  )
                })}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
