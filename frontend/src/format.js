// Format & kosakata awam. Semua waktu ditampilkan dalam WIB (asumsi zona waktu data sumber).
const TZ = 'Asia/Jakarta'

const dateLong = new Intl.DateTimeFormat('id-ID', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: TZ })
const dateShort = new Intl.DateTimeFormat('id-ID', { weekday: 'short', day: 'numeric', month: 'short', timeZone: TZ })
const dayMonth = new Intl.DateTimeFormat('id-ID', { day: 'numeric', month: 'short', timeZone: TZ })
const timeFmt = new Intl.DateTimeFormat('id-ID', { hour: '2-digit', minute: '2-digit', timeZone: TZ })
// Angka memakai format yang sama dengan teks dari backend (1,234.5) agar tidak tercampur.
const numFmt = new Intl.NumberFormat('en-US', { maximumFractionDigits: 1 })

// "2026-10-10" -> Date di WIB (bukan UTC) supaya nama hari tidak bergeser.
export const parseDate = (iso) => new Date(iso.length === 10 ? `${iso}T00:00:00+07:00` : iso)

export const fmtDateLong = (iso) => dateLong.format(parseDate(iso))
export const fmtDateShort = (iso) => (iso ? dateShort.format(parseDate(iso)) : '–')
export const fmtDayMonth = (iso) => (iso ? dayMonth.format(parseDate(iso)) : '–')
export const fmtTime = (iso) => timeFmt.format(parseDate(iso))
export const fmtWhen = (iso) => (iso ? `${dayMonth.format(parseDate(iso))}, ${timeFmt.format(parseDate(iso))}` : '–')
export const fmtNum = (n) => (n == null ? '–' : numFmt.format(n))
// 1 desimal seperti angka lain: 79.5% tidak boleh tampil sebagai 80%.
export const fmtPct = (n) => (n == null ? '–' : `${numFmt.format(n)}%`)

export const STATUS = {
  HIGH: { label: 'Perlu tindakan', tone: 'red', meaning: 'Ada masalah serius yang perlu diputuskan sekarang.' },
  MEDIUM: { label: 'Pantau', tone: 'amber', meaning: 'Ada tanda risiko. Cek lagi dalam beberapa hari.' },
  LOW: { label: 'Perhatikan', tone: 'amber', meaning: 'Datanya belum cukup untuk dinilai.' },
  OK: { label: 'Aman', tone: 'green', meaning: 'Tidak ada masalah yang ditemukan.' },
}

export const PROJECT_TYPE = {
  'Archive Arrangement': 'Penataan arsip',
  'Document Digitalisation': 'Digitalisasi dokumen',
  'Data Verification': 'Verifikasi data',
  'System Integration': 'Integrasi sistem',
  'DMS Implementation': 'Implementasi aplikasi pengelolaan dokumen (DMS)',
}

// Glosarium dipakai di panel "Cara membaca" dan tooltip "?".
export const GLOSSARY = {
  pic: ['PIC', 'Penanggung jawab project di tata.id. Angka "Laporan PIC" adalah angka yang ia tulis sendiri.'],
  system: ['Tercatat di sistem', 'Angka dari mesin atau aplikasi produksi (mis. log mesin scanner, aplikasi verifikasi). Lebih bisa dipercaya daripada laporan, karena dicatat otomatis.'],
  forecast: ['Perkiraan selesai', 'Tanggal selesai jika tim terus bekerja secepat rata-rata sejak project dimulai. Bukan dari laporan PIC. Tanda ± artinya kira-kira.'],
  ml: ['Meter linear', 'Satuan panjang arsip jika berkas disusun berjajar di rak (dipakai di project penataan arsip).'],
  endpoint: ['Endpoint', 'Satu titik sambungan antara dua sistem. Project integrasi dianggap selesai jika setiap endpoint sudah dicoba di sistem milik customer.'],
  customer: ['Sistem customer', 'Sistem asli milik customer yang dipakai sehari-hari (sering disebut "production"), bukan sistem uji coba.'],
  dms: ['DMS', 'Document Management System, aplikasi untuk menyimpan dan mengelola dokumen secara digital.'],
}

export const UNIT = { ML: 'meter linear', pages: 'halaman', boxes: 'box', records: 'data', endpoints: 'endpoint', system: 'sistem' }
export const unitLabel = (u) => UNIT[u] ?? u

export const REPORTED_STATUS = { 'ON TRACK': 'sesuai rencana', COMPLETED: 'selesai' }

export function daysLeftLabel(days) {
  if (days == null) return ''
  if (days < 0) return `lewat ${-days} hari`
  if (days === 0) return 'hari ini'
  return `${days} hari lagi`
}

// ---------- sumber bukti dalam bahasa awam ----------

const SOURCE_SYSTEM = {
  scanner_production_log: 'Log mesin scanner',
  archive_production_report: 'Laporan produksi arsip',
  warehouse_entry: 'Pencatatan gudang',
  verification_application: 'Aplikasi verifikasi',
  api_monitor: 'Monitor integrasi API',
  dms_monitor: 'Monitor aplikasi DMS',
}

/** Label sumber untuk satu item riwayat (update manusia atau data sistem). */
export function sourceLabel(item) {
  if (item.kind === 'update') {
    const { source_type: type, source_name: name } = item.raw
    return type === 'PROJECT_MANAGER' ? `Pesan ${name} (PM)` : `Pesan ${name}`
  }
  return SOURCE_SYSTEM[item.raw.source_system] ?? 'Data sistem'
}

const VALUE = {
  RUNNING: 'jalan', OUT_OF_SERVICE: 'rusak', LIMITED: 'terbatas', ONLINE: 'online', COMPLETED: 'selesai',
  NOT_CONFIGURED: 'belum dikonfigurasi', VERIFIED: 'terverifikasi', PENDING_INTERNAL_CHECK: 'menunggu pengecekan',
}

const FIELD = {
  verified_quantity: 'Terverifikasi',
  pending_internal_check_quantity: 'Menunggu pengecekan internal',
  pages_processed_total: 'Total halaman diproses',
  processed_boxes: 'Box diproses',
  records_verified: 'Data terverifikasi',
  records_skipped_missing_region: 'Data dilewati (wilayah kosong)',
  developed_endpoints: 'Endpoint selesai dikembangkan',
  configured_endpoints: 'Endpoint dikonfigurasi',
  production_tested_endpoints: 'Endpoint teruji di sistem customer',
  target_endpoints: 'Target endpoint',
  connection_status: 'Koneksi ke sistem customer',  // dataset hanya punya environment=production
  last_successful_connection: 'Terakhir tersambung',
  application_status: 'Aplikasi',
  deployment_status: 'Pemasangan aplikasi',
  active_users_last_24h: 'User aktif (24 jam)',
  successful_logins_last_24h: 'Login berhasil (24 jam)',
  failed_logins_last_24h: 'Login gagal (24 jam)',
}

/** Ringkasan awam untuk satu record sistem; field yang tidak dikenal tetap ada di "data mentah". */
export function describeRecord(payload) {
  if (payload.scanners) {
    return 'Status scanner: ' + payload.scanners
      .map((s) => `${s.scanner_id.replace('SCN-', '')} ${VALUE[s.status] ?? s.status}`).join(' · ')
  }
  const unit = payload.unit ? ` ${unitLabel(payload.unit)}` : ''
  const parts = Object.entries(FIELD)
    .filter(([key]) => key in payload)
    .map(([key, label]) => {
      const v = payload[key]
      if (v === null) return `${label}: belum pernah`
      if (typeof v === 'number') return `${label}: ${fmtNum(v)}${key.startsWith('records_') || key.includes('endpoint') || key.includes('_last_24h') ? '' : unit}`
      return `${label}: ${VALUE[v] ?? v}`
    })
  // Tipe record baru tanpa kosakata awam: jangan tampil kosong, arahkan ke data mentah.
  return parts.length ? parts.join(' · ') : 'Catatan sistem (lihat data mentah).'
}
