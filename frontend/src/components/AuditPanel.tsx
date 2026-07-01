'use client'

import { useCallback, useEffect, useState } from 'react'
import { getAudit, type AuditEntry } from '@/lib/api'

function formatTimestamp(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    completed: 'border-green-200 bg-green-50 text-green-700',
    needs_clarification: 'border-amber-200 bg-amber-50 text-amber-700',
    failed: 'border-red-200 bg-red-50 text-red-700',
  }
  const label = status === 'needs_clarification' ? 'clarification' : status
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${
        styles[status] ?? 'border-gray-200 bg-gray-50 text-gray-600'
      }`}
    >
      {label}
    </span>
  )
}

export function AuditPanel({ sessionId }: { sessionId: string | null }) {
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getAudit(sessionId ?? undefined)
      setEntries(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load the audit log.')
    } finally {
      setLoading(false)
    }
  }, [sessionId])

  useEffect(() => {
    load()
  }, [load])

  return (
    <section data-testid="audit-panel" className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-gray-800">Audit log</h2>
          <p className="text-xs text-gray-500">Every query, its answer, token cost and status — newest first.</p>
        </div>
        <button
          type="button"
          data-testid="audit-refresh"
          onClick={load}
          disabled={loading}
          className="rounded-lg border border-gray-300 px-3 py-1 text-xs font-medium text-gray-600 hover:bg-gray-50 disabled:opacity-50"
        >
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {loading ? (
        <div data-testid="audit-loading" className="py-10 text-center text-sm text-gray-400">
          Loading the audit log…
        </div>
      ) : error ? (
        <div data-testid="audit-error" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      ) : entries.length === 0 ? (
        <div data-testid="audit-empty" className="py-10 text-center text-sm text-gray-400">
          No queries yet. Ask a question in the Chat view and it will appear here.
        </div>
      ) : (
        <ul data-testid="audit-list" className="space-y-3">
          {entries.map(entry => (
            <li
              key={entry.id}
              data-testid="audit-row"
              className="rounded-lg border border-gray-200 p-3"
            >
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm font-medium text-gray-800">{entry.question}</p>
                <StatusBadge status={entry.status} />
              </div>
              {entry.answer && (
                <p className="mt-1 line-clamp-2 text-xs text-gray-500">{entry.answer}</p>
              )}
              <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-400">
                <span data-testid="audit-timestamp">{formatTimestamp(entry.created_at)}</span>
                <span data-testid="audit-tokens">
                  {entry.prompt_tokens == null && entry.completion_tokens == null
                    ? '— tokens'
                    : `${(entry.prompt_tokens ?? 0).toLocaleString()} prompt + ${(entry.completion_tokens ?? 0).toLocaleString()} completion tokens`}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
