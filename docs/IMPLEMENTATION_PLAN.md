# Implementation Plan — Project Reality Check

Referensi: [PRD.md](PRD.md) · [TECH_SPEC.md](TECH_SPEC.md)
Stack: **Django 6.1 + PostgreSQL 18 (backend) + Vite/React (frontend)** · Timebox total: **±4 jam kerja aktual**.
Urutan disusun agar setiap fase berakhir dalam kondisi yang *bisa didemokan*. Jika waktu habis, potong dari fase belakang.

> **Catatan timebox:** waktu penyusunan dokumen perencanaan ini ikut terhitung sebagai kerja aktual. Catat jam mulai dan selesai setiap fase (kolom *Aktual*), lalu laporkan totalnya di README. Jika sudah melewati ±4 jam, terapkan Rencana Potong.

## Ringkasan Fase

| # | Fase | Estimasi | Aktual | Output yang bisa diperiksa |
|---|---|---|---|---|
| 0 | Setup repo, DB, Django & Vite | 20 m | | `runserver` dan `npm run dev` jalan, `data/` berisi salinan file sumber |
| 1 | Models + ingest command | 30 m | | `manage.py migrate && manage.py ingest` → data terlihat di Django Admin |
| 2 | Metrik + rule engine + text signals | 60 m | | `manage.py ingest` mencetak ringkasan findings per project |
| 3 | Test backend | 20 m | | `manage.py test monitor` hijau sesuai expected output Tech Spec §6 |
| 4 | API views | 20 m | | `curl localhost:8000/api/projects` |
| 5 | Frontend React | 50 m | | Daftar + detail + evidence klik + timeline di browser |
| 6 | Dokumentasi | 25 m | | README (9 bagian + Final Question), AI_USAGE.md, .env.example |
| — | Buffer | 15 m | | |
| | **Total** | **240 m** | | |
| 7a | *(tambahan)* Bahasa awam + perkiraan selesai (backend) | — | | `summary` di setiap finding, `forecast_finish`/`forecast_delay_days`, test |
| 7b | *(tambahan)* Redesign UI "Papan status" + responsive | — | | Papan + detail di 3 ukuran layar |

> Fase 7 ditambahkan setelah review UI: tampilan Fase 5 dinilai terlalu teknis untuk orang awam dan terlihat seperti template. Tidak ada di rencana awal; waktu kerjanya dicatat di README.

**Jalur kritis:** Fase 1 → 2 → 3. Setelah Fase 3 selesai, inti nilai produk (kesimpulan + evidence) sudah ada dan bisa didemokan via CLI + Django Admin meskipun frontend belum jadi.

## Fase 0 — Setup (20 m)
- [x] Install **Node 22 LTS** (minimal 20.19) karena belum terpasang. Cek dengan `node --version`.
- [x] Buat role + database Postgres `tata` (Tech Spec §1 Setup database). Verifikasi dengan `psql -h 127.0.0.1 -U tata -d tata -c 'select 1'`.
- [x] `git init`. Buat `.gitignore`: `.venv/`, `__pycache__/`, `.env`, `node_modules/`, `frontend/dist/`.
- [x] Salin `02_*.csv`, `03_*.csv`, `04_*.json` ke `data/` **tanpa modifikasi** (verifikasi dengan `sha256sum`).
- [x] Buat kerangka `AI_USAGE.md` sekarang, lalu **isi sambil jalan**. Langsung catat keputusan yang sudah ada:
  - stack stdlib yang diusulkan AI diganti Django + Vite/React;
  - SQLite diganti PostgreSQL;
  - hasil audit dokumen: konvensi pace, kapasitas klaim bukan dasar perhitungan, keyword diganti frasa spesifik.
- [x] Backend:
  - venv, lalu `pip install "Django==6.1.*" "psycopg[binary]"` → `pip freeze > backend/requirements.txt`. Pastikan wheel `psycopg-binary` tersedia untuk Python 3.14.
  - `django-admin startproject config backend`, lalu `manage.py startapp monitor`.
  - settings: env (Tech Spec §9), `DATABASES` diarahkan ke Postgres, `TIME_ZONE="Asia/Jakarta"`, `USE_TZ=True`, dan `monitor` di `INSTALLED_APPS`.
- [x] Frontend: `npm create vite@latest frontend -- --template react`, hapus boilerplate demo, tambahkan proxy `/api` di `vite.config.js`.
- **Done ketika:** halaman default Django di :8000 dan halaman kosong React di :5173 sama-sama terbuka.

## Fase 1 — Models + ingest (30 m)
- [x] `models.py`: raw + derived models (Tech Spec §4). Jalankan `makemigrations` + `migrate`.
- [x] `admin.py`: register semua model dengan read-only, `list_display` dan `list_filter` berdasarkan `project_id`.
- [x] `management/commands/ingest.py`:
  - argumen `--data-dir` (default `settings.DATA_DIR`);
  - di dalam `transaction.atomic()`: hapus semua → `csv.DictReader` untuk CSV (string kosong → `None`) → `json.load` untuk production data (kolom umum + `payload`);
  - semua timestamp di-`make_aware` (Asia/Jakarta);
  - simpan `generated_at` sebagai `AS_OF`;
  - warning untuk `project_id` yatim;
  - panggil `services.run_assessment(as_of)` (diisi di Fase 2).
- **Done ketika:**
  - Admin menampilkan 6 Project, 23 ProjectUpdate, dan 12 ProductionRecord.
  - Menjalankan ingest dua kali tetap menghasilkan jumlah yang sama (idempotent).
  - Tidak ada warning naive datetime.

## Fase 2 — Metrik + rule engine + text signals (60 m)
- [x] `assess.py` (tanpa import Django): konstanta threshold, dataclass `Finding`, regex stated capacity.
- [x] `compute_metrics()` dengan konvensi waktu Tech Spec §5: laju dari `observed_at`, deadline inklusif, hari kalender pecahan.
- [x] Implementasi rule berurutan sesuai nilai:
  1. `REPORTED_VS_OBSERVED` (dengan timestamp + breakdown pending), `PCT_INCONSISTENT`
  2. `PACE_RISK` (ratio vs historis, HIGH jika kapasitas klaim pun tidak cukup, verify jika kapasitas tidak tersedia)
  3. `ENV_NOT_READY`, `SCOPE_GAP`, `EQUIPMENT_DEGRADED`, `DATA_QUALITY_SKIP`
  4. `STALE_REPORT`, `OVERDUE`, `POST_GO_LIVE_HEALTH`
  5. `DEADLINE_IMMINENT_BLOCKED`, `STATUS_CONTRADICTION` (meta-rule, jalan terakhir)
- [x] `text_signals(updates)`: daftar frasa spesifik (Tech Spec §6).
- [x] Setiap rule mengisi `explanation` (dengan angka dan timestamp), `verify`, `follow_up`, dan `evidence`.
- [x] `services.py`: ubah model → dict, panggil `assess`, simpan `ProjectMetrics` + `Finding`, hitung `attention`.
- [x] Ingest mencetak tabel ringkas `project | attention | rules`.
- **Done ketika:** output ingest cocok dengan tabel expected di Tech Spec §6.

## Fase 3 — Test backend (20 m)
- [x] `tests/test_assess.py`: `pace_ratio` dengan konvensi baru, HIGH ketika `required > capacity`, boundary threshold, regex, dan `text_signals` tidak menangkap pesan kabar baik.
- [x] `tests/test_api.py`: ingest → attention + rule per project, hasil text signals, validitas evidence, urutan list, 404.
- **Done ketika:** `python manage.py test monitor` hijau.

## Fase 4 — API views (20 m)
- [x] `views.py`: `project_list` dan `project_detail` (`@require_GET`, `JsonResponse`), termasuk `is_active`, `stages`, `signals`, timeline + `hints`.
- [x] `monitor/urls.py` + include di `config/urls.py`.
- **Done ketika:** kedua endpoint mengembalikan shape sesuai Tech Spec §7. Test 404 juga hijau.

## Fase 5 — Frontend React (50 m)
- [x] `api.js`: `getProjects()`, `getProject(id)` dengan penanganan error.
- [x] `App.jsx`: fetch list, `selectedId` ↔ `location.hash`, layout dua kolom.
- [x] `ProjectList.jsx` *(diganti `ProjectBoard.jsx` di 7b)*: seksi Aktif & Selesai, tabel + badge attention, deadline beserta nama hari.
- [x] `ProjectDetail.jsx`: Reported vs Observed (+ timestamp, funnel `stages`) → Findings + chip evidence → Sinyal dari update → Verifikasi / Follow-up.
- [x] `Timeline.jsx` *(diganti `ActivityLog.jsx` di 7b)*: item update/record, `<mark>` untuk frasa sinyal, `<details>` untuk raw JSON. Chip evidence → `scrollIntoView` + highlight.
- [x] `styles.css`: badge warna, responsive ~400px.
- **Checklist:**
  - [x] `npm run build` sukses (smoke check).
  - [x] Urutan seksi Aktif: PRJ-005, PRJ-002, PRJ-001, PRJ-003, PRJ-004. Seksi Selesai: PRJ-006.
  - [x] Keenam pertanyaan management (PRD §2) bisa dijawab untuk PRJ-002 hanya dari UI.
  - [x] Klik setiap chip evidence di PRJ-002 berhasil menemukan item timeline.
  - [x] PRJ-001 menampilkan UPD-012 & UPD-019 di seksi sinyal.
  - [x] Backend dimatikan → pesan error tampil, bukan layar kosong.

## Fase 6 — Dokumentasi (25 m)
- [x] ~~README: catat di Limitations bahwa di layar sempit detail muncul di bawah daftar~~ — tidak berlaku lagi setelah Fase 7b (detail jadi halaman sendiri).
- [x] README: Overview, How to Run (DB + 2 terminal), Requirements (Python ≥3.12, Node ≥20.19, Postgres ≥14), Architecture, Data Model, Key Decisions, Assumptions (salin dari PRD §8, termasuk konvensi waktu), Limitations, Next, **Final Question (maksimal 300 kata)**, dan total waktu aktual.
- [x] `.env.example`.
- [x] Rapikan AI_USAGE.md: tools, kegunaan, bagian yang di-generate, proses review, **1 contoh yang ditolak/diubah**, keputusan sendiri.
- [x] Final checklist di Submission Guide §10. Lakukan clone bersih → ikuti README → pastikan jalan.
- [ ] Zip / push repo (tanpa `node_modules`, `.venv`, `.env`).

## Fase 7a — Bahasa awam + perkiraan selesai (backend)
- [x] `Finding.summary` (satu kalimat awam) untuk ke-13 rule; `explanation` tetap sebagai detail teknis.
- [x] `ProjectMetrics.forecast_finish` + `forecast_delay_days`; `STALE_REPORT` menyebut "seharusnya sudah selesai" bila perkiraan < AS_OF.
- [x] Migration `0002_plain_summary_and_forecast`.
- [x] API list: `headline` = `summary`, tambah `forecast_*`, `target_unit`, `last_activity_at`.
- [x] Test: perkiraan per project, `summary` bebas jargon (dicek dengan mutation), kalimat kunci. **31 test hijau** (saat Fase 7a; total sekarang lihat bagian audit di bawah).

## Fase 7b — Redesign UI "Papan status" + responsive
- [x] `format.js`: label awam status, sumber evidence (source_type/source_system → bahasa awam), tanggal.
- [x] `ProjectBoard` (menggantikan `ProjectList`; `Timeline` menjadi `ActivityLog`): kolom sesuai Tech Spec §8, seksi Aktif/Selesai, strip ringkasan.
- [x] `ProjectDetail`: garis waktu jadwal, dua bar, masalah bernomor + "Lihat bukti & detail", yang perlu dilakukan, riwayat aktivitas.
- [x] Responsive 3 ukuran (≥1100 / 680–1100 / <680) + navigasi papan → detail via `#hash` dengan tombol kembali — **di semua ukuran** (lihat catatan Tech Spec §8).
- [x] Visual sesuai prinsip Tech Spec §8 saat itu (tanpa kartu bulat/pil/gradient; diganti gaya dashboard di Fase 9).
- **Checklist:**
  - [x] `npm run build` + lint bersih.
  - [x] Tidak ada nama rule/field/ID di tampilan utama (hanya di "Detail").
  - [x] Semua bukti PRJ-002 bisa dibuka dan menunjuk ke riwayat aktivitas yang benar.
  - [x] Screenshot 1360px, 900px, 400px tanpa scroll horizontal; di HP memilih project membuka halaman detail dan tombol kembali bekerja.
  - [x] Error state tetap bekerja.
- **Hasil:** 22/22 pengecekan headless browser di 1360/900/400px; 6 project × 3 lebar tanpa label jadwal bertumpuk; 32 test backend hijau (saat 7b; 38 setelah audit pasca-7b, 42 setelah audit putaran 2).
- **Ditemukan & diperbaiki saat review screenshot:** "Masalah utama" PRJ-003/004 menampilkan temuan yang kurang penting (→ `RULE_ORDER`); label jadwal bertumpuk (→ "Perkiraan selesai" di baris kedua); timestamp data mentah dalam UTC (→ WIB); teks *verify/follow-up* masih berjargon (→ ditulis ulang, test bebas-jargon diperluas).

## Audit pasca-7b (kode + dokumen)

Audit mendalam backend & frontend, ditambah pengecekan kesesuaian dokumen dengan kode oleh agent terpisah.

**Bug & titik rapuh yang diperbaiki (masing-masing dengan test):**
- [x] `DATA_QUALITY_SKIP` membaca semua snapshot historis, sehingga temuan bisa dobel. Sekarang hanya snapshot terbaru per field.
- [x] Frontend memakai `key={f.rule}`, padahal satu rule bisa muncul lebih dari sekali. Sekarang key unik.
- [x] Frasa sinyal dicocokkan sebagai potongan kata ("threshold" cocok dengan "hold"). Sekarang kata utuh, di backend dan `<mark>` frontend.
- [x] Regex kapasitas "halaman per hari" berlaku untuk semua unit. Sekarang hanya untuk project `pages`.
- [x] Record dengan unit berbeda tidak dicek (`observed_unit` tidak terpakai; `UNIT_MISMATCH` di dokumen tidak pernah dibuat). Sekarang diabaikan → `INSUFFICIENT_DATA`.
- [x] `ingest` dengan data rusak menampilkan traceback mentah. Sekarang `CommandError` dengan pesan jelas, data lama tetap utuh, dan `--data-dir` diterima sebagai string maupun Path.
- [x] Urutan findings di API bergantung pada urutan ID di database. Sekarang memakai `finding_order()` yang sama dengan `assess.py`.
- [x] Persentase dibulatkan (79.5% tampil 80%). Sekarang 1 desimal.
- [x] Judul tab browser disamakan dengan judul halaman.
- [x] Mode gelap dicek visual: kontras dan warna status tetap terbaca.

**Hasil:** 38 test backend hijau, build + lint bersih, 22/22 pengecekan UI di 3 ukuran layar, console browser bersih.

**Dokumen yang disinkronkan:** PRD (FR-5, FR-8, FR-13), Tech Spec (jumlah rule 13, `INSUFFICIENT_DATA`, unit berbeda, urutan findings, contoh API, nama seksi UI, daftar test), README (jumlah rule, field model, jumlah test), dan AI_USAGE.

## Audit putaran 2 — kasus pinggir

Probe langsung ke rule engine dengan kasus yang tidak ada di dataset, tetapi pasti muncul pada 100 project.

- [x] **Project tanpa progress (laju 0) dinilai "Aman"**: alarm terlewat, karena rasio laju tidak terdefinisi sehingga `PACE_RISK` diam. Sekarang HIGH: "Belum ada progress yang tercatat…".
- [x] Tidak ada data sistem → sebelumnya hanya INFO ("Aman"). Sekarang `INSUFFICIENT_DATA` LOW ("Perhatikan").
- [x] Target kosong di master → sebelumnya tanpa temuan sama sekali. Sekarang `INSUFFICIENT_DATA` LOW.
- [x] Urutan papan untuk nilai seri tidak deterministik (query tanpa `order_by`). Sekarang `project_id` jadi pemecah seri.
- [x] Perkiraan selesai tepat di hari deadline ditulis "sebelum deadline". Sekarang "tepat di hari deadline".
- [x] Papan kosong (belum `ingest`) sebelumnya hanya menampilkan footnote. Sekarang ada pesan petunjuk.
- [x] Record sistem tipe baru tanpa kosakata awam tampil kosong di riwayat. Sekarang ada teks pengganti.
- [x] Dikonfirmasi benar: target terlampaui → OK; deadline lewat → OVERDUE.

**Hasil:** 42 test hijau, output dataset tidak berubah, build + lint bersih, 22/22 pengecekan UI. Dokumen diperbarui bersamaan dengan kode.

**Keputusan lanjutan (dipilih user):** batas MEDIUM `PACE_RISK` diturunkan **1.1 → 1.0**. Sebelumnya, project dengan rasio 1.0–1.1 tampil "N hari terlambat" di kolom perkiraan tetapi statusnya bisa "Aman". Rasio > 1.0 setara dengan perkiraan selesai lewat deadline, dan kesetaraan ini dikunci test (terbukti gagal dengan batas lama). Output dataset tidak berubah. Contoh "PRJ-001 kasus perbatasan" di dokumen diganti dengan PRJ-004 (terlambat 13 hari tetapi hanya MEDIUM). **43 test hijau.**

## Audit putaran 3 — fuzz, skala, keamanan, aksesibilitas, integritas data

- [x] **Fuzz test** (3000 → 10.000 project acak): ditemukan **crash `OverflowError`** saat perkiraan selesai > ribuan tahun (progress sangat kecil). Perkiraan dibatasi 10 tahun. Fuzz test permanen (500 project, seed tetap) ditambahkan.
- [x] **Skala:** list endpoint 2 query konstan (tanpa N+1), dikunci test dengan 100 project. Detail 4 query (diukur).
- [x] **Keamanan:**
  - `DJANGO_DEBUG=0` dengan secret key default (ada di repo) sebelumnya tetap jalan; sekarang app menolak start.
  - ID berisi NUL (`%00`) membuat 500, dan UI melaporkannya sebagai "backend tidak dapat dihubungi"; sekarang 404.
  - XSS lewat `#hash` aman (tidak ada alert/dialog).
  - `MAILERS` bawaan template yang tidak terpakai dihapus.
  - Peringatan HTTPS dicatat sebagai limitation.
- [x] **Aksesibilitas:** `--ink-3` hanya 3.3:1 (gagal WCAG AA) untuk header kolom, waktu, dan footnote. Diganti, semua warna teks sekarang ≥ 4.5:1 di mode terang & gelap. Navigasi keyboard (Tab ke baris, Enter membuka, `aria-expanded`) berfungsi.
- [x] **Integritas data:** ID duplikat, kolom hilang, angka bukan angka, JSON rusak → `CommandError`, data lama utuh. Update untuk project tak dikenal → disimpan + WARNING. File sumber kosong → sekarang WARNING (sebelumnya diam).

**Hasil:** 46 test hijau, `check` bersih, build + lint bersih, UI 22/22.

## Audit putaran 4 — dependency & clone bersih (tidak ada temuan)

- [x] `npm audit`: 0 kerentanan. `pip-audit -r requirements.txt`: tidak ada kerentanan yang diketahui.
- [x] Clone bersih (hanya file yang akan masuk repo, 50 file, tanpa venv/node_modules/cache/.env) → ikuti README dari nol: install, migrate, ingest, 46 test, API, build, lint semuanya berhasil.
- [x] Dokumen diverifikasi agent terpisah terhadap kode: tidak ada kesalahan fakta tersisa.

Putaran ini tidak menemukan masalah baru, jadi audit dihentikan di sini.

## Fase 8 — UX untuk orang awam (atas permintaan user, di luar rencana awal)

Hasil review user: orang awam masih tidak paham "ini aplikasi apa" dan apa yang harus dilakukan. Keputusan user: pengantar + *Cara membaca*, ringkasan hari ini di atas papan, gaya **bersih & modern** (Plus Jakarta Sans dibundel, ukuran 17px, latar putih hangat), dan paragraf *Kesimpulan* di awal detail.

### Fase 8a — Kesimpulan + istilah di sumber (backend)
- [x] `assess.conclusion(attention, findings)` → `{text, first_step}`; dikirim di API detail sebagai `conclusion`.
- [x] Istilah dibereskan di sumber: ML → "meter linear", production → "sistem customer", go-live → "mulai dipakai".
- [x] Test: kesimpulan per project, langkah pertama memilih hambatan/jadwal dulu, bebas jargon; fuzz mencakup `conclusion`. **47 test hijau.**

### Fase 8b — Redesign UX & visual (frontend)
- [x] Pengantar + panel *Cara membaca* (status, dua angka progress, perkiraan selesai, glosarium PIC / meter linear / endpoint / sistem customer / DMS).
- [x] *Perlu tindakan hari ini* di atas papan + hitungan "perlu dipantau / aman"; papan berjudul *Semua project*.
- [x] Detail dibuka dengan *Kesimpulan* + *Langkah pertama*.
- [x] Tooltip "?" untuk label kunci (Laporan PIC, Tercatat di sistem, Perkiraan selesai, tahapan endpoint); jenis project diterjemahkan.
- [x] Visual: Plus Jakarta Sans (`@fontsource`, lokal), 17px, latar `#FAFAF9`, tanpa serif; kontras ≥ 4.5:1 terang & gelap.
- **Checklist:** build + lint, UI 3 ukuran layar tanpa scroll horizontal, kontras WCAG, keyboard (tooltip & Cara membaca bisa dibuka dengan keyboard), error state, dokumen diverifikasi agent.
- **Hasil:** 30/30 pengecekan headless browser (3 ukuran layar, pengantar, *Perlu tindakan hari ini*, *Cara membaca* & "?" via keyboard, Kesimpulan pertama di detail, bebas jargon, 16/16 bukti, font termuat, error state), build + lint bersih, 47 test backend.
- **Ditemukan & diperbaiki saat review screenshot:**
  - bar progress di papan menyusut jadi ±20px (kolom terlalu sempit);
  - legenda bar di *Cara membaca* terpecah ke baris lain (flex);
  - label "Tercatat sistem" terpotong 2 baris;
  - dua bar dalam satu baris tidak mulai sejajar.
- **Satu kegagalan pengecekan adalah masalah script, bukan aplikasi:** cek bukti awalnya 14/16 karena halaman lebih panjang sehingga scroll halus lebih lama dari jeda tetap 350ms. Script diubah untuk menunggu sampai sumber terlihat utuh (kriteria lebih ketat).

## Fase 9 — Tampilan dashboard profesional (atas permintaan user, di luar rencana awal)

Hasil review user: UI terasa tidak profesional; diminta tampil seperti dashboard. Logika, API, dan teks tidak berubah, hanya tampilan.

- [x] Kerangka: sidebar gelap (menu *Ringkasan* + daftar project bertitik warna status, project aktif ditandai) + top bar; di ≤ 960px sidebar menjadi bar atas.
- [x] Ringkasan: kartu pengantar, **kartu KPI** (total, perlu tindakan, perlu dipantau, aman), kartu *Perlu tindakan hari ini*, tabel dalam kartu dengan header berlatar dan jumlah per seksi.
- [x] Status menjadi badge (titik + teks); detail menjadi kartu, Jadwal & Progress berdampingan; nomor masalah di lingkaran berwarna.
- [x] Palet slate baru; kontras WCAG AA dihitung untuk 27 pasangan warna (terang & gelap, termasuk sidebar dan badge). Semua ≥ 4.5:1.
- **Hasil:** 34/34 pengecekan headless browser (ditambah: angka KPI, isi sidebar, sidebar menandai project yang dibuka, sidebar jadi bar atas di tablet/HP), build + lint bersih, backend tidak berubah (47 test).
- **Ditemukan & diperbaiki saat review:**
  - kolom "Masalah utama" terpotong di 1360px karena sidebar memakan lebar; kolom ini kini pindah ke baris sendiri sampai layar > 1500px;
  - selector CSS `.board-head span:last-child` ikut menyembunyikan tombol "?" di header tabel (span di dalam span). Bug ini sudah ada sejak Fase 8b pada lebar 680–1100px, tetapi baru tertangkap ketika breakpoint bergeser; diperbaiki menjadi `> span:last-child`.

### Audit pasca-Fase 9
- [x] Backend: 47 test hijau, `check` & `makemigrations --check` bersih, pip-audit & npm audit 0 kerentanan. Probe API: ID tidak valid/NUL/500 karakter/path traversal → 404, Host asing → 400, POST ditolak (403 CSRF), header keamanan ada.
- [x] Dicek: KPI *Perlu tindakan* tidak bisa berbeda dari daftar *Perlu tindakan hari ini*, karena project selesai paling tinggi MEDIUM (`rule_post_go_live_health`).
- [x] **Bug: tooltip "?" terpotong/tertutup di 10 tempat**, termasuk menyebabkan scroll horizontal di detail 1360px. Penyebab: kartu tabel `overflow: hidden`, tooltip selalu rata kiri tombol, dan tidak ada pengecekan jarak ke bawah layar. Perbaikan: posisi `fixed` dihitung dari tombol dan dijepit di dalam layar. Probe baru membuka **36 tooltip** di 4 lebar layar × 3 halaman dan memeriksa keempat sudutnya terlihat: 0 gagal.
- [x] **A11y: perlu 9× Tab untuk melewati sidebar.** Ditambah tombol *Lewati ke konten* (WCAG 2.4.1).
- **Hasil:** 34/34 pengecekan UI tetap lulus, build + lint bersih.

### Fase 9b — Penempatan layout (review user)
- [x] Daftar project dikeluarkan dari sidebar (keberatan user: tidak muat untuk 10.000+ project). Sidebar hanya logo + satu menu.
- [x] Tanggal data pindah dari bawah sidebar ke **navbar kanan** (chip). Navbar sticky; di detail ada breadcrumb *Ringkasan / nama project* (kemudian dinamai *Dashboard / nama project*) yang menggantikan link "← Semua project".
- [x] Penempatan diperiksa ulang: header kolom *Perkiraan selesai* sempat terpecah 2 baris (tanda "?" turun), kolom dilebarkan ke 155px; dicek satu baris di 1100/1360/1600px. `scroll-margin` blok dinaikkan agar bukti yang diklik tidak tertutup navbar sticky.
- **Catatan skala (jujur):** sidebar tidak menambah beban server, karena memakai data yang sama dengan tabel (1 request, 2 query). Batas sebenarnya untuk ribuan project adalah `GET /api/projects` tanpa paginasi; dicatat di README *Limitations*.
- [x] Menu sidebar diganti namanya menjadi **Dashboard**; membuka detail **tidak** menambah menu di sidebar (permintaan user), posisi cukup dari breadcrumb. Nama diseragamkan: menu, judul halaman, dan breadcrumb semuanya **Dashboard** (*Dashboard / nama project*).
- **Hasil:** 40/40 pengecekan UI (ditambah: menu bernama Dashboard, detail tidak menambah menu); sebelumnya 38/38 (ditambah: sidebar tanpa daftar project, tanggal di navbar kanan, navbar tetap terlihat saat scroll, breadcrumb di 3 lebar layar), 36/36 tooltip terlihat utuh, build + lint bersih.

## Audit pasca-Fase 9b — cek ulang terhadap folder requirements

Brief, Data Dictionary, dan Submission Guide dibaca ulang dan dicocokkan dengan kode serta dokumen.

- [x] 6 pertanyaan management di brief terjawab di UI: project berjalan (tabel *Sedang berjalan*), yang perlu perhatian (status + KPI + *Perlu tindakan hari ini*), alasan (masalah + Kesimpulan), dasar informasi (bukti → sumber), yang perlu diverifikasi (*Perlu dikonfirmasi*), tindak lanjut (*Yang perlu dilakukan* + Langkah pertama).
- [x] 8 minimum expectations, README 9 seksi + Final Question, AI_USAGE 6 seksi, `.env.example`, dependency file, migrations, import command: ada.
- [x] Data di `data/` identik dengan file asli (sha256). Semua field, `record_type`, `source_system`, dan `source_type` di Data Dictionary tertangani.
- [x] **Bug: teks awam masih mengandung "production"**: *Perlu dikonfirmasi* PRJ-005 "akses ke sistem production-nya". Test jargon tidak menangkapnya karena hanya mencari kode/ID/huruf kapital. Regex `JARGON` diperluas dengan kata teknis (production, go-live, environment, deployment, snapshot); test dibuktikan gagal dulu, lalu teks diperbaiki menjadi "akses ke sistemnya".
- [x] **Label riwayat aktivitas masih teknis:** "Endpoint teruji di production", "Koneksi production", "Deployment" → "… di sistem customer", "Koneksi ke sistem customer", "Pemasangan aplikasi". Dicek dengan memindai teks yang tampil di 7 halaman. Sisa kata "production" hanya ada di glosarium (penjelasan istilah) dan **pesan asli tim** yang sengaja dikutip apa adanya sebagai bukti.
- [x] Favicon masih logo bawaan Vite (sisa template) → diganti logo "t" yang sama dengan sidebar.
- [x] Git sudah di-`init`, **belum ada commit dan belum ada remote**. File yang akan masuk commit dicek: 52 file, tanpa `.venv`, `node_modules`, `.env`, build output, atau folder `requirements/`.
- **Hasil:** 47 test backend, 41/41 UI, 36/36 tooltip, build + lint bersih.
- **Sisa yang harus diisi user sendiri:** sudah diisi (TODO di `AI_USAGE.md` §4–§6 dan waktu kerja di README). Tinggal commit + akses repo untuk evaluator.

## Rencana Potong Jika Waktu Habis

| Urutan potong | Item | Dampak |
|---|---|---|
| 1 | Funnel `stages`, sinkronisasi hash URL, raw JSON viewer | Evidence tetap terlihat via ID + timeline |
| 2 | `<mark>` di timeline (seksi sinyal tetap dipertahankan) | Hanya kosmetik |
| 3 | `POST_GO_LIVE_HEALTH`, `OVERDUE` | PRJ-006 kehilangan ringkasan kesehatan, dan OVERDUE tidak punya kasus di dataset |
| 4 | Frontend seluruhnya | Demo lewat output ingest + Django Admin + API JSON. Didokumentasikan sebagai incomplete. |

**Tidak boleh dipotong:** evidence per finding, seksi sinyal update (satu-satunya tempat hold PRJ-001 terlihat), test expected output, README how-to-run, AI_USAGE.md.

## Draf Jawaban Final Question (untuk diisi di README)

Jika dipakai untuk 100 project dan menjadi dasar keputusan:
1. **Ingest otomatis + kontrak data per jenis project.** Ganti file manual dengan feed terjadwal dari production system. Definisikan mapping "observed quantity" dan definisi "selesai" per `project_type` sebagai konfigurasi, bukan if-else di kode. Kalender kerja per project dipakai untuk perhitungan pace.
2. **Kalibrasi dan audit rule.** Threshold ditetapkan bersama management, diberi versi, dan setiap kesimpulan menyimpan versi rule yang dipakai. Tambahkan feedback "flag ini salah/benar" untuk mengukur false positive (contoh: PRJ-004 terlambat 13 hari tetapi hanya MEDIUM karena rasio 1.40 < 1.5).
3. **Akuntabilitas & freshness sebagai first-class.** SLA update per PIC, deteksi otomatis data basi, dan riwayat perubahan status agar tren (makin memburuk/membaik) terlihat, bukan hanya snapshot. Pada skala ini ingest juga perlu dijalankan via scheduler, dan snapshot assessment disimpan per hari (bukan ditimpa).
