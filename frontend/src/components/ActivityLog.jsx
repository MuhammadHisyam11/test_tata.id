import { fmtWhen, sourceLabel } from '../format.js'

const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

/** Tandai frasa sinyal (dari backend) di dalam teks pesan — kata utuh, sama dengan assess.text_signals. */
export function Highlighted({ text, phrases }) {
  if (!phrases?.length) return text
  const re = new RegExp(`\\b(${phrases.map(escapeRe).join('|')})\\b`, 'gi')
  return text.split(re).map((part, i) => (i % 2 ? <mark key={i}>{part}</mark> : part))
}

export default function ActivityLog({ items, flash, describe }) {
  return (
    <section className="card block">
      <h3 className="block-title">Riwayat aktivitas</h3>
      <p className="sub">Pesan dari tim dan catatan dari sistem, diurutkan menurut waktu.</p>
      <ol className="log">
        {items.map((t) => {
          const on = flash === t.ref_id
          return (
            <li key={t.ref_id} id={`ref-${t.ref_id}`} className={`log-item log-${t.kind} ${on ? 'flash' : ''}`}>
              <span className="log-when">{fmtWhen(t.ts)}</span>
              <div className="log-body">
                <span className="log-source">{sourceLabel(t)}</span>
                <p className="log-text">
                  {t.kind === 'update' ? <Highlighted text={t.text} phrases={t.hints} /> : describe(t.raw)}
                </p>
                {/* key ikut flash supaya data mentah terbuka saat buktinya diklik */}
                <details key={on ? 'open' : 'closed'} open={on}>
                  <summary>data mentah · {t.ref_id}</summary>
                  <pre>{JSON.stringify(t.raw, null, 2)}</pre>
                </details>
              </div>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
