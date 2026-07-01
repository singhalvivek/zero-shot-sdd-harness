'use client'

import { useRef, useState } from 'react'
import { askQuestion, getSession, type AskEvent, type DatasetResult } from '@/lib/api'
import { UploadPanel, type LoadedDataset } from '@/components/UploadPanel'
import { ConversationThread, type Turn } from '@/components/ConversationThread'
import { AuditPanel } from '@/components/AuditPanel'
import { SessionSwitcher } from '@/components/SessionSwitcher'

type View = 'chat' | 'audit'

export default function Home() {
  const [datasets, setDatasets] = useState<LoadedDataset[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [question, setQuestion] = useState('')
  const [turns, setTurns] = useState<Turn[]>([])
  const [asking, setAsking] = useState(false)
  const [streamingStarted, setStreamingStarted] = useState(false)
  const [view, setView] = useState<View>('chat')
  const [sessionsToken, setSessionsToken] = useState(0)
  const turnCounter = useRef(0)

  const hasData = datasets.length > 0
  const canAsk = hasData && !!sessionId && !!question.trim() && !asking

  function bumpSessions() {
    setSessionsToken(t => t + 1)
  }

  function onUploaded(d: DatasetResult) {
    setSessionId(d.session_id)
    setDatasets(prev => {
      // Replace if same dataset id (defensive), else append to the session's list.
      const without = prev.filter(x => x.dataset_id !== d.dataset_id)
      return [...without, { dataset_id: d.dataset_id, df_name: d.df_name, row_count: d.row_count, columns: d.columns }]
    })
    bumpSessions()
  }

  function startNewSession() {
    setSessionId(null)
    setDatasets([])
    setTurns([])
    setQuestion('')
    setView('chat')
    turnCounter.current = 0
  }

  async function resumeSession(id: string) {
    try {
      const detail = await getSession(id)
      setSessionId(detail.session_id)
      setDatasets(
        detail.datasets.map(d => ({
          dataset_id: d.dataset_id,
          df_name: d.df_name,
          filename: d.filename,
          row_count: d.row_count,
          columns: d.columns,
        })),
      )
      // Rehydrate the conversation: pair user questions with their assistant answer.
      const rebuilt: Turn[] = []
      turnCounter.current = 0
      for (const m of detail.messages) {
        if (m.role === 'user') {
          rebuilt.push({
            id: `turn-${turnCounter.current++}`,
            question: m.content,
            answer: '',
            status: 'complete',
          })
        } else if (m.role === 'assistant' && rebuilt.length > 0) {
          rebuilt[rebuilt.length - 1].answer = m.content
        }
      }
      setTurns(rebuilt)
      setQuestion('')
      setView('chat')
    } catch {
      // Surface nothing destructive — keep current state; the switcher shows its own errors.
    }
  }

  async function ask(rawQuestion: string) {
    const q = rawQuestion.trim()
    if (!q || !sessionId || asking) return

    const turnId = `turn-${turnCounter.current++}`
    setTurns(prev => [...prev, { id: turnId, question: q, answer: '', status: 'streaming' }])
    setQuestion('')
    setAsking(true)
    setStreamingStarted(false)

    const update = (patch: Partial<Turn>) =>
      setTurns(prev => prev.map(t => (t.id === turnId ? { ...t, ...patch } : t)))

    let answer = ''
    let clarifying = false
    const onEvent = (evt: AskEvent) => {
      switch (evt.type) {
        case 'token':
          setStreamingStarted(true)
          answer += evt.text
          update({ answer })
          break
        case 'clarify':
          clarifying = true
          update({ status: 'clarifying', clarify: evt.question })
          break
        case 'suggestions':
          update({ suggestions: evt.items })
          break
        case 'usage':
          update({ usage: { prompt_tokens: evt.prompt_tokens, completion_tokens: evt.completion_tokens } })
          break
        case 'error':
          update({ status: 'error', error: evt.message })
          setQuestion(q)
          break
        case 'done':
          if (evt.status === 'needs_clarification' || clarifying) {
            update({ status: 'complete' })
          } else if (evt.status === 'failed') {
            update({ status: 'error', error: 'The agent failed. Please try again.' })
            setQuestion(q)
          } else {
            update({ status: 'complete' })
          }
          break
        default:
          break
      }
    }

    try {
      await askQuestion(sessionId, q, onEvent)
      setTurns(prev =>
        prev.map(t => (t.id === turnId && t.status === 'streaming' ? { ...t, status: 'complete' } : t)),
      )
    } catch (err) {
      update({ status: 'error', error: err instanceof Error ? err.message : 'The agent failed. Please try again.' })
      setQuestion(q)
    } finally {
      setAsking(false)
      bumpSessions()
    }
  }

  async function handleAsk(e: React.FormEvent) {
    e.preventDefault()
    if (!canAsk) return
    await ask(question)
  }

  function handleSuggestion(suggestion: string) {
    if (asking || !sessionId) return
    void ask(suggestion)
  }

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Personal Data Analysis Agent</h1>
          <p className="text-sm text-gray-500">Upload your data and ask questions in plain language.</p>
        </div>
        <SessionSwitcher
          activeSessionId={sessionId}
          onResume={resumeSession}
          onNewSession={startNewSession}
          reloadToken={sessionsToken}
        />
      </header>

      <nav className="mb-6 flex items-center gap-2 border-b border-gray-200 pb-2">
        <button
          type="button"
          data-testid="chat-tab"
          onClick={() => setView('chat')}
          className={`rounded-md px-3 py-1 text-sm font-medium transition-colors ${
            view === 'chat' ? 'bg-blue-50 text-blue-700' : 'text-gray-500 hover:bg-gray-50'
          }`}
        >
          Console
        </button>
        <button
          type="button"
          data-testid="audit-tab"
          onClick={() => setView('audit')}
          className={`rounded-md px-3 py-1 text-sm font-medium transition-colors ${
            view === 'audit' ? 'bg-blue-50 text-blue-700' : 'text-gray-500 hover:bg-gray-50'
          }`}
        >
          Audit log
        </button>
      </nav>

      {view === 'audit' ? (
        <AuditPanel sessionId={sessionId} />
      ) : (
        <div className="grid gap-6 md:grid-cols-[20rem_1fr]">
          <div className="space-y-4">
            <UploadPanel datasets={datasets} sessionId={sessionId} onUploaded={onUploaded} />
          </div>

          <div className="space-y-4">
            <ConversationThread
              turns={turns}
              streamingStarted={streamingStarted}
              onAskSuggestion={handleSuggestion}
              disabled={asking}
            />

            <form onSubmit={handleAsk} className="rounded-xl border border-gray-200 bg-white p-3 shadow-sm">
              <textarea
                data-testid="question-input"
                className="w-full resize-none rounded-lg border border-gray-300 p-3 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-50"
                rows={2}
                placeholder={hasData ? 'Ask a question about your data…' : 'Upload a file first to ask a question'}
                value={question}
                onChange={e => setQuestion(e.target.value)}
                disabled={!hasData || asking}
                onKeyDown={e => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleAsk(e)
                  }
                }}
              />
              <div className="mt-2 flex items-center justify-between">
                <span className="text-xs text-gray-400">{hasData ? 'Press Enter to ask' : 'No dataset loaded'}</span>
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
      )}
    </main>
  )
}
