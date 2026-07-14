'use client'

import type { TokenUsage } from '@/lib/api'

interface CostPanelProps {
  tokenUsage: TokenUsage | null
  costUsd: number | null
}

// Token usage + estimated cost for the generation.
export default function CostPanel({ tokenUsage, costUsd }: CostPanelProps) {
  if (!tokenUsage) return null

  const cost = typeof costUsd === 'number' ? costUsd : 0

  return (
    <section
      className="grid grid-cols-2 gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
      data-testid="cost-panel"
    >
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Tokens</p>
        <p className="mt-0.5 text-lg font-semibold text-slate-800" data-testid="total-tokens">
          {tokenUsage.total_tokens.toLocaleString()}
        </p>
        <p className="text-[11px] text-slate-400">
          {tokenUsage.prompt_tokens.toLocaleString()} in · {tokenUsage.completion_tokens.toLocaleString()} out
        </p>
      </div>
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Cost</p>
        <p className="mt-0.5 text-lg font-semibold text-slate-800">
          ${cost < 0.01 ? cost.toFixed(4) : cost.toFixed(2)}
        </p>
        <p className="text-[11px] text-slate-400">estimated</p>
      </div>
    </section>
  )
}
