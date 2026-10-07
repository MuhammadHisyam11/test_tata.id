# Project Reality Check

> tata.id Builder Technical Challenge — *"What Is Actually Happening?"*

Prototype untuk management: menampilkan semua project, menandai project yang perlu perhatian, menjelaskan **kenapa** dengan angka, dan menunjukkan **evidence** (update / record sistem / master) yang mendasari setiap kesimpulan — supaya management tidak perlu bertanya satu-satu ke setiap PIC.

Dokumen perencanaan: [PRD](docs/PRD.md) · [Tech Spec](docs/TECH_SPEC.md) · [Implementation Plan](docs/IMPLEMENTATION_PLAN.md) · [AI Usage](AI_USAGE.md)

---

## 1. Overview

Data assessment berasal dari tiga sumber yang sering tidak konsisten: project master (laporan PIC), update dari berbagai pihak, dan snapshot production system. Aplikasi ini:

1. **Mengimpor** ketiga file apa adanya ke PostgreSQL (`manage.py ingest`).
2. **Menghitung** metrik per project — progress menurut sistem, laju nyata vs laju yang dibutuhkan sampai deadline — lalu menjalankan **14 rule** deterministik yang menghasilkan *findings* (severity, penjelasan berangka, hal yang perlu diverifikasi, saran follow-up, evidence).
3. **Menyajikan** hasilnya lewat API JSON dan UI React berbahasa awam:
   - **Untuk orang awam:** pengantar "aplikasi apa ini" di atas halaman, panel *Cara membaca* (arti status, dua angka progress, cara hitung perkiraan, glosarium istilah), dan tombol "?" di label penting.
   - **Perlu tindakan hari ini** — di atas papan: project yang perlu diputuskan sekarang, masing-masing dengan alasan satu kalimat.
   - **Papan status** — satu baris per project: status (*Perlu tindakan / Pantau / Aman*), progress *laporan PIC vs tercatat di sistem*, **perkiraan tanggal selesai** dari kecepatan kerja nyata, deadline, dan masalah utama dalam satu kalimat.
   - **Halaman detail** — dibuka dengan **Kesimpulan** (paragraf awam + *Langkah pertama*), lalu garis waktu jadwal (mulai → hari ini → deadline → perkiraan selesai), dilaporkan vs sistem, daftar masalah bernomor dengan tombol *"Lihat bukti & detail"* (bukti bisa diklik ke riwayat aktivitas; istilah teknis disembunyikan di sini), yang perlu dilakukan & dikonfirmasi, pesan yang perlu dibaca, dan riwayat aktivitas.
   - Tampilan dashboard: sidebar navigasi, kartu KPI per status, tabel project, dan detail berbasis kartu.
   - Responsive: desktop, tablet, dan HP (≥ 400px). Font Plus Jakarta Sans dibundel lokal, kontras warna memenuhi WCAG AA, bisa dioperasikan dengan keyboard.

Hasil pada dataset (as of 2026-10-06 17:00 WIB):

| Project | Status dilaporkan | Tingkat perhatian | Inti temuan |
|---|---|---|---|
| PRJ-005 Integrasi API Epsilon | ON TRACK 90% | **HIGH** | 0 endpoint teruji di production, koneksi `NOT_CONFIGURED`, deadline 7 hari lagi |
| PRJ-002 Digitalisasi Arsip Beta | ON TRACK 76% | **HIGH** | Butuh 6,551 hal/hari, laju nyata 3,355; bahkan kapasitas klaim 4,500 tidak cukup; Scanner B terbatas |
| PRJ-001 Penataan Arsip Alpha | ON TRACK 79.5% | MEDIUM | 318 ML dilaporkan = 301.5 verified + 16.5 masih pending; diperkirakan selesai 2 hari setelah deadline |
| PRJ-003 Penataan Arsip Gamma | ON TRACK 94% | MEDIUM | 1,840/2,000 = 92% (bukan 94%); tidak ada informasi baru 6 hari |
| PRJ-004 Verifikasi Data Delta | ON TRACK 52% | MEDIUM | 45,000/100,000 = 45% (bukan 52%); laju kurang (rasio 1.40); 3,200 record dilewati |
| PRJ-006 Implementasi DMS Zeta | COMPLETED | OK | Sistem online, 14 user aktif, 1/22 login gagal |

## 2. How to Run

Prasyarat: lihat [§3 Requirements](#3-requirements). Semua command dijalankan dari root repo.

### a. Database (sekali saja)

```bash
sudo -u postgres psql -c "CREATE ROLE tata LOGIN PASSWORD 'tata' CREATEDB;" -c "CREATE DATABASE tata OWNER tata;"
```

`CREATEDB` diperlukan karena test runner Django membuat database `test_tata` sendiri. Kredensial `tata/tata` hanya untuk local dev.

### b. Backend — terminal 1

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # wajib di setiap terminal baru
pip install -r requirements.txt
python manage.py migrate
python manage.py ingest            # import data/ + jalankan assessment, mencetak ringkasan
python manage.py runserver         # http://127.0.0.1:8000
```

`ingest` aman dijalankan berulang (hapus & muat ulang dalam satu transaksi). Contoh output:

```
Ingest OK (as_of 2026-10-06 17:00): 6 projects, 23 updates, 12 production records
PROJECT  ATTENTION  PACE  FINDINGS
PRJ-005  HIGH          -  REPORTED_VS_OBSERVED[H], ENV_NOT_READY[H], DEADLINE_IMMINENT_BLOCKED[H], STATUS_CONTRADICTION[H], SCOPE_GAP[M]
PRJ-002  HIGH       1.95  PACE_RISK[H], STATUS_CONTRADICTION[H], REPORTED_VS_OBSERVED[M], EQUIPMENT_DEGRADED[M]
...
```

### c. Frontend — terminal 2

```bash
cd frontend
npm ci
npm run dev                        # http://localhost:5173  ← buka ini
```

Vite meneruskan `/api/*` ke Django di port 8000, jadi kedua server harus berjalan.

### d. Test

```bash
cd backend && source .venv/bin/activate
python manage.py test monitor      # 49 test: unit rule engine + ingest dataset asli + API + bahasa awam
cd ../frontend && npm run build    # smoke check frontend
```

### e. Opsional

- **API langsung:** `http://127.0.0.1:8000/api/projects`, `http://127.0.0.1:8000/api/projects/PRJ-002`
- **Django Admin (read-only)** untuk menelusuri raw data: `python manage.py createsuperuser`, lalu buka `http://127.0.0.1:8000/admin/`.
- **Environment variables:** semuanya opsional dengan default local dev — lihat [`.env.example`](.env.example). Untuk memakainya: `cp .env.example .env`, ubah nilainya, lalu `set -a; . ./.env; set +a` sebelum menjalankan `manage.py`.

### Troubleshooting

| Gejala | Penyebab & solusi |
|---|---|
| `ModuleNotFoundError: No module named 'django'` | venv belum aktif → `source backend/.venv/bin/activate` (atau `backend/.venv/bin/python manage.py ...`) |
| `connection refused` / `password authentication failed` | Postgres belum jalan atau role `tata` belum dibuat → langkah 2a |
| UI menampilkan "Backend tidak dapat dihubungi" | `runserver` belum jalan di port 8000 |
| UI kosong tanpa project | `python manage.py ingest` belum dijalankan |

## 3. Requirements

| Komponen | Versi |
|---|---|
| Python | ≥ 3.12 (dikembangkan di 3.14) |
| PostgreSQL | ≥ 14 (dikembangkan di 18.6) |
| Node.js | ≥ 20.19, disarankan 22 LTS (dikembangkan di 22.23) |
| Backend deps | `Django 6.1`, `psycopg 3` — [`backend/requirements.txt`](backend/requirements.txt) |
| Frontend deps | `react 19`, `vite 8` — [`frontend/package.json`](frontend/package.json) + lockfile |

Tidak perlu Docker atau API key.

## 4. Architecture

```
data/*.csv, *.json  (salinan file assessment, tidak diubah)
      │  python manage.py ingest   — transaction.atomic: hapus semua → load ulang
      ▼
RAW LAYER (PostgreSQL)      Project · ProjectUpdate · ProductionRecord(payload jsonb)
      │  services.run_assessment() → assess.py  (pure Python, tanpa Django)
      ▼
DERIVED LAYER               ProjectMetrics · Finding(evidence jsonb)
      │  views.py — 2 endpoint GET, JsonResponse
      ▼
/api/projects, /api/projects/<id>  ──(Vite proxy)──▶  React UI :5173
```

| Path | Isi |
|---|---|
| `backend/monitor/assess.py` | **Inti logika**: threshold, `compute_metrics`, 14 rule, `text_signals`, kalimat awam, perkiraan selesai. Tidak meng-import Django → bisa dites & dijelaskan terpisah. |
| `backend/monitor/services.py` | Jembatan ORM ↔ `assess.py`: load raw, konversi waktu ke WIB, simpan derived, cetak ringkasan. |
| `backend/monitor/management/commands/ingest.py` | Import CSV/JSON → raw layer. |
| `backend/monitor/models.py` | Raw + derived models. |
| `backend/monitor/views.py`, `urls.py` | API read-only. |
| `backend/monitor/tests/` | `test_assess.py` (unit, tanpa DB), `test_api.py` (ingest dataset asli + API), `test_fuzz.py` (500 project acak). |
| `frontend/src/` | `App.jsx` (sidebar + navigasi `#hash`), `components/{Intro,Term,ProjectBoard,ProjectDetail,ActivityLog}.jsx`, `api.js`, `format.js` (kosakata awam), `styles.css`. |

## 5. Data Model / Data Handling

**Raw layer — 1:1 dengan sumber, tidak pernah "dibersihkan":**

| Model | Sumber | Catatan |
|---|---|---|
| `Project` | `02_Project_Master.csv` | Satu row per project. |
| `ProjectUpdate` | `03_Project_Updates.csv` | `project_id` sengaja **bukan FK**: update yang merujuk project tak dikenal tetap disimpan + warning saat ingest. |
| `ProductionRecord` | `04_Production_Data.json` | Kolom umum + `payload` (record JSON asli lengkap, `jsonb`). 8 `record_type` dengan field berbeda tidak dipecah ke 8 tabel. |

**Derived layer — dihapus & dihitung ulang setiap ingest:**

| Model | Isi |
|---|---|
| `ProjectMetrics` | `as_of`, `computed_pct`, `observed_actual/at/pct`, `observed_source_id`, `historical_rate`, `required_rate`, `pace_ratio`, `stated_capacity`, `forecast_finish`, `forecast_delay_days`, `days_remaining`, `last_activity_at`, `attention`. |
| `Finding` | `rule`, `severity` (HIGH/MEDIUM/LOW/INFO), `category`, `summary` (satu kalimat awam), `explanation` (detail teknis), `verify`, `follow_up`, `evidence` = `[{ref_type: master|update|production, ref_id}]`. |

**Transformasi saat ingest** (file sumber tidak diubah; `data/` identik dengan file asli, diverifikasi dengan `sha256sum`):
- Nilai CSV kosong → `NULL`; angka → `float`.
- Timestamp tanpa zona waktu → di-*localize* ke **Asia/Jakarta** (`make_aware`).
- `generated_at` di production data → `as_of` (titik "hari ini" untuk semua perhitungan).

**Mapping "progress menurut sistem"** (target_unit → field production record terbaru):
`ML → verified_quantity` (hanya VERIFIED) · `pages → pages_processed_total` · `boxes → processed_boxes` · `records → records_verified` · `endpoints → production_tested_endpoints`.

**Rule** (detail & threshold di [Tech Spec §6](docs/TECH_SPEC.md#6-rule-engine)):
`REPORTED_VS_OBSERVED`, `PCT_INCONSISTENT`, `PACE_RISK`, `ENV_NOT_READY`, `SCOPE_GAP`, `EQUIPMENT_DEGRADED`, `DATA_QUALITY_SKIP`, `STALE_REPORT`, `OVERDUE`, `POST_GO_LIVE_HEALTH`, `COMPLETION_NOT_SUPPORTED` (dilaporkan selesai padahal data sistem jauh di bawah target), `INSUFFICIENT_DATA`, dan meta-rule `DEADLINE_IMMINENT_BLOCKED`, `STATUS_CONTRADICTION`. Tingkat perhatian project = severity tertinggi dari findings-nya.

## 6. Key Engineering Decisions

1. **Rule deterministik, bukan LLM.** Kesimpulan yang dipakai untuk keputusan harus bisa diaudit, direproduksi, dan dijalankan offline. Setiap finding menyebut angka dan sumbernya. LLM lebih cocok nanti untuk *mengekstrak* sinyal dari teks bebas, tetap dengan kutipan sumber.
2. **"Dilaporkan" dan "menurut sistem" ditampilkan berdampingan, bukan digabung.** Selisihnya justru informasi utama. Jika angka master lebih baru dari snapshot sistem, selisih diberi label "belum terverifikasi sistem", bukan "salah".
3. **Evidence-first.** Tidak ada finding tanpa pointer ke record sumber; test memastikan setiap `ref_id` ada di raw layer dan bisa ditemukan di timeline UI.
4. **Raw dan derived dipisah.** Raw = apa yang dikatakan sumber; derived = interpretasi yang selalu bisa dibangun ulang ketika rule berubah.
5. **`assess.py` bebas Django.** Logika inti dites tanpa database (31 unit test + fuzz test 500 project) dan bisa dibaca tanpa memahami framework.
6. **Laju dihitung terhadap laju historis, bukan kapasitas yang diklaim PM.** Klaim kapasitas (PRJ-002: 4,500 hal/hari) hanya dipakai sebagai skenario terbaik: jika bahkan klaim itu tidak cukup → HIGH.
7. **Sinyal teks tidak memengaruhi tingkat perhatian.** Pencocokan frasa ("hold", "error", "dicek kembali", …) membantu manusia menemukan update penting (mis. hold klasifikasi di PRJ-001) tanpa membuat sistem "menyimpulkan" dari teks bebas.
8. **Stack: Django + PostgreSQL + Vite/React** — ORM, migration, management command, admin, dan test runner tersedia tanpa dependency tambahan; tanpa DRF karena hanya ada 2 endpoint GET.

## 7. Assumptions

- **"Hari ini" = `generated_at` production data = 2026-10-06 17:00 WIB.** Semua timestamp sumber dianggap WIB.
- **Laju dihitung dari timestamp snapshot sistem**, bukan "hari ini", karena tiap sumber diperbarui pada waktu berbeda (PRJ-003 terakhir 09-30).
- **Deadline inklusif** (pekerjaan boleh sampai 23:59:59 di tanggal deadline) dan **hari kalender**, bukan hari kerja — kalender kerja tidak tersedia. Deadline PRJ-002 jatuh hari Sabtu; jika tim tidak bekerja akhir pekan, risikonya lebih besar dari yang dihitung.
- **Progress linier terhadap waktu** untuk project berbasis kuantitas (ML, pages, boxes, records); tidak dipakai untuk integrasi/DMS.
- **Angka production system lebih dipercaya** daripada master untuk kuantitas; untuk PRJ-001 hanya `VERIFIED` yang dihitung selesai.
- **Endpoint "selesai" = sudah teruji di production.** Tahap developed/configured tetap ditampilkan.
- **Record sistem yang mencantumkan unit berbeda dari target project diabaikan** (tidak dibandingkan). Jika tidak ada data lain, project ditandai "tidak ada data sistem untuk dibandingkan".
- **Threshold adalah pilihan saya**, belum dikalibrasi dengan management: selisih progress > 1 poin; selisih reported vs observed > 1% target (HIGH > 5%); rasio laju > 1.0, yaitu perkiraan selesai lewat deadline (HIGH > 1.5 atau melebihi kapasitas klaim); tidak ada informasi > 3 hari = basi; blocker dengan deadline ≤ 7 hari = HIGH.

## 8. Limitations

- **Threshold belum dikalibrasi.** Batas MEDIUM untuk keterlambatan sengaja 1.0, jadi setiap perkiraan selesai yang lewat deadline menjadi temuan dan status selalu konsisten dengan kolom "N hari terlambat". Batas HIGH (1.5) adalah pilihan saya. Akibatnya, PRJ-004 yang diperkirakan terlambat **13 hari** hanya MEDIUM (rasio 1.40), sama dengan PRJ-001 yang terlambat 2 hari. Yang lebih tepat mungkin batas berbasis jumlah hari terlambat, tetapi itu perlu dikalibrasi bersama management.
- **Evidence update dipilih berdasarkan kata kunci** (mis. update yang menyebut "scanner") sehingga bisa ikut menyertakan update yang kurang relevan (UPD-008 di temuan scanner). Kata kunci tidak pernah menentukan severity.
- **Ekstraksi kapasitas & frasa sinyal sengaja sempit** (regex `… halaman per hari`, 7 frasa). Cukup untuk dataset ini, tidak untuk bahasa bebas yang lebih bervariasi.
- **Satu snapshot, tanpa riwayat.** Ingest menimpa assessment sebelumnya, jadi tren (membaik/memburuk) belum terlihat.
- **Read-only, tanpa autentikasi/RBAC**, tanpa input koreksi atau status tindak lanjut dari management.
- **Belum siap production:** tanpa HTTPS/HSTS/secure cookie (sisa 4 peringatan `manage.py check --deploy`). Satu-satunya pengaman yang dipasang: app menolak start dengan `DJANGO_DEBUG=0` jika `DJANGO_SECRET_KEY` belum diatur.
- **Mode development saja:** dua proses (`runserver` + Vite dev server); belum ada build produksi yang disajikan Django.
- **Frontend tanpa unit test**; diverifikasi dengan `npm run build` dan checklist manual (dijalankan via headless browser selama pengembangan, script-nya tidak disertakan).
- **Kosakata awam di frontend di-hardcode** (`format.js`: nama sumber, label field record, glosarium, terjemahan jenis project). Field atau sistem sumber baru akan tampil apa adanya sampai kosakatanya ditambahkan.
- **Belum ada paginasi.** `GET /api/projects` mengirim semua project sekaligus (query tetap 2, tanpa N+1), dan tabel menampilkan semuanya. Cukup untuk puluhan sampai ratusan project. Untuk ribuan project perlu paginasi + filter/pencarian di API dan tabel. Daftar project sengaja tidak ditaruh di sidebar karena alasan yang sama.
- **Perkiraan tanggal selesai mengasumsikan kecepatan konstan** (rata-rata sejak mulai). Belum memperhitungkan percepatan/perlambatan terbaru, hari kerja, atau kapasitas yang berubah (mis. scanner rusak).

## 9. What I Would Do Next

1. **Riwayat assessment harian + status tindak lanjut** (siapa, kapan, hasil) agar tren dan akuntabilitas terlihat.
2. **Kontrak data per `project_type`** sebagai konfigurasi (mapping observed, definisi selesai, kalender kerja) menggantikan mapping di kode.
3. **Kalibrasi threshold** bersama management + feedback "flag ini tepat/tidak".
4. **Ekstraksi sinyal dari teks dengan LLM** (dengan kutipan sumber) menggantikan daftar frasa.
5. **Build produksi** (Django menyajikan `frontend/dist`) + autentikasi.

## 10. Final Question

> *Jika besok sistem ini digunakan oleh management untuk memonitor 100 project dari berbagai jenis pekerjaan, dan management mulai bergantung pada informasi di dalam sistem untuk mengambil keputusan, apa tiga hal pertama yang akan Anda ubah atau kembangkan lebih lanjut, dan mengapa?*

**1. Data masuk otomatis, dengan kontrak per jenis project.** Saat ini data dibaca dari file, dan definisi "angka menurut sistem" per unit tertulis di kode. Untuk 100 project lintas jenis pekerjaan, ingest harus terjadwal langsung dari production system, dan definisi selesai, unit, serta kalender kerja per jenis project menjadi konfigurasi yang divalidasi saat data masuk. Data yang tidak memenuhi kontrak ditandai, bukan dilewati diam-diam. Alasannya: kesimpulan hanya sebaik data yang masuk, dan satu kesalahan mapping akan menyesatkan banyak keputusan sekaligus.

**2. Riwayat dan jejak audit.** Sekarang hasil assessment ditimpa setiap ingest. Jika management mengambil keputusan dari sistem, mereka perlu bisa melihat apa yang ditunjukkan sistem pada hari keputusan dibuat, tren tiap project (membaik atau memburuk), versi rule yang dipakai, dan siapa yang menindaklanjuti apa. Ini juga titik masuk alami untuk kontrol akses per peran.

**3. Kalibrasi threshold berbasis umpan balik.** Batas-batas di sistem ini adalah pilihan saya. PRJ-004 menunjukkan risikonya: diperkirakan terlambat 13 hari, tetapi hanya berstatus "Pantau" karena rasio kecepatannya 1.40, di bawah batas 1.5 yang belum pernah divalidasi. Saya akan menambahkan penilaian "flag ini tepat/tidak" dan status tindak lanjut, lalu menetapkan threshold per jenis project bersama management berdasarkan data tersebut. Tanpa ini, 100 project akan menghasilkan terlalu banyak alarm sehingga diabaikan, atau terlalu sedikit sehingga masalah nyata lolos.

## Status & Waktu Kerja

Semua fase di [Implementation Plan](docs/IMPLEMENTATION_PLAN.md) selesai: ingest, rule engine, 49 test backend, API, UI, dokumentasi. Fase 7–9 (bahasa awam, UX orang awam, tampilan dashboard) tidak ada di rencana awal; ditambahkan setelah review UI.

**Waktu kerja aktual: ±3 jam 45 menit**, dari total rentang ±6 jam (Rabu, 7 Oktober 2026, 09.19–15.14 WIB). Pengerjaan dilakukan di sela pekerjaan lain.

| Waktu (WIB) | Durasi aktif | Pekerjaan |
|---|---|---|
| 09.19–10.14 | ±45 menit | Membaca requirements; menyusun PRD, Tech Spec, Implementation Plan; memilih stack; mengaudit dokumen; mengecek aturan penggunaan AI |
| 10.14–10.55 | ±40 menit | **Inti, Fase 0–6:** setup, ingest, rule engine, test, API, UI awal, dokumentasi |
| 11.06–12.22 | ±1 jam 15 menit | Fase 7 (bahasa awam + perkiraan selesai), audit putaran 1–4, Fase 8 (UX orang awam) |
| 13.47–14.25 | ±40 menit | Fase 9 (tampilan dashboard), audit, penyesuaian layout |
| 14.51–15.14 | ±25 menit | Cek ulang terhadap requirements, mengisi AI_USAGE.md dan README |

**Cara menghitung:** waktu diambil dari catatan sesi AI tools (jam setiap pesan dan setiap langkah kerja). Jeda lebih dari 10 menit tanpa aktivitas dihitung sebagai tidak bekerja, karena saat itu saya mengerjakan hal lain. Jeda terbesar adalah 12.22–13.47. Angka ini termasuk waktu menunggu AI menulis kode dan menjalankan test, karena saat itu saya tetap mengikuti dan mereview hasilnya.

**Ringkasnya:** inti (perencanaan + Fase 0–6) selesai dalam ±1,5 jam. Sisanya, ±2 jam 20 menit, dipakai untuk perbaikan UI setelah review, audit, dan dokumentasi. Total masih di bawah timebox ±4 jam.
