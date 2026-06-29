// A clearly-labelled, non-functional stub. Visible badge + disabled styling so it is
// never mistaken for a bug.

export function ComingSoonBadge({ children = 'Coming soon' }: { children?: React.ReactNode }) {
  return (
    <span
      data-testid="coming-soon-badge"
      className="inline-flex items-center rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700"
    >
      {children}
    </span>
  )
}

export function StubCard({
  label,
  description,
  badge = 'Coming soon',
}: {
  label: string
  description: string
  badge?: string
}) {
  return (
    <div
      data-testid="stub-card"
      aria-disabled="true"
      className="cursor-not-allowed select-none rounded-lg border border-dashed border-gray-300 bg-gray-50 p-3 opacity-70"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium text-gray-600">{label}</span>
        <ComingSoonBadge>{badge}</ComingSoonBadge>
      </div>
      <p className="mt-1 text-xs text-gray-400">{description}</p>
    </div>
  )
}
