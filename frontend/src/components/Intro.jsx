import { GLOSSARY, STATUS } from '../format.js'
import { Bar, StatusMark } from './ProjectBoard.jsx'

/** Pengantar "aplikasi apa ini" + panel "Cara membaca" untuk pembaca awam. */
export default function Intro() {
  return (
    <section className="card intro" aria-label="Tentang dashboard ini">
      <p className="intro-lead">
        Dashboard ini merangkum kondisi setiap project tata.id secara otomatis. Untuk setiap project, kami membandingkan{' '}
        <strong>apa yang dilaporkan penanggung jawab (PIC)</strong> dengan{' '}
        <strong>apa yang benar-benar tercatat di sistem produksi</strong>, lalu menandai project yang perlu perhatian
        beserta alasan dan buktinya.
      </p>
      <details className="howto">
        <summary>Cara membaca dashboard ini</summary>
        <div className="howto-grid">
          <div>
            <h3>Arti status</h3>
            <dl className="howto-list">
              {Object.keys(STATUS).map((level) => (
                <div key={level}><dt><StatusMark level={level} /></dt><dd>{STATUS[level].meaning}</dd></div>
              ))}
            </dl>
          </div>
          <div>
            <h3>Dua angka progress</h3>
            <p className="legend"><span className="legend-bar"><Bar pct={70} tone="ghost" /></span> <b>Laporan PIC</b>: angka yang ditulis penanggung jawab.</p>
            <p className="legend"><span className="legend-bar"><Bar pct={60} /></span> <b>Tercatat di sistem</b>: angka dari mesin atau aplikasi produksi.</p>
            <p>Jika keduanya berbeda, angka sistem lebih bisa dipercaya.</p>
            <h3>Perkiraan selesai</h3>
            <p>Dihitung dari kecepatan kerja rata-rata sejak project dimulai, bukan dari laporan PIC. Tanda ± artinya kira-kira.</p>
            <h3>Seberapa baru datanya</h3>
            <p>Bukan real-time: kondisi saat data terakhir dikumpulkan (lihat tanggal di bagian atas).</p>
          </div>
          <div>
            <h3>Istilah</h3>
            <dl className="howto-list">
              {Object.entries(GLOSSARY).map(([key, [title, text]]) => (
                <div key={key}><dt>{title}</dt><dd>{text}</dd></div>
              ))}
            </dl>
          </div>
        </div>
      </details>
    </section>
  )
}
