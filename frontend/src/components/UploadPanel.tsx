'use client'

import { useRef, useState } from 'react'
import { uploadDataset, type DatasetResult } from '@/lib/api'
import { ComingSoonBadge } from './ComingSoon'

export function UploadPanel({
  dataset,
  sessionId,
  onUploaded,
}: {
  dataset: DatasetResult | null
  sessionId: string | null
  onUploaded: (d: DatasetResult) => void
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)

  async function handleFile(file: File) {
    setBusy(true)
    setError(null)
    try {
      const result = await uploadDataset(file, sessionId ?? undefined)
      onUploaded(result)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not read this file — is it a valid CSV?')
    } finally {
      setBusy(false)
    }
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handleFile(file)
  }

  return (
    <section data-testid="upload-panel" className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-800">Data source</h2>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">Excel</span>
          <ComingSoonBadge>Excel — coming soon</ComingSoonBadge>
        </div>
      </div>

      <div
        onClick={() => !busy && inputRef.current?.click()}
        onDragOver={e => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        role="button"
        tabIndex={0}
        data-testid="dropzone"
        className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-4 py-8 text-center transition-colors ${
          dragOver ? 'border-blue-400 bg-blue-50' : 'border-gray-300 bg-gray-50 hover:border-gray-400'
        } ${busy ? 'pointer-events-none opacity-60' : ''}`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          data-testid="file-input"
          className="hidden"
          onChange={e => {
            const file = e.target.files?.[0]
            if (file) handleFile(file)
            e.target.value = ''
          }}
        />
        {busy ? (
          <span className="text-sm text-gray-500">Profiling your file…</span>
        ) : (
          <>
            <span className="text-sm font-medium text-gray-700">Drop a CSV here, or click to select</span>
            <span className="mt-1 text-xs text-gray-400">CSV files only in Phase 1</span>
          </>
        )}
      </div>

      {error && (
        <div
          data-testid="upload-error"
          className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
        >
          {error}
        </div>
      )}

      {dataset && (
        <div data-testid="dataset-summary" className="mt-4 rounded-lg border border-green-200 bg-green-50 p-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold text-green-800">{dataset.df_name}</span>
            <span className="text-xs text-green-700">{dataset.row_count.toLocaleString()} rows</span>
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {dataset.columns.map(col => (
              <span
                key={col.name}
                className="inline-flex items-center gap-1 rounded border border-gray-200 bg-white px-2 py-0.5 text-xs text-gray-600"
              >
                <span className="font-medium">{col.name}</span>
                <span className="text-gray-400">{col.dtype}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* STUB: second-file upload (real in P3) */}
      <div className="mt-4">
        <div
          data-testid="multi-file-stub"
          aria-disabled="true"
          className="flex cursor-not-allowed items-center justify-between rounded-lg border border-dashed border-gray-300 bg-gray-50 px-3 py-2 opacity-70"
        >
          <span className="text-sm text-gray-500">Add a second file to join</span>
          <ComingSoonBadge>Multi-file — coming soon</ComingSoonBadge>
        </div>
      </div>
    </section>
  )
}
