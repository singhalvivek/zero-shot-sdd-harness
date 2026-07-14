'use client'

import { useState } from 'react'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

interface CodePanelProps {
  code: string | null
}

// Collapsible, read-only, syntax-highlighted CadQuery source.
// Phase 1: view only. The "Edit code & re-run" toggle is a labelled Phase 2 stub.
export default function CodePanel({ code }: CodePanelProps) {
  const [open, setOpen] = useState(true)

  return (
    <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between px-4 py-3">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="flex items-center gap-2 text-sm font-semibold text-slate-800"
          aria-expanded={open}
        >
          <svg
            className={`h-4 w-4 text-slate-400 transition-transform ${open ? 'rotate-90' : ''}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>
          Generated CadQuery code
        </button>

        {/* Phase 2 stub — clearly labelled, disabled, never a bug */}
        <span
          className="inline-flex cursor-not-allowed items-center gap-1.5 rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-xs font-medium text-slate-400"
          title="Editing the code and re-running is coming in Phase 2"
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z" />
          </svg>
          Edit code
          <span className="rounded bg-slate-200 px-1 text-[10px] uppercase tracking-wide text-slate-500">
            Phase 2
          </span>
        </span>
      </div>

      {open && (
        <div className="border-t border-slate-100">
          {code ? (
            <div className="max-h-[360px] overflow-auto text-xs">
              <SyntaxHighlighter
                language="python"
                style={oneDark}
                customStyle={{ margin: 0, borderRadius: 0, background: '#282c34' }}
                showLineNumbers
                wrapLongLines
              >
                {code}
              </SyntaxHighlighter>
            </div>
          ) : (
            <p className="px-4 py-6 text-center text-sm text-slate-400">
              The generated code will appear here after you Generate a part.
            </p>
          )}
        </div>
      )}
    </section>
  )
}
