'use client'

interface DownloadButtonsProps {
  stlUrl: string | null
  stepUrl: string | null
  codeUrl: string | null
}

interface ItemProps {
  href: string | null
  label: string
  sub: string
}

function DownloadItem({ href, label, sub }: ItemProps) {
  const disabled = !href
  const base =
    'flex flex-1 flex-col items-center gap-1 rounded-lg border px-3 py-2.5 text-center transition'
  if (disabled) {
    return (
      <span className={`${base} cursor-not-allowed border-slate-200 bg-slate-50 text-slate-300`}>
        <span className="text-sm font-semibold">{label}</span>
        <span className="text-[11px]">{sub}</span>
      </span>
    )
  }
  return (
    <a
      href={href}
      download
      className={`${base} border-slate-200 bg-white text-slate-700 hover:border-sky-400 hover:bg-sky-50 hover:text-sky-700`}
    >
      <span className="text-sm font-semibold">{label}</span>
      <span className="text-[11px] text-slate-400">{sub}</span>
    </a>
  )
}

// Anchor downloads for the three exported artifacts.
export default function DownloadButtons({ stlUrl, stepUrl, codeUrl }: DownloadButtonsProps) {
  return (
    <section className="flex gap-3">
      <DownloadItem href={stlUrl} label="STL" sub="for printing" />
      <DownloadItem href={stepUrl} label="STEP" sub="for CAD" />
      <DownloadItem href={codeUrl} label="Code" sub="CadQuery .py" />
    </section>
  )
}
