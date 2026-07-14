'use client'

interface StatusBannerProps {
  // Fixed red banner for transport / request errors.
  networkError: string | null
  // Amber panel for a pipeline failure (HTTP 200, status:"failed").
  pipelineError: string | null
}

// Two visually-distinct problem states: red = the request itself failed;
// amber = the pipeline ran but could not produce a valid part.
export default function StatusBanner({ networkError, pipelineError }: StatusBannerProps) {
  if (networkError) {
    return (
      <div
        role="alert"
        className="flex items-start gap-3 rounded-xl border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700"
      >
        <svg className="mt-0.5 h-5 w-5 shrink-0 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
        </svg>
        <div>
          <p className="font-semibold">Request failed</p>
          <p>{networkError}</p>
        </div>
      </div>
    )
  }

  if (pipelineError) {
    return (
      <div
        role="alert"
        className="flex items-start gap-3 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800"
      >
        <svg className="mt-0.5 h-5 w-5 shrink-0 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
        </svg>
        <div>
          <p className="font-semibold">Generation did not complete</p>
          <p>{pipelineError}</p>
        </div>
      </div>
    )
  }

  return null
}
