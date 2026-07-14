'use client'

import { useState } from 'react'
import type { RepairAttempt } from '@/lib/api'

interface RepairPanelProps {
  attempts: RepairAttempt[]
  // Only meaningful once a run has completed.
  hasRun: boolean
}

// Accordion of self-repair attempts. Hidden pre-run; shows "no repairs needed"
// when the first generation executed cleanly.
export default function RepairPanel({ attempts, hasRun }: RepairPanelProps) {
  const [openIdx, setOpenIdx] = useState<number | null>(0)

  if (!hasRun) return null

  if (attempts.length === 0) {
    return (
      <section className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 shadow-sm">
        <div className="flex items-center gap-2 text-sm font-medium text-emerald-700">
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
          </svg>
          No repairs needed — code executed on the first attempt.
        </div>
      </section>
    )
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center gap-2 px-4 py-3 text-sm font-semibold text-slate-800">
        <svg className="h-4 w-4 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
        </svg>
        Self-repair log
        <span className="ml-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
          {attempts.length} of 3
        </span>
      </div>

      <ul className="divide-y divide-slate-100 border-t border-slate-100">
        {attempts.map((a, i) => {
          const isOpen = openIdx === i
          return (
            <li key={a.attempt}>
              <button
                type="button"
                onClick={() => setOpenIdx(isOpen ? null : i)}
                className="flex w-full items-center justify-between px-4 py-2.5 text-left"
                aria-expanded={isOpen}
              >
                <span className="flex items-center gap-2 text-sm font-medium text-slate-700">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-amber-100 text-xs font-semibold text-amber-700">
                    {a.attempt}
                  </span>
                  Attempt {a.attempt}
                </span>
                <svg
                  className={`h-4 w-4 text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {isOpen && (
                <div className="space-y-3 px-4 pb-4">
                  <div>
                    <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-red-600">Error</p>
                    <pre className="overflow-auto rounded-md bg-red-50 p-2 text-xs text-red-800">{a.error}</pre>
                  </div>
                  <div>
                    <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-emerald-600">Fix applied</p>
                    <p className="rounded-md bg-emerald-50 p-2 text-xs text-emerald-800">{a.change_summary}</p>
                  </div>
                </div>
              )}
            </li>
          )
        })}
      </ul>
    </section>
  )
}
