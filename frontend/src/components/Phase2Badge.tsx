// Small shared badge that marks a non-functional Phase 2 stub so it can never
// be mistaken for a bug.
export default function Phase2Badge({ className = '' }: { className?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500 ${className}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-slate-400" />
      Coming in Phase 2
    </span>
  )
}
