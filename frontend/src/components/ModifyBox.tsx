'use client'

import Phase2Badge from './Phase2Badge'

// Phase 2 stub: natural-language follow-up to refine the current part. Disabled
// input, clearly labelled, so it reads as "coming soon" rather than broken.
export default function ModifyBox() {
  return (
    <section className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-500">Refine this part</h3>
        <Phase2Badge />
      </div>
      <div className="flex gap-2 opacity-60">
        <input
          type="text"
          disabled
          placeholder="e.g. make the mounting holes 6mm…"
          className="flex-1 cursor-not-allowed rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-400 placeholder:text-slate-300"
          aria-label="Refine this part (coming in Phase 2)"
        />
        <button
          type="button"
          disabled
          className="cursor-not-allowed rounded-lg bg-slate-300 px-4 py-2 text-sm font-medium text-white"
        >
          Refine
        </button>
      </div>
      <p className="mt-2 text-xs text-slate-400">
        Natural-language refinement creates a new version. Available in Phase 2.
      </p>
    </section>
  )
}
