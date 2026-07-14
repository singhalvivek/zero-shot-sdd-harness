'use client'

import { useState } from 'react'
import dynamic from 'next/dynamic'
import {
  generateRun,
  ApiError,
  MODELS,
  DEFAULT_MODEL,
  type ModelId,
  type RunData,
} from '@/lib/api'
import CodePanel from '@/components/CodePanel'
import RepairPanel from '@/components/RepairPanel'
import CostPanel from '@/components/CostPanel'
import DownloadButtons from '@/components/DownloadButtons'
import HistoryRail from '@/components/HistoryRail'
import ModifyBox from '@/components/ModifyBox'
import StatusBanner from '@/components/StatusBanner'

// three.js touches `window`/`document`, so keep the viewer out of the static
// prerender pass and load it client-side only.
const Viewer = dynamic(() => import('@/components/Viewer'), {
  ssr: false,
  loading: () => (
    <div className="flex h-full w-full items-center justify-center rounded-xl border border-slate-700 bg-slate-900 text-sm text-slate-400">
      Loading viewer…
    </div>
  ),
})

export default function Home() {
  const [prompt, setPrompt] = useState('')
  const [model, setModel] = useState<ModelId>(DEFAULT_MODEL)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<RunData | null>(null)
  const [networkError, setNetworkError] = useState<string | null>(null)

  const completed = result?.status === 'completed' ? result : null
  const pipelineError =
    result?.status === 'failed'
      ? result.safety_violation ??
        'Could not produce valid geometry after 3 repair attempts. See the repair log below.'
      : null

  async function handleGenerate() {
    if (!prompt.trim() || loading) return
    setLoading(true)
    setNetworkError(null)
    setResult(null)
    try {
      const data = await generateRun({
        prompt: prompt.trim(),
        model_id: model,
        mode: 'generate',
      })
      setResult(data)
    } catch (err) {
      if (err instanceof ApiError) {
        setNetworkError(err.message)
      } else {
        // fetch threw (server unreachable / DNS / connection refused)
        setNetworkError('Network error — is the server running?')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="min-h-screen bg-slate-100 text-slate-900">
      {/* Header */}
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-[1600px] items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-sky-600 text-white">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 7.5l-9-5.25L3 7.5m18 0l-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9" />
              </svg>
            </span>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-slate-900">AI CAD Studio</h1>
              <p className="text-xs text-slate-500">Plain English → parametric 3D geometry</p>
            </div>
          </div>
          <span className="hidden rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-500 sm:inline">
            Phase 1 · Generate
          </span>
        </div>
      </header>

      {/* Three-column responsive layout */}
      <div className="mx-auto grid max-w-[1600px] gap-4 px-4 py-5 lg:grid-cols-[240px_minmax(0,1fr)_400px]">
        {/* Left — history rail (Phase 2 stub) */}
        <div className="order-3 lg:order-1 lg:h-[calc(100vh-140px)]">
          <HistoryRail />
        </div>

        {/* Center — prompt + viewer */}
        <div className="order-1 flex flex-col gap-4 lg:order-2">
          <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <label htmlFor="prompt" className="mb-1.5 block text-sm font-semibold text-slate-700">
              Describe your part
            </label>
            <textarea
              id="prompt"
              rows={3}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              disabled={loading}
              placeholder="e.g. a 60x40x10mm rectangular bracket with two 5mm mounting holes"
              className="w-full resize-y rounded-lg border border-slate-300 p-3 text-sm shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500 disabled:bg-slate-50"
            />
            <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center">
              <div className="flex-1">
                <label htmlFor="model" className="sr-only">
                  Model
                </label>
                <select
                  id="model"
                  value={model}
                  onChange={(e) => setModel(e.target.value as ModelId)}
                  disabled={loading}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500 disabled:bg-slate-50"
                >
                  {MODELS.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </div>
              <button
                type="button"
                onClick={handleGenerate}
                disabled={loading || !prompt.trim()}
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-sky-600 px-6 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading && (
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                )}
                {loading ? 'Generating… (~10–30s)' : 'Generate'}
              </button>
            </div>
          </section>

          <StatusBanner networkError={networkError} pipelineError={pipelineError} />

          {/* Viewer — the centerpiece */}
          <div className="h-[420px] lg:h-[calc(100vh-360px)] lg:min-h-[420px]">
            <Viewer stlUrl={completed?.stl_url ?? null} generating={loading} />
          </div>

          {/* Phase 2 stub — refine box */}
          <ModifyBox />
        </div>

        {/* Right — code / repairs / cost */}
        <div className="order-2 flex flex-col gap-4 lg:order-3 lg:h-[calc(100vh-140px)] lg:overflow-y-auto lg:pr-1">
          {completed && (
            <>
              <CostPanel tokenUsage={completed.token_usage} costUsd={completed.cost_usd} />
              <DownloadButtons
                stlUrl={completed.stl_url}
                stepUrl={completed.step_url}
                codeUrl={completed.code_url}
              />
            </>
          )}
          <CodePanel code={result?.generated_code ?? null} />
          <RepairPanel attempts={result?.repair_attempts ?? []} hasRun={result !== null} />

          {!result && !networkError && (
            <div className="rounded-xl border border-dashed border-slate-300 bg-white/50 px-4 py-8 text-center text-sm text-slate-400">
              Generate a part to see its code, repair log, tokens and cost here.
            </div>
          )}
        </div>
      </div>
    </main>
  )
}
