'use client'

import { useRef, useState } from 'react'
import { askQuestion, type AskEvent, type DatasetResult } from '@/lib/api'
import { UploadPanel } from '@/components/UploadPanel'
import { ConversationThread, type Turn } from '@/components/ConversationThread'
import { ComingSoonBadge, StubCard } from '@/components/ComingSoon'

export default function Home() {
  const [dataset, setDataset] = useState<DatasetResult | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [question, setQuestion] = useState('')
  const [turns, setTurns] = useState<Turn[]>([])
  const [asking, setAsking] = useState(false)
  const [streamingStarted, setStreamingStarted] = useState(false)
  const turnCounter = useRef(0)

  const canAsk = !!dataset && !!sessionId && !!question.trim() && !asking

  function onUploaded(d: DatasetResult) {
    setDataset(d)
    setSessionId(d.session_id)
  }

  async function handleAsk(e: React.FormEvent) {
    e.preventDefault()
    if (!canAsk || !sessionId) return

    const q = question.trim()
    const turnId = `turn-${turnCounter.current++}`
    setTurns(prev => [...prev, { id: turnId, question: q, answer: '', status: 'streaming' }])
    setQuestion('')
    setAsking(true)
    setStreamingStarted(false)

    const update = (patch: Partial<Turn>) =>
      setTurns(prev => prev.map(t => (t.id === turnId ? { ...t, ...patch } : t)))

    let answer = ''
    const onEvent = (evt: AskEvent) => {
      switch (evt.type) {
        case 'token':
          setStreamingStarted(true)
          answer += evt.text
          update({ answer })
          break
        case 'error':
          update({ status: 'error', error: evt.message })
          // keep the question editable to retry
          setQuestion(q)
          break
        case 'done':
          update({ status: 'complete' })
          break
        // usage/clarify/suggestions are received but their display is a P2 stub
        default:
          break
      }
    }

    try {
      await askQuestion(sessionId, q, onEvent)
      // ensure terminal state if the stream closed without an explicit done/error
      setTurns(prev =>
        prev.map(t => (t.id === turnId && t.status === 'streaming' ? { ...t, status: 'complete' } : t)),
      )
    } catch (err) {
      update({ status: 'error', error: err instanceof Error ? err.message : 'The agent failed. Please try again.' })
      setQuestion(q)
    } finally {
      setAsking(false)
    }
  }

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Personal Data Analysis Agent</h1>
          <p className="text-sm text-gray-500">Upload your data and ask questions in plain language.</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">Session</span>
          <ComingSoonBadge>Switcher — coming soon</ComingSoonBadge>
        </div>
      </header>

      {/* Top-level P2 stub tabs: audit log */}
      <nav className="mb-6 flex items-center gap-2 border-b border-gray-200 pb-2">
        <span className="rounded-md bg-blue-50 px-3 py-1 text-sm font-medium text-blue-700">Console</span>
        <button
          type="button"
          disabled
          data-testid="audit-tab-stub"
          aria-disabled="true"
          className="flex cursor-not-allowed items-center gap-2 rounded-md px-3 py-1 text-sm text-gray-400 opacity-70"
        >
          Audit log
          <ComingSoonBadge>Coming soon</ComingSoonBadge>
        </button>
      </nav>

      <div className="grid gap-6 md:grid-cols-[20rem_1fr]">
        {/* Left: data source */}
        <div className="space-y-4">
          <UploadPanel dataset={dataset} sessionId={sessionId} onUploaded={onUploaded} />
        </div>

        {/* Right: conversation */}
        <div className="space-y-4">
          <ConversationThread turns={turns} streamingStarted={streamingStarted} />

          {/* STUB: clarifying-question area (real in P2) */}
          <StubCard
            label="Clarifying questions"
            description="When your question is ambiguous, the agent will ask for clarification here."
            badge="P2 — coming soon"
          />

          <form onSubmit={handleAsk} className="rounded-xl border border-gray-200 bg-white p-3 shadow-sm">
            <textarea
              data-testid="question-input"
              className="w-full resize-none rounded-lg border border-gray-300 p-3 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-50"
              rows={2}
              placeholder={dataset ? 'Ask a question about your data…' : 'Upload a CSV first to ask a question'}
              value={question}
              onChange={e => setQuestion(e.target.value)}
              disabled={!dataset || asking}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleAsk(e)
                }
              }}
            />
            <div className="mt-2 flex items-center justify-between">
              <span className="text-xs text-gray-400">
                {dataset ? 'Press Enter to ask' : 'No dataset loaded'}
              </span>
              <button
                type="submit"
                data-testid="ask-button"
                disabled={!canAsk}
                className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {asking ? 'Asking…' : 'Ask'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </main>
  )
}
