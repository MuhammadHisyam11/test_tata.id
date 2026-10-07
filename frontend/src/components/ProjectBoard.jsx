import { daysLeftLabel, fmtDateShort, fmtDayMonth, fmtPct, REPORTED_STATUS, STATUS } from '../format.js'
import Term from './Term.jsx'

export function StatusMark({ level }) {
  const s = STATUS[level] ?? { label: level, tone: 'grey' }
  return <span className={`mark mark-${s.tone}`}>{s.label}</span>
}

export function Bar({ pct, tone = 'ink' }) {
  const width = Math.max(0, Math.min(100, pct ?? 0))
  return (
    <span className="bar" aria-hidden="true">
      <span className={`bar-fill bar-${tone}`} style={{ width: `${width}%` }} />
    </span>
  )
}

function Forecast({ p }) {
  if (!p.is_active) return <span className="muted">Selesai</span>
  if (!p.forecast_finish) return <span className="muted">tidak dapat diperkirakan</span>
  const late = p.forecast_delay_days > 0
  const stale = new Date(p.forecast_finish) < new Date(p.as_of)
  return (
    <>
      <span className={late ? 'late' : ''}>±{fmtDayMonth(p.forecast_finish)}</span>
      <span className={`sub ${late ? 'late' : ''}`}>
        {late ? `${p.forecast_delay_days} hari terlambat`
          : stale ? 'seharusnya sudah selesai'
            : p.forecast_delay_days === 0 ? 'tepat di hari deadline' : 'sebelum deadline'}
      </span>
    </>
  )
}

/** Kartu angka ringkas di atas: berapa project di tiap status. */
function Kpis({ projects }) {
  const count = (level) => projects.filter((p) => p.attention === level).length
  const cards = [
    { label: 'Total project', value: projects.length, note: `${projects.filter((p) => p.is_active).length} sedang berjalan`, tone: 'blue' },
    { label: 'Perlu tindakan', value: count('HIGH'), note: STATUS.HIGH.meaning, tone: 'red' },
    { label: 'Perlu dipantau', value: count('MEDIUM'), note: STATUS.MEDIUM.meaning, tone: 'amber' },
    ...(count('LOW') ? [{ label: 'Data belum cukup', value: count('LOW'), note: STATUS.LOW.meaning, tone: 'amber' }] : []),
    { label: 'Aman', value: count('OK'), note: STATUS.OK.meaning, tone: 'green' },
  ]
  return (
    <ul className="kpis" aria-label="Ringkasan status">
      {cards.map((c) => (
        <li key={c.label} className={`card kpi kpi-${c.tone}`}>
          <span className="kpi-label">{c.label}</span>
          <span className="kpi-value">{c.value}</span>
          <span className="kpi-note">{c.note}</span>
        </li>
      ))}
    </ul>
  )
}

/** "Perlu tindakan hari ini": yang paling penting terbaca sebelum tabel. */
function Today({ projects }) {
  const urgent = projects.filter((p) => p.is_active && p.attention === 'HIGH')
  return (
    <section className={`card today ${urgent.length ? '' : 'today-clear'}`} aria-labelledby="today-title">
      <h2 id="today-title" className="card-title">
        {urgent.length ? `Perlu tindakan hari ini · ${urgent.length} project` : 'Tidak ada project yang perlu tindakan hari ini'}
      </h2>
      {urgent.length > 0 && (
        <ul className="today-list">
          {urgent.map((p) => (
            <li key={p.project_id}>
              <a className="today-item" href={`#${p.project_id}`}>
                <span className="today-name">{p.project_name}</span>
                <span className="today-pic">Penanggung jawab: {p.pic} · {p.customer}</span>
                <span className="today-why">{p.headline}</span>
                <span className="today-go">Lihat penjelasan →</span>
              </a>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function Row({ p }) {
  return (
    <li>
      <a className="board-row" href={`#${p.project_id}`}>
        <span className="cell cell-project">
          <span className="project-name">{p.project_name}</span>
          <span className="sub">{p.pic} · {p.customer}</span>
        </span>
        <span className="cell cell-status" data-label="Status"><StatusMark level={p.attention} /></span>
        <span className="cell cell-progress" data-label="Progress">
          <span className="progress-line">
            <span className="progress-label">Laporan PIC</span><Bar pct={p.reported_pct} tone="ghost" />
            <span className="num">{fmtPct(p.reported_pct)}</span>
          </span>
          <span className="progress-line">
            <span className="progress-label">Tercatat sistem</span><Bar pct={p.observed_pct} />
            <span className="num">{fmtPct(p.observed_pct)}</span>
          </span>
        </span>
        <span className="cell cell-forecast" data-label="Perkiraan selesai"><Forecast p={p} /></span>
        <span className="cell cell-deadline" data-label="Deadline">
          {fmtDateShort(p.deadline)}
          <span className="sub">{p.is_active ? daysLeftLabel(p.days_remaining) : `dilaporkan ${REPORTED_STATUS[p.reported_status] ?? p.reported_status}`}</span>
        </span>
        <span className="cell cell-issue" data-label="Masalah utama">{p.headline || '—'}</span>
      </a>
    </li>
  )
}

function Section({ title, items }) {
  if (!items.length) return null
  return (
    <section className="card board-section">
      <h3 className="card-title">{title} <span className="count">{items.length}</span></h3>
      {/* Tombol "?" ada di header, bukan di baris: baris adalah link, dan tombol di dalam link tidak valid. */}
      <div className="board-head">
        <span>Project</span><span>Status</span>
        <span>Progress <Term k="system" bare /></span>
        <span>Perkiraan selesai <Term k="forecast" bare /></span><span>Deadline</span><span>Masalah utama</span>
      </div>
      <ul className="board">{items.map((p) => <Row key={p.project_id} p={p} />)}</ul>
    </section>
  )
}

export default function ProjectBoard({ projects }) {
  if (!projects.length) {
    return <p className="notice">Belum ada data project. Jalankan <code>python manage.py ingest</code> di backend, lalu muat ulang halaman ini.</p>
  }
  return (
    <main>
      <Kpis projects={projects} />
      <Today projects={projects} />
      <h2 className="board-title">Semua project</h2>
      <Section title="Sedang berjalan" items={projects.filter((p) => p.is_active)} />
      <Section title="Sudah selesai" items={projects.filter((p) => !p.is_active)} />
      <p className="footnote">
        Urutan: yang paling perlu tindakan di atas. Klik sebuah project untuk melihat kesimpulan, alasan, dan buktinya.
      </p>
    </main>
  )
}
