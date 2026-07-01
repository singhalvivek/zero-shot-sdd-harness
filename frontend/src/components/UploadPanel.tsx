'use client'

import { useRef, useState } from 'react'
import { uploadDataset, type Column } from '@/lib/api'

const ACCEPT =
  '.csv,.xlsx,.xls,text/csv,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

/** A dataset loaded into the active session, as shown in the loaded-datasets list. */
export interface LoadedDataset {
  dataset_id: string
  df_name: string
  filename?: string
  row_count: number
  columns: Column[]
}

export function UploadPanel({
  datasets,
  sessionId,
  onUploaded,
}: {
  datasets: LoadedDataset[]
  sessionId: string | null
  onUploaded: (d: { dataset_id: string; df_name: string; row_count: number; columns: Column[]; session_id: string }) => void
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)

  const hasData = datasets.length > 0

  async function handleFile(file: File) {
    setBusy(true)
    setError(null)
    try {
      const result = await uploadDataset(file, sessionId ?? undefined)
      onUploaded(result)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not read this file — is it a valid CSV or Excel file?')
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
        <span className="text-xs text-gray-400">CSV &amp; Excel</span>
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
          accept={ACCEPT}
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
            <span className="text-sm font-medium text-gray-700">
              {hasData ? 'Add another file, or click to select' : 'Drop a file here, or click to select'}
            </span>
            <span className="mt-1 text-xs text-gray-400">CSV, XLSX or XLS</span>
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

      {hasData && (
        <div className="mt-4">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              Loaded datasets
            </h3>
            <span
              data-testid="dataset-count"
              className="inline-flex items-center rounded-full border border-gray-200 bg-gray-50 px-2 py-0.5 text-xs font-medium text-gray-600"
            >
              {datasets.length} loaded
            </span>
          </div>

          <ul data-testid="dataset-list" className="space-y-2">
            {datasets.map(d => (
              <li
                key={d.dataset_id}
                data-testid="dataset-item"
                className="rounded-lg border border-green-200 bg-green-50 p-3"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-semibold text-green-800" title={d.filename ?? d.df_name}>
                    {d.df_name}
                  </span>
                  <span className="shrink-0 text-xs text-green-700">
                    {d.row_count.toLocaleString()} rows · {d.columns.length} cols
                  </span>
                </div>
                {d.filename && d.filename !== d.df_name && (
                  <p className="mt-0.5 truncate text-xs text-green-600" title={d.filename}>
                    {d.filename}
                  </p>
                )}
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {d.columns.map(col => (
                    <span
                      key={col.name}
                      className="inline-flex items-center gap-1 rounded border border-gray-200 bg-white px-2 py-0.5 text-xs text-gray-600"
                    >
                      <span className="font-medium">{col.name}</span>
                      <span className="text-gray-400">{col.dtype}</span>
                    </span>
                  ))}
                </div>
              </li>
            ))}
          </ul>

          {datasets.length >= 2 && (
            <p data-testid="multi-file-hint" className="mt-3 rounded-lg bg-blue-50 px-3 py-2 text-xs text-blue-700">
              {datasets.length} datasets are loaded — ask questions across all of them and the agent will join
              them for you.
            </p>
          )}
        </div>
      )}
    </section>
  )
}
