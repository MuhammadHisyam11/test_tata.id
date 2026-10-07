import { useEffect, useState } from 'react'
import { getProjects } from './api.js'
import { fmtDateLong, fmtTime } from './format.js'
import Intro from './components/Intro.jsx'
import ProjectBoard from './components/ProjectBoard.jsx'
import ProjectDetail from './components/ProjectDetail.jsx'

const idFromHash = () => decodeURIComponent(window.location.hash.slice(1))

/** Sidebar: hanya menu tetap. Daftar project sengaja tidak di sini: tidak muat untuk ribuan project. */
function Sidebar({ openId }) {
  return (
    <aside className="sidebar">
      <a href="#" className="brand">
        <span className="brand-logo" aria-hidden="true">t</span>
        <span><span className="brand-name">tata.id</span><span className="brand-sub">Kondisi Project</span></span>
      </a>
      <nav className="nav" aria-label="Navigasi">
        {/* detail project ada di bawah Dashboard: tidak menambah menu, posisinya terlihat dari breadcrumb */}
        <a href="#" className="nav-link active" aria-current={!openId ? 'page' : undefined}>Dashboard</a>
      </nav>
    </aside>
  )
}

export default function App() {
  const [projects, setProjects] = useState(null)
  const [error, setError] = useState(null)
  // Navigasi lewat URL: "#" = papan, "#PRJ-002" = detail. Link bisa dibagikan, tombol back browser bekerja.
  const [openId, setOpenId] = useState(idFromHash)

  useEffect(() => {
    getProjects().then(setProjects).catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    const onHash = () => {
      setOpenId(idFromHash())
      window.scrollTo(0, 0)
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const asOf = projects?.[0]?.as_of
  const openName = projects?.find((p) => p.project_id === openId)?.project_name

  return (
    <div className="app">
      {/* tombol, bukan link "#konten": hash dipakai untuk navigasi project */}
      <button type="button" className="skip" onClick={() => document.getElementById('content').focus()}>Lewati ke konten</button>
      <Sidebar openId={openId} />
      <div className="content" id="content" tabIndex={-1}>
        <header className="topbar">
          <div className="topbar-main">
            {openId && (
              <nav className="crumbs" aria-label="Breadcrumb">
                <a className="back" href="#">Dashboard</a><span aria-hidden="true">/</span>
                <span className="crumb-current">{openName ?? openId}</span>
              </nav>
            )}
            <h1 className="topbar-title">{openId ? 'Detail project' : 'Dashboard'}</h1>
          </div>
          {asOf && <p className="data-chip"><span className="muted">Data per</span> {fmtDateLong(asOf)}, {fmtTime(asOf)} WIB</p>}
        </header>

        {!openId && <Intro />}
        {error && <p className="notice notice-error" role="alert">{error}</p>}
        {!error && !projects && <p className="notice">Memuat data…</p>}

        {projects && (openId
          ? <ProjectDetail key={openId} projectId={openId} />
          : <ProjectBoard projects={projects} />)}
      </div>
    </div>
  )
}
