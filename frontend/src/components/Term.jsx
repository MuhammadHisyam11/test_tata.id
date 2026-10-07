import { useEffect, useId, useState } from 'react'
import { GLOSSARY } from '../format.js'

const POP_HEIGHT = 170  // perkiraan tinggi maksimal penjelasan; dipakai untuk memilih buka ke bawah/atas

/** Istilah + tombol "?" yang membuka penjelasan singkat (bisa dengan keyboard; Escape menutup).
 *  `bare`: hanya tombol "?", untuk ditempel di belakang label yang sudah ada.
 *  Penjelasan memakai position: fixed yang dihitung dari posisi tombol dan dijepit di dalam layar,
 *  supaya tidak terpotong kartu (overflow) atau keluar layar di kolom kanan / HP. Tertutup saat scroll. */
export default function Term({ k, children, bare = false }) {
  const [pos, setPos] = useState(null)  // null = tertutup
  const id = useId()
  const [title, text] = GLOSSARY[k]

  const toggle = (e) => {
    if (pos) return setPos(null)
    const r = e.currentTarget.getBoundingClientRect()
    const width = Math.min(300, innerWidth - 32)
    const left = Math.min(Math.max(16, r.left), innerWidth - width - 16)
    setPos(r.bottom + 6 + POP_HEIGHT <= innerHeight || r.top < POP_HEIGHT
      ? { left, width, top: r.bottom + 6 }
      : { left, width, bottom: innerHeight - r.top + 6 })
  }

  useEffect(() => {
    if (!pos) return
    const close = () => setPos(null)
    window.addEventListener('scroll', close, true)
    window.addEventListener('resize', close)
    return () => {
      window.removeEventListener('scroll', close, true)
      window.removeEventListener('resize', close)
    }
  }, [pos])

  return (
    <span className="term" onKeyDown={(e) => e.key === 'Escape' && setPos(null)}>
      {!bare && (children ?? title)}
      <button type="button" className="term-btn" aria-label={`Apa itu ${title}?`} aria-expanded={!!pos}
        aria-controls={pos ? id : undefined} onClick={toggle}>?</button>
      {pos && <span id={id} role="note" className="term-pop" style={pos}>{text}</span>}
    </span>
  )
}
