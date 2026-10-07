const BACKEND_DOWN = 'Backend tidak dapat dihubungi. Pastikan `python manage.py runserver` berjalan di port 8000.'

async function get(path) {
  let res
  try {
    res = await fetch(`/api${path}`)
  } catch {
    throw new Error(BACKEND_DOWN)
  }
  // Proxy Vite membalas 5xx saat Django mati.
  if (res.status >= 500) throw new Error(BACKEND_DOWN)
  if (res.status === 404) throw new Error('Project tidak ditemukan.')
  if (!res.ok) throw new Error(`Gagal memuat data (HTTP ${res.status}).`)
  return res.json()
}

export const getProjects = () => get('/projects')
export const getProject = (id) => get(`/projects/${encodeURIComponent(id)}`)
