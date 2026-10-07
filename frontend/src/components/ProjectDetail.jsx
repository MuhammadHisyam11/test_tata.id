import { useEffect, useState } from 'react'
import { getProject } from '../api.js'
import {
  daysLeftLabel, describeRecord, fmtDateShort, fmtDayMonth, fmtNum, fmtPct, fmtWhen, parseDate,
  PROJECT_TYPE, REPORTED_STATUS, sourceLabel, unitLabel,
} from '../format.js'
import Term from './Term.jsx'
import { Bar, StatusMark } from './ProjectBoard.jsx'
import ActivityLog, { Highlighted } from './ActivityLog.jsx'

const SEV_TONE = { HIGH: 'red', MEDIUM: 'amber', LOW: 'amber', INFO: 'green' }

function ScheduleLine({ p, m }) {
  const points = [
    { key: 'start', label: 'Mulai', date: p.start_date, pos: 'above' },
    { key: 'today', label: 'Hari ini', date: m.as_of, pos: 'below' },
    { key: 'deadline', label: 'Deadline', date: p.deadline, pos: 'above' },
  ]
  const late = m.forecast_delay_days > 0
  if (m.forecast_finish) {
    points.push({ key: 'forecast', label: 'Perkiraan selesai', date: m.forecast_finish, pos: 'below-2', late })  // baris kedua: tak pernah menimpa label "Hari ini"
  }
  const t = points.map((pt) => parseDate(pt.date).getTime())
  const min = Math.min(...t), span = Math.max(...t) - min || 1
  const at = (i) => ((t[i] - min) / span) * 100
  const deadlineAt = at(2)
  return (
    <div className="schedule" role="img"
      aria-label={`Mulai ${fmtDayMonth(p.start_date)}, deadline ${fmtDayMonth(p.deadline)}` +
        (m.forecast_finish ? `, perkiraan selesai ${fmtDayMonth(m.forecast_finish)}` : '')}>
      <div className="schedule-track">
        <span className="schedule-plan" style={{ left: 0, width: `${deadlineAt}%` }} />
        {late && <span className="schedule-overrun" style={{ left: `${deadlineAt}%`, width: `${at(3) - deadlineAt}%` }} />}
        {points.map((pt, i) => {
          const x = at(i)
          const align = x < 12 ? 'start' : x > 88 ? 'end' : 'mid'
          return (
            <span key={pt.key} className={`schedule-point point-${pt.key} ${pt.late ? 'late' : ''}`} style={{ left: `${x}%` }}>
              <span className={`schedule-label label-${pt.pos} align-${align}`}>
                <b>{pt.label}</b> {fmtDayMonth(pt.date)}
              </span>
            </span>
          )
        })}
      </div>
    </div>
  )
}

function Progress({ p, m, stages, flash }) {
  const unit = unitLabel(p.target_unit)
  return (
    <section id={`ref-${p.project_id}`} className={`card block ${flash ? 'flash' : ''}`}>
      <h3 className="block-title">Dilaporkan vs tercatat di sistem</h3>
      <div className="compare">
        <div className="compare-item">
          <div className="compare-label"><Term k="pic">Laporan PIC</Term> ({p.pic})</div>
          <div className="compare-value">{fmtPct(p.reported_progress_pct)}</div>
          <Bar pct={p.reported_progress_pct} tone="ghost" />
          <div className="sub">{fmtNum(p.reported_actual)} dari {fmtNum(p.target)} {unit} · ditulis {fmtWhen(p.last_reported_update_at)}</div>
        </div>
        <div className="compare-item">
          <div className="compare-label"><Term k="system" /></div>
          {m.observed_actual == null ? (
            <div className="sub">Tidak ada data sistem untuk dibandingkan.</div>
          ) : (
            <>
              <div className="compare-value">{fmtPct(m.observed_pct)}</div>
              <Bar pct={m.observed_pct} />
              <div className="sub">{fmtNum(m.observed_actual)} dari {fmtNum(p.target)} {unit} · dicatat {fmtWhen(m.observed_at)}</div>
            </>
          )}
        </div>
      </div>
      {stages.length > 0 && (
        <>
        <p className="stages-title">Tahapan <Term k="endpoint">endpoint</Term></p>
        <ol className="stages" aria-label="Tahapan endpoint">
          {stages.map((s) => (
            <li key={s.label} className={s.value === 0 ? 'stage-zero' : ''}>
              <span className="stage-value">{s.value}</span>
              <span className="stage-label">{{ developed: 'selesai dikembangkan', configured: 'dikonfigurasi', 'production tested': 'teruji di sistem customer', target: 'target' }[s.label] ?? s.label}</span>
            </li>
          ))}
        </ol>
        </>
      )}
    </section>
  )
}

function Problem({ f, index, byId, project, onJump }) {
  const [open, setOpen] = useState(false)
  return (
    <li className={`problem tone-${SEV_TONE[f.severity]}`}>
      <span className="problem-no">{index}</span>
      <div className="problem-body">
        <p className="problem-text">{f.summary}</p>
        <button className="link-button" aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? 'Tutup bukti & detail' : 'Lihat bukti & detail'}
        </button>
        {open && (
          <div className="problem-detail">
            <h4>Bukti</h4>
            <ul className="evidence">
              {f.evidence.map((e) => {
                const item = byId[e.ref_id]
                const label = e.ref_type === 'master' ? `Laporan ${project.pic} di project master` : item ? sourceLabel(item) : e.ref_id
                const when = item ? fmtWhen(item.ts) : fmtWhen(project.last_reported_update_at)
                return (
                  <li key={`${e.ref_type}-${e.ref_id}`}>
                    <button className="evidence-link" onClick={() => onJump(e.ref_id)}>
                      <span className="evidence-when">{when}</span> {label}
                    </button>
                  </li>
                )
              })}
            </ul>
            <h4>Detail teknis</h4>
            <p className="tech">{f.explanation}</p>
            <p className="tech muted">Aturan <code>{f.rule}</code> · tingkat {f.severity}</p>
          </div>
        )}
      </div>
    </li>
  )
}

export default function ProjectDetail({ projectId }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [flash, setFlash] = useState(null)

  useEffect(() => {
    getProject(projectId).then(setData).catch((e) => setError(e.message))
  }, [projectId])

  // Klik bukti -> scroll ke sumbernya dan tandai sebentar (juga saat bukti yang sama diklik ulang).
  const jump = (refId) => {
    setFlash(refId)
    requestAnimationFrame(() =>
      document.getElementById(`ref-${refId}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }))
  }

  if (error) return <main className="detail"><p className="notice notice-error" role="alert">{error}</p></main>
  if (!data) return <main className="detail"><p className="notice">Memuat…</p></main>

  const { project: p, metrics: m, findings, signals, timeline, stages, conclusion } = data
  const isActive = p.reported_status !== 'COMPLETED'
  const byId = Object.fromEntries(timeline.map((t) => [t.ref_id, t]))
  const problems = findings.filter((f) => f.severity !== 'INFO')
  const notes = findings.filter((f) => f.severity === 'INFO')
  const followUps = findings.filter((f) => f.follow_up && f.severity !== 'INFO')
  const verifies = findings.filter((f) => f.verify)

  return (
    <main className="detail">
      <header className="card detail-head">
        <p className="eyebrow">{p.customer} · {PROJECT_TYPE[p.project_type] ?? p.project_type}</p>
        <h2 className="detail-title">{p.project_name}</h2>
        <div className="detail-meta">
          <StatusMark level={m.attention} />
          <span>Penanggung jawab (PIC) <b>{p.pic}</b></span>
          <span>Deadline <b>{fmtDateShort(p.deadline)}</b>{isActive && ` (${daysLeftLabel(m.days_remaining)})`}</span>
          <span>Dilaporkan <b>{REPORTED_STATUS[p.reported_status] ?? p.reported_status}</b></span>
        </div>
      </header>

      <section className="card conclusion" aria-labelledby="conclusion-title">
        <h3 id="conclusion-title" className="block-title">Kesimpulan</h3>
        <p className="conclusion-text">{conclusion.text}</p>
        {conclusion.first_step && (
          <p className="first-step"><span className="first-step-label">Langkah pertama</span>{conclusion.first_step}</p>
        )}
      </section>

      <div className="detail-grid">
      <section className="card block">
        <h3 className="block-title">Jadwal & <Term k="forecast">perkiraan selesai</Term></h3>
        <ScheduleLine p={p} m={m} />
        <p className="schedule-note">
          {!isActive ? 'Project sudah dinyatakan selesai.'
            : !m.forecast_finish ? 'Perkiraan tanggal selesai tidak dapat dihitung: tidak ada data kecepatan kerja untuk project jenis ini.'
              : m.forecast_delay_days > 0
                ? <>Jika kecepatan kerja seperti sejauh ini, project selesai sekitar <b className="late">{fmtDayMonth(m.forecast_finish)}</b> — <b className="late">{m.forecast_delay_days} hari setelah deadline</b>.</>
                : new Date(m.forecast_finish) < new Date(m.as_of)
                  ? <>Menurut kecepatan sebelumnya, project ini <b>seharusnya sudah selesai sekitar {fmtDayMonth(m.forecast_finish)}</b>, tetapi belum ada laporan terbaru.</>
                  : <>Jika kecepatan kerja seperti sejauh ini, project selesai sekitar <b>{fmtDayMonth(m.forecast_finish)}</b>, {m.forecast_delay_days === 0 ? 'tepat di hari deadline' : 'sebelum deadline'}.</>}
        </p>
      </section>

      <Progress p={p} m={m} stages={stages} flash={flash === p.project_id} />
      </div>

      <section className="card block">
        <h3 className="block-title">{problems.length ? `Masalah yang ditemukan · ${problems.length}` : 'Tidak ada masalah'}</h3>
        <ol className="problems">
          {[...problems, ...notes].map((f, i) => (
            <Problem key={`${f.rule}-${i}`} f={f} index={f.severity === 'INFO' ? '·' : i + 1} byId={byId} project={p} onJump={jump} />
          ))}
        </ol>
      </section>

      {(followUps.length > 0 || verifies.length > 0) && (
        <section className="card block actions">
          <div>
            <h3 className="block-title">Yang perlu dilakukan</h3>
            <ul className="checklist">{followUps.map((f, i) => <li key={`${f.rule}-${i}`}>{f.follow_up}</li>)}</ul>
          </div>
          <div>
            <h3 className="block-title">Perlu dikonfirmasi</h3>
            <ul className="checklist">{verifies.map((f, i) => <li key={`${f.rule}-${i}`}>{f.verify}</li>)}</ul>
          </div>
        </section>
      )}

      {signals.length > 0 && (
        <section className="card block">
          <h3 className="block-title">Pesan yang perlu dibaca</h3>
          <p className="sub">Pesan yang menyebut kendala (hold, error, menunggu, …). Hanya penanda untuk dibaca — tidak memengaruhi status.</p>
          <ul className="signals">
            {signals.map((s) => (
              <li key={s.update_id}>
                <button className="evidence-link" onClick={() => jump(s.update_id)}>
                  <span className="evidence-when">{fmtWhen(byId[s.update_id].ts)}</span> {sourceLabel(byId[s.update_id])}
                </button>
                <p><Highlighted text={s.text} phrases={s.phrases} /></p>
              </li>
            ))}
          </ul>
        </section>
      )}

      <ActivityLog items={timeline} flash={flash} describe={describeRecord} />
    </main>
  )
}
