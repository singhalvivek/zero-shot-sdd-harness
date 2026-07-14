'use client'

import Phase2Badge from './Phase2Badge'

// Phase 2 stub: the history gallery of past parts. Rendered as muted,
// non-interactive placeholder tiles with a clear label so it is never mistaken
// for a bug or empty state.
export default function HistoryRail() {
  const tiles = [0, 1, 2, 3]
  return (
    <aside
      className="flex h-full flex-col rounded-xl border border-slate-200 bg-white shadow-sm"
      aria-label="History (coming in Phase 2)"
    >
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-700">History</h2>
        <Phase2Badge />
      </div>
      <div className="flex-1 space-y-3 overflow-hidden p-3 opacity-60">
        {tiles.map((t) => (
          <div
            key={t}
            className="pointer-events-none select-none rounded-lg border border-dashed border-slate-200 bg-slate-50 p-2"
          >
            <div className="mb-2 aspect-square w-full rounded-md bg-gradient-to-br from-slate-200 to-slate-100" />
            <div className="h-2.5 w-2/3 rounded bg-slate-200" />
            <div className="mt-1.5 h-2 w-1/2 rounded bg-slate-200" />
          </div>
        ))}
      </div>
      <p className="border-t border-slate-100 px-4 py-3 text-center text-xs text-slate-400">
        Your generated parts and their versions will be browsable here.
      </p>
    </aside>
  )
}
