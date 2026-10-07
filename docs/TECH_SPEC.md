# Tech Spec — Project Reality Check

Referensi: [PRD.md](PRD.md) · [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)

## 1. Stack

| Komponen | Pilihan | Alasan |
|---|---|---|
| Backend | Python 3.12+ · **Django 6.1** | ORM, migrations, management command, test runner, dan admin sudah tersedia dalam satu paket |
| API | Django views + `JsonResponse` (tanpa DRF) | Hanya ada 2 endpoint GET read-only, sehingga serializer/viewset belum dibutuhkan |
| Storage | **PostgreSQL 18** via `psycopg` 3 | DB server sungguhan, `JSONField` disimpan sebagai `jsonb` (bisa di-query), dan siap untuk skala 100+ project |
| Frontend | **Vite + React** (JavaScript) | Dev server cepat dan cocok untuk UI berbasis komponen (list, detail, timeline) |
| Styling | CSS biasa (1 file) | Tanpa UI library |
| Test backend | `django.test.TestCase` | Sudah built-in |
| Inspeksi data mentah | Django Admin | Gratis: evaluator bisa menelusuri raw tables tanpa tools tambahan |

**Dependency:**
- Backend: `Django`, `psycopg[binary]` (`backend/requirements.txt`).
- Frontend: `react`, `react-dom`, `vite`, `@vitejs/plugin-react`, `oxlint` untuk `npm run lint`, dan `@fontsource/plus-jakarta-sans` (font dibundel lokal, lisensi OFL; Fase 8b) (`frontend/package.json` + lockfile).
- Tidak memakai `django-cors-headers`, karena Vite dev proxy meneruskan `/api` ke Django (same-origin dari sisi browser).

**Runtime:** Python ≥ 3.12, **Node ≥ 20.19 (disarankan 22 LTS)** sesuai kebutuhan Vite terbaru, PostgreSQL ≥ 14 (dikembangkan di 18.6).

### Setup database

Role aplikasi butuh hak `CREATEDB` karena test runner Django membuat database `test_tata` sendiri.

```bash
sudo -u postgres psql <<'SQL'
CREATE ROLE tata LOGIN PASSWORD 'tata' CREATEDB;
CREATE DATABASE tata OWNER tata;
SQL
```

Kredensial `tata/tata` hanya untuk local dev dan didokumentasikan di `.env.example`. Ini bukan secret.

## 2. Struktur Repo

```
test_tata.id/
├── README.md
├── AI_USAGE.md
├── .env.example
├── docs/                         # PRD, Tech Spec, Implementation Plan
├── data/                         # salinan ketiga file sumber, TIDAK diubah
├── backend/
│   ├── requirements.txt
│   ├── manage.py
│   ├── config/                   # settings.py, urls.py, wsgi.py
│   └── monitor/                  # satu Django app
│       ├── models.py             # raw + derived models
│       ├── migrations/
│       ├── admin.py              # register semua model (read-only)
│       ├── assess.py             # metrik + rule engine + text signals (pure functions, tanpa ORM)
│       ├── services.py           # ORM <-> assess: load raw, simpan derived
│       ├── views.py              # 2 endpoint JSON
│       ├── urls.py
│       ├── management/commands/ingest.py
│       └── tests/
│           ├── test_assess.py    # unit test pure function
│           ├── test_api.py       # ingest + expected output + shape API
│           └── test_fuzz.py      # 500 project acak (seed tetap): tidak crash, invariant terjaga
└── frontend/
    ├── package.json
    ├── vite.config.js            # proxy /api -> http://127.0.0.1:8000
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx               # sidebar + top bar + navigasi #hash: ringkasan atau halaman detail
        ├── api.js                # fetch wrapper + pesan error
        ├── format.js             # tanggal (id-ID, WIB), angka (1,234.5), kosakata awam: status + artinya, jenis project, glosarium, sumber, field record
        ├── components/
        │   ├── Intro.jsx         # pengantar "aplikasi apa ini" + panel Cara membaca (status, dua angka progress, glosarium)
        │   ├── Term.jsx          # istilah + tombol "?" (keyboard: Enter buka, Escape tutup)
        │   ├── ProjectBoard.jsx  # Perlu tindakan hari ini + papan semua project (+ StatusMark, Bar)
        │   ├── ProjectDetail.jsx # kesimpulan, jadwal, dilaporkan vs sistem, masalah + bukti, tindakan, pesan perlu dibaca
        │   └── ActivityLog.jsx   # riwayat aktivitas + penanda frasa
        └── styles.css
```

## 3. Alur Data

```
data/*.csv, *.json
      │  python manage.py ingest   (transaction.atomic: hapus semua -> load ulang)
      ▼
Raw models: Project, ProjectUpdate, ProductionRecord     ← 1:1 dengan sumber
      │  services.run_assessment() -> assess.py (pure)
      ▼
Derived models: ProjectMetrics, Finding                  ← selalu bisa dibangun ulang
      │  views.py (JsonResponse; text signals dihitung saat request)
      ▼
/api/projects, /api/projects/<id>  ──(Vite proxy)──▶  React UI (localhost:5173)
```

- **Raw dan derived dipisah.** Derived dibuang dan dihitung ulang setiap ingest. Raw tidak pernah "dibersihkan".
- **`assess.py` tidak meng-import Django.** Input dan output-nya berupa dict/dataclass. Dengan begitu rule engine bisa di-test tanpa DB dan logikanya mudah dijelaskan secara terpisah dari framework.
- Ingest dibungkus `transaction.atomic()`. Jika parsing gagal di tengah jalan, data lama tetap utuh.

## 4. Data Model (Django models)

```python
# ---------- RAW LAYER ----------
class Project(models.Model):
    project_id = models.CharField(primary_key=True, max_length=20)
    customer = models.CharField(max_length=200)
    project_name = models.CharField(max_length=200)
    project_type = models.CharField(max_length=100)
    pic = models.CharField(max_length=100)
    start_date = models.DateField()
    deadline = models.DateField()
    target = models.FloatField(null=True)
    target_unit = models.CharField(max_length=20)
    reported_actual = models.FloatField(null=True)
    reported_progress_pct = models.FloatField(null=True)
    reported_status = models.CharField(max_length=30)
    last_reported_update_at = models.DateTimeField(null=True)

class ProjectUpdate(models.Model):
    update_id = models.CharField(primary_key=True, max_length=20)
    project_id = models.CharField(max_length=20, db_index=True)   # bukan FK, lihat catatan
    timestamp = models.DateTimeField()
    source_type = models.CharField(max_length=30)
    source_name = models.CharField(max_length=100)
    message = models.TextField()

class ProductionRecord(models.Model):
    source_record_id = models.CharField(primary_key=True, max_length=40)
    project_id = models.CharField(max_length=20, db_index=True)
    source_system = models.CharField(max_length=50)
    record_type = models.CharField(max_length=50)
    timestamp = models.DateTimeField()
    payload = models.JSONField()          # record asli, lengkap (jsonb)

# ---------- DERIVED LAYER ----------
class ProjectMetrics(models.Model):
    project = models.OneToOneField(Project, primary_key=True, on_delete=models.CASCADE, related_name="metrics")
    as_of = models.DateTimeField()
    computed_pct = models.FloatField(null=True)      # reported_actual / target
    observed_actual = models.FloatField(null=True)   # dari production system
    observed_at = models.DateTimeField(null=True)    # timestamp snapshot observed
    observed_source_id = models.CharField(max_length=40, null=True)
    observed_pct = models.FloatField(null=True)
    days_remaining = models.IntegerField(null=True)  # deadline - AS_OF.date (hari kalender)
    historical_rate = models.FloatField(null=True)   # per hari, dihitung dari observed_at
    required_rate = models.FloatField(null=True)
    pace_ratio = models.FloatField(null=True)        # required_rate / historical_rate
    stated_capacity = models.FloatField(null=True)   # klaim dari update (PRJ-002)
    forecast_finish = models.DateTimeField(null=True)  # observed_at + sisa pekerjaan / historical_rate
    forecast_delay_days = models.IntegerField(null=True)  # forecast_finish.date - deadline (+ = terlambat)
    last_activity_at = models.DateTimeField(null=True)
    attention = models.CharField(max_length=10)      # HIGH | MEDIUM | LOW | OK

class Finding(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="findings")
    rule = models.CharField(max_length=40)
    severity = models.CharField(max_length=10)       # HIGH | MEDIUM | LOW | INFO
    category = models.CharField(max_length=20)       # DATA_MISMATCH | SCHEDULE | BLOCKER | DATA_QUALITY | STALE
    summary = models.TextField(default="")           # satu kalimat bahasa awam (tampilan utama)
    explanation = models.TextField()                 # detail teknis: angka, nama field, timestamp
    verify = models.TextField(blank=True)
    follow_up = models.TextField(blank=True)
    evidence = models.JSONField()                    # [{"ref_type": "update|production|master", "ref_id": "..."}]
```

**Catatan desain:**
- **`project_id` di raw updates/records bukan FK.** Jika ada record yang merujuk project tidak dikenal, record tersebut tetap tersimpan (tidak hilang karena constraint) dan ingest mencetak warning. Prinsipnya: data sumber disimpan apa adanya.
- **`payload` berupa `JSONField`, bukan model per record_type.** Ada 8 record_type dengan field berbeda dan hanya 12 record, jadi model per tipe hanya menambah 8 model kecil. Upgrade path: model khusus jika volume besar atau perlu query per field.
- **`evidence` berupa `JSONField`, bukan tabel relasi.** Evidence hanya dibaca bersama finding-nya. Test memastikan setiap `ref_id` benar-benar ada di raw tables. Upgrade ke tabel relasi diperlukan jika butuh query terbalik ("finding apa saja yang mengutip UPD-013?").
- **Text signals tidak disimpan.** Hasilnya murah dihitung ulang dari `ProjectUpdate` saat request dan bukan bagian dari assessment.

## 5. Metrik

### Konvensi waktu
- **Zona waktu:** `TIME_ZONE = "Asia/Jakarta"`, `USE_TZ = True`. Semua timestamp naive dari sumber di-`make_aware` ke Asia/Jakarta saat ingest.
- **`AS_OF`** = `production_data.generated_at` (2026-10-06T17:00:00 WIB), disimpan saat ingest. Dipakai untuk `days_remaining`, data basi, dan `OVERDUE`.
- **Perhitungan laju memakai `observed_at`** (timestamp snapshot), bukan `AS_OF`, karena setiap sumber diperbarui pada waktu berbeda.
- **Deadline inklusif:** batasnya `deadline 23:59:59`.
- **Hari kalender** (bukan hari kerja), dalam satuan hari pecahan (`timedelta.total_seconds() / 86400`).

| Metrik | Rumus | Catatan |
|---|---|---|
| `computed_pct` | `reported_actual / target * 100` | Dibandingkan dengan `reported_progress_pct` |
| `observed_actual`, `observed_at` | Lihat tabel mapping di bawah | Record **terbaru yang memiliki field tersebut** |
| `days_remaining` | `(deadline - AS_OF.date).days` | Integer, untuk tampilan dan rule tenggat |
| `historical_rate` | `observed_actual / (observed_at - start_date 00:00)` | Hanya untuk unit kuantitas |
| `required_rate` | `(target - observed_actual) / (deadline 23:59:59 - observed_at)` | |
| `pace_ratio` | `required_rate / historical_rate` | Lebih dari 1 berarti butuh akselerasi dibanding laju nyata |
| `stated_capacity` | regex dari pesan update | Skenario terbaik, **bukan** pembagi pace_ratio |

**Mapping observed quantity:**

| record_type / field | Unit |
|---|---|
| `production_snapshot.verified_quantity` (workflow_state=VERIFIED) | ML |
| `production_snapshot.pages_processed_total` | pages |
| `production_snapshot.processed_boxes` | boxes |
| `verification_snapshot.records_verified` | records |
| `integration_snapshot.production_tested_endpoints` | endpoints (definisi "done" = sudah teruji di production) |

Record yang mencantumkan `unit` berbeda dari `project.target_unit` **diabaikan** sebagai observed (tidak dibandingkan). Jika tidak ada record lain, muncul finding LOW `INSUFFICIENT_DATA`. Tidak ada rule `UNIT_MISMATCH` terpisah.

**Perkiraan selesai (Fase 7a):** `forecast_finish = observed_at + (target − observed_actual) / historical_rate` hari, hanya untuk unit kuantitas, dan hanya jika ≤ `MAX_FORECAST_DAYS` (3650 hari). Di atas itu, perkiraan tidak bermakna dan sempat membuat crash `OverflowError` (ditemukan fuzz test); `PACE_RISK` tetap HIGH lewat rasio, untuk deadline yang wajar (rasio > 1.5 selama sisa waktu < ±6,5 tahun). `forecast_delay_days = forecast_finish.date − deadline` dalam hari kalender (positif = terlambat). Jika `forecast_finish < AS_OF` (PRJ-003), `STALE_REPORT` menyebut bahwa project "seharusnya sudah selesai" tetapi tidak ada laporan. Integrasi/DMS tidak diperkirakan.

**Stated capacity:** diekstrak dengan regex `(\d[\d.,]*)\s*halaman per hari` dari pesan update, **hanya untuk project ber-unit `pages`**. Regex ini sengaja sempit dan hanya cocok dengan pola di dataset (`ponytail:` upgrade ke field terstruktur bila sumber menyediakan).

## 6. Rule Engine

`monitor/assess.py` berisi fungsi-fungsi `rule_x(ctx) -> list[Finding]` (`ctx` = dataclass berisi project, updates, records, metrics, as_of). Meta-rule menerima `(ctx, findings)`. Semua rule adalah pure function sehingga mudah di-test. Threshold dikumpulkan sebagai konstanta di atas file. Rule hanya berjalan untuk project aktif (`reported_status != COMPLETED`), kecuali `POST_GO_LIVE_HEALTH` dan `COMPLETION_NOT_SUPPORTED` yang khusus untuk project selesai.

| Rule | Kondisi | Severity | Evidence |
|---|---|---|---|
| `PCT_INCONSISTENT` | `abs(reported_progress_pct - computed_pct) > 1` (poin persen) | MEDIUM | master |
| `REPORTED_VS_OBSERVED` | `abs(reported_actual - observed_actual) / target > 1%` | MEDIUM; HIGH bila > 5% | master + production record(s) |
| `PACE_RISK` | `pace_ratio > 1.0` → MEDIUM (setara perkiraan selesai lewat deadline; dikunci test `test_pace_finding_iff_forecast_late`); `pace_ratio > 1.5` **atau** `required_rate > stated_capacity` → HIGH; **laju historis = 0** (belum ada progress tercatat, rasio tak terdefinisi) → HIGH | MEDIUM/HIGH | master + record observed + update kapasitas |
| `OVERDUE` | proyek aktif dan `days_remaining < 0` | HIGH | master |
| `DEADLINE_IMMINENT_BLOCKED` | `0 ≤ days_remaining ≤ 7` dan ada blocker aktif | HIGH | evidence dari blocker |
| `EQUIPMENT_DEGRADED` | scanner_status terbaru punya status ≠ RUNNING | MEDIUM (OUT_OF_SERVICE → HIGH) | scanner record + update operator/vendor |
| `ENV_NOT_READY` | `environment_check.connection_status != "CONNECTED"` atau `production_tested_endpoints == 0` | HIGH | api records + update |
| `SCOPE_GAP` | `developed_endpoints < target_endpoints` | MEDIUM | api record |
| `DATA_QUALITY_SKIP` | `records_skipped_* > 0` pada **snapshot terbaru** per field (bukan setiap snapshot historis) | MEDIUM | quality record + update yang menyebut "dilewati" |
| `STALE_REPORT` | `AS_OF - last_activity_at > 3 hari` | MEDIUM | master + update terakhir + record terakhir |
| `STATUS_CONTRADICTION` | `reported_status == ON TRACK` dan ada finding HIGH | HIGH | master + evidence dari finding HIGH |
| `COMPLETION_NOT_SUPPORTED` | COMPLETED, tetapi `(target - observed_actual) / target > 1%`: klaim "selesai" tidak didukung data sistem | MEDIUM; HIGH bila > 5% | master + record observed |
| `POST_GO_LIVE_HEALTH` | COMPLETED: `application_status != ONLINE` → MEDIUM; `failed/(success+failed) > 10%` → MEDIUM; selain itu INFO ringkasan kesehatan | INFO/MEDIUM | usage record |
| `INSUFFICIENT_DATA` | proyek aktif dengan `target` kosong, **atau** unit punya mapping observed tetapi tidak ada record sistem (ber-unit sama) | **LOW** ("Perhatikan" — tanpa data, sistem tidak bisa menyatakan aman) | master |

Total **14 rule**: 10 rule biasa + 2 meta-rule untuk project aktif, dan `COMPLETION_NOT_SUPPORTED` + `POST_GO_LIVE_HEALTH` untuk project selesai. `COMPLETION_NOT_SUPPORTED` hanya berlaku bila unit punya mapping observed (bukan `system`), jadi PRJ-006 tidak terpengaruh.

**Detail rule:**
- **`REPORTED_VS_OBSERVED`:**
  - Explanation selalu menyebut **kedua timestamp**.
  - Jika `last_reported_update_at > observed_at`, selisih diberi label *"belum terverifikasi sistem"*, bukan "salah".
  - Jika ada record `pending_internal_check_quantity` dan `reported ≈ verified + pending`, rinciannya dimasukkan ke explanation. Contoh PRJ-001: *"318 = 301.5 verified + 16.5 pending internal check"*. Tidak ada rule terpisah untuk ini.
- **`PACE_RISK`:**
  - Explanation menyebut laju historis, laju yang dibutuhkan, dan kapasitas klaim (jika ada). Contoh: *"butuh 6,551/hari; laju nyata 3,355/hari; bahkan kapasitas klaim 4,500/hari tidak cukup"*.
  - Jika kapasitas tidak tersedia, field `verify` berisi *"Data kapasitas harian tidak tersedia; minta rekap kapasitas harian ke PIC."*. Ini berlaku untuk PRJ-004 (UPD-023).
- **Blocker aktif** = finding `ENV_NOT_READY`, atau `EQUIPMENT_DEGRADED` dengan severity HIGH. **Hanya sinyal terstruktur.** Teks bebas tidak pernah menjadi blocker.
- **Attention level** = severity tertinggi dari findings (hanya INFO atau tidak ada findings → `OK`).
- **Urutan daftar** (per seksi Aktif/Selesai): `(attention, jumlah HIGH desc, days_remaining asc)`, lalu `project_id` sebagai pemecah seri.
- **Urutan findings dalam satu project:** `finding_order()` = severity, lalu `RULE_ORDER`: `COMPLETION_NOT_SUPPORTED`, `REPORTED_VS_OBSERVED`, `PACE_RISK`, `OVERDUE`, `ENV_NOT_READY`, `DEADLINE_IMMINENT_BLOCKED`, `STALE_REPORT`, `EQUIPMENT_DEGRADED`, `DATA_QUALITY_SKIP`, `SCOPE_GAP`, `PCT_INCONSISTENT`, `STATUS_CONTRADICTION`, `POST_GO_LIVE_HEALTH`, `INSUFFICIENT_DATA` (rule tak dikenal di akhir). Dipakai di `assess.py` dan `views.py`. Finding teratas menjadi "Masalah utama" di papan — mis. PRJ-003 menampilkan "seharusnya sudah selesai, tidak ada kabar" alih-alih "persentase tidak cocok".

### Text signals (FR-8)

Fungsi pure `text_signals(updates) -> list[{update_id, phrases}]`.

- **Frasa:** `hold`, `error`, `dicek kembali`, `dilewati`, `menunggu`, `belum dapat`, `terbatas`.
- **Tanpa penjaga negasi:** frasa dipilih cukup spesifik sehingga kalimat kabar baik ("tidak/belum ada kendala") tidak cocok sama sekali. Penjaga negasi sempat dirancang, tetapi terbukti tidak berpengaruh (mutation test Fase 3) sehingga dihapus. Perlu ditambahkan kembali jika kata umum seperti `kendala` masuk daftar.
- Pencocokan case-insensitive dan **kata utuh** (`\b…\b`), sehingga "threshold" tidak cocok dengan "hold". Frontend memakai aturan yang sama untuk `<mark>`.
- Hasilnya dipakai untuk **(a)** seksi "Pesan yang perlu dibaca" di detail dan **(b)** `<mark>` di "Riwayat aktivitas". **Tidak menjadi finding dan tidak memengaruhi attention.**

Hasil yang diharapkan pada dataset (diverifikasi saat audit, 0 false positive):

| Update | Project | Frasa |
|---|---|---|
| UPD-006 | PRJ-005 | belum dapat |
| UPD-011 | PRJ-004 | dilewati |
| UPD-012 | PRJ-001 | dicek kembali |
| UPD-013 | PRJ-002 | error |
| UPD-016 | PRJ-005 | menunggu |
| UPD-017 | PRJ-002 | belum dapat |
| UPD-019 | PRJ-001 | hold, menunggu |
| UPD-022 | PRJ-002 | terbatas |

**Kenapa tidak memakai LLM?** Kesimpulan harus deterministik, bisa diaudit, dan bisa dijalankan offline tanpa API key. Kandidat penggunaan LLM ke depan adalah *ekstraksi* sinyal dari pesan bebas (menggantikan daftar frasa), yang hasilnya tetap ditampilkan sebagai sinyal dengan kutipan sumber.

### Kalimat awam (`summary`, Fase 7a)

Setiap finding menyimpan dua teks: `summary` (satu kalimat awam, tampil di UI utama) dan `explanation` (detail teknis, disembunyikan di "Detail"). Kosakata awam di `assess.py`: `UNIT_PLAIN` (pages → halaman, records → data, …) dan `OBSERVED_PLAIN` (pages → "tercatat di mesin scanner", endpoints → "teruji di sistem customer", …). Test memastikan tidak ada `snake_case`, ID `XX-…`, atau kode status kapital di `summary`.

| Project · rule | `summary` |
|---|---|
| PRJ-002 `PACE_RISK` | Dengan kecepatan sekarang, diperkirakan selesai ±15 Okt — 5 hari setelah deadline (10 Okt). Kapasitas yang diklaim pun tidak cukup. |
| PRJ-002 `REPORTED_VS_OBSERVED` | Laporan PIC (91,500 halaman) lebih tinggi dari yang tercatat di mesin scanner (87,240). |
| PRJ-001 `REPORTED_VS_OBSERVED` | 16.5 meter linear yang dilaporkan selesai belum lolos pengecekan internal. |
| PRJ-005 `REPORTED_VS_OBSERVED` | Dilaporkan 9 endpoint selesai, tetapi belum satu pun yang teruji di sistem customer. |
| PRJ-005 `ENV_NOT_READY` | Belum bisa diuji di sistem customer karena akses koneksinya belum diberikan. |
| PRJ-003 `STALE_REPORT` | Tidak ada kabar dari project ini selama 6 hari. Menurut kecepatan sebelumnya seharusnya sudah selesai ±4 Okt, tetapi belum dilaporkan. |
| `STATUS_CONTRADICTION` | PIC melaporkan "sesuai rencana", padahal ada N masalah serius. |

Perkiraan selesai pada dataset: PRJ-001 ±17 Okt (+2), PRJ-002 ±15 Okt (+5), PRJ-003 ±4 Okt (−16, data basi), PRJ-004 ±18 Nov (+13), PRJ-005 & PRJ-006 tidak diperkirakan.

Istilah dibereskan di sumbernya (Fase 8a): satuan `ML` ditulis "meter linear", "production" ditulis "sistem customer", "go-live" ditulis "mulai dipakai". Istilah yang tetap perlu ada (PIC, endpoint, DMS) dijelaskan di glosarium "Cara membaca" pada UI.

### Kesimpulan (`conclusion`, Fase 8a)

Fungsi pure `assess.conclusion(attention, findings)` dipanggil saat request detail. Tidak disimpan, karena hanya menyusun ulang `summary`/`follow_up` yang sudah ada.

- **Kalimat pembuka sesuai status:** HIGH "Project ini perlu tindakan segera.", MEDIUM "…perlu dipantau.", LOW "Data project ini belum cukup untuk dinilai.", OK "Tidak ada masalah yang ditemukan…".
- **Maksimal 2 `summary` teratas** (selain `STATUS_CONTRADICTION`). Jika ada kontradiksi status, ditambah 'Padahal, PIC masih melaporkan project ini "sesuai rencana".'
- **`first_step`** = `follow_up` dari temuan `BLOCKER`/`SCHEDULE` pertama (hal yang perlu diputuskan), jika tidak ada maka temuan teratas, jika tidak ada temuan maka kosong.

| Project | Langkah pertama |
|---|---|
| PRJ-005 | Eskalasi ke PIC customer… (hambatan didahulukan) |
| PRJ-002 / 001 / 004 | Minta PIC rencana percepatan… |
| PRJ-003 | Minta kabar terbaru dari Andi… |
| PRJ-006 | — |

### Expected output pada dataset (dipakai sebagai test)

| Project | days_rem | hist rate | req rate | pace | Findings | Attention |
|---|---|---|---|---|---|---|
| PRJ-001 | 9 | 8.7 ML/hari | 9.6 | 1.108 | REPORTED_VS_OBSERVED M (318 vs 301.5, selisih = pending), PACE_RISK M | MEDIUM |
| PRJ-002 | 4 | 3,355 p/hari | 6,551 (cap 4,500) | 1.95 | PACE_RISK H, STATUS_CONTRADICTION H, REPORTED_VS_OBSERVED M (91.5k vs 87.2k, belum terverifikasi), EQUIPMENT_DEGRADED M (SCN-B LIMITED) | HIGH |
| PRJ-003 | 14 | 39.4 box/hari | 7.9 | 0.20 | STALE_REPORT M (6 hari), PCT_INCONSISTENT M (94 vs 92) | MEDIUM |
| PRJ-004 | 30 | 1,275 rec/hari | 1,791 | 1.40 | PACE_RISK M (+verify kapasitas), DATA_QUALITY_SKIP M (3,200), PCT_INCONSISTENT M (52 vs 45) | MEDIUM |
| PRJ-005 | 7 | — | — | — | REPORTED_VS_OBSERVED H (9 vs 0 tested), ENV_NOT_READY H, DEADLINE_IMMINENT_BLOCKED H, STATUS_CONTRADICTION H, SCOPE_GAP M (9/10) | HIGH |
| PRJ-006 | — | — | — | — | POST_GO_LIVE_HEALTH INFO (ONLINE, 14 user aktif, 1/22 login gagal) | OK |

Urutan seksi Aktif: PRJ-005 (4 HIGH), PRJ-002 (2 HIGH), lalu MEDIUM berdasarkan `days_remaining` asc: PRJ-001 (9), PRJ-003 (14), PRJ-004 (30). Seksi Selesai: PRJ-006.

> **Catatan threshold:** batas MEDIUM `PACE_RISK` = 1.0 (diputuskan setelah audit putaran 2; sebelumnya 1.1 membuat project dengan rasio 1.0–1.1 berstatus "Aman" walau kolom perkiraan menulis "terlambat"). Batas HIGH 1.5 belum dikalibrasi: PRJ-004 terlambat 13 hari tetapi MEDIUM (rasio 1.40). Selisih reported PRJ-001 4.1% juga di bawah batas HIGH (5%). UI menampilkan angka mentah dan breakdown verified/pending agar management bisa menilai sendiri. Sinyal hold/sengketa klasifikasi (UPD-012, UPD-019) muncul di seksi sinyal.

## 7. API (Django)

`config/urls.py` → `path("api/", include("monitor.urls"))`, `path("admin/", admin.site.urls)`.

Read-only, semua respons via `JsonResponse`, dan hanya method GET (`@require_GET`).

**`GET /api/projects`**
```json
[{ "project_id": "PRJ-002", "project_name": "...", "customer": "...", "project_type": "Document Digitalisation",
   "pic": "Nadia", "is_active": true, "deadline": "2026-10-10", "days_remaining": 4,
   "reported_status": "ON TRACK", "reported_pct": 76.25, "observed_pct": 72.7,
   "attention": "HIGH", "finding_counts": {"HIGH": 2, "MEDIUM": 2},
   "target_unit": "pages", "forecast_finish": "2026-10-15T18:17:…+07:00", "forecast_delay_days": 5,
   "last_activity_at": "…", "as_of": "2026-10-06T17:00:00+07:00", "headline": "<summary finding teratas>" }]
```
Sudah terurut (§6), dengan `project_id` sebagai pemecah seri supaya urutan selalu sama. Frontend memisahkan seksi berdasarkan `is_active`.

**`GET /api/projects/<project_id>`**
```json
{ "project": { ...semua field master },
  "metrics": { ...ProjectMetrics },
  "stages": [{"label": "developed", "value": 9}, {"label": "configured", "value": 9},
             {"label": "production tested", "value": 0}, {"label": "target", "value": 10}],
  "findings": [{ "rule": "PACE_RISK", "severity": "HIGH", "category": "SCHEDULE",
                 "summary": "Dengan kecepatan sekarang, diperkirakan selesai ±15 Okt — …", "explanation": "...", "verify": "...", "follow_up": "...",
                 "evidence": [{"ref_type": "production", "ref_id": "SCAN-BETA-001"}] }],
  "conclusion": { "text": "Project ini perlu tindakan segera. Dengan kecepatan sekarang, …",
                  "first_step": "Minta Nadia rencana percepatan …" },
  "signals": [{ "update_id": "UPD-013", "phrases": ["error"], "text": "..." }],
  "timeline": [{ "ts": "...", "kind": "update|production", "ref_id": "...",
                 "source": "OPERATOR · Operator 1", "text": "...", "hints": ["error"],
                 "raw": {...} }] }
```

- `stages` hanya diisi untuk project dengan `integration_snapshot`, selain itu `[]`.
- Id tidak dikenal **atau tidak valid** (di luar `[\w-]{1,20}`, mis. karakter NUL yang sebelumnya membuat Postgres error 500) → `404 {"error": "not found"}`.
- Jumlah query konstan: list = 2 (join metrics + prefetch findings, berapa pun jumlah project; dikunci test dengan 100 project), detail = 4 (diukur, tidak dikunci test).
- Timeline dirakit di view (gabungan `ProjectUpdate` + `ProductionRecord`, diurutkan berdasarkan `(timestamp, ref_id)` sehingga urutan stabil saat waktunya sama). `raw` berisi data asli dengan timestamp WIB. Untuk production record, `text` adalah ringkasan teknis payload; UI memakai ringkasan awam dari `format.js`.
- Query: `select_related("metrics")` + `prefetch_related("findings")` di list view untuk menghindari N+1.

## 8. Frontend (Vite + React) — "Papan status" untuk orang awam (Fase 7b, didesain ulang di Fase 8b)

- **Dev:** `npm run dev` → `http://localhost:5173`. `vite.config.js` mem-proxy `/api` ke `http://127.0.0.1:8000`.
- **State:** `useState` di `App.jsx` (list project + `openId`). `location.hash` adalah sumber kebenaran: `openId` dibaca dari hash pada `hashchange`, dan navigasi dilakukan dengan link `href="#PRJ-002"`, sehingga link bisa dibagikan dan tombol back browser bekerja. Tanpa router, tanpa state library.

**Gaya visual "dashboard" (Fase 9, menggantikan gaya bersih & modern Fase 8b):**
- **Kerangka:** sidebar gelap (`#0F172A`, 232px) hanya berisi logo dan satu menu **Dashboard** (tetap aktif di halaman detail; membuka detail tidak menambah menu, posisinya terlihat dari breadcrumb). Daftar project **sengaja tidak** ada di sidebar karena tidak muat untuk ribuan project; daftar ada di tabel. **Navbar atas** (sticky, putih): judul halaman (dan breadcrumb *Dashboard / nama project* di detail) di kiri, chip tanggal data di kanan. Konten di kanvas abu-abu muda (`#F1F5F9`) dengan **kartu putih** (sudut 10px, garis `#E2E8F0`, bayangan tipis). Di ≤ 960px sidebar menjadi bar atas berisi logo saja.
- **Font Plus Jakarta Sans** (400/600/700) dibundel lewat `@fontsource`, tanpa internet. Ukuran dasar 15px (padat seperti dashboard), tanpa serif.
- **Palet:** teks `#0F172A`/`#334155`/`#576476`, status merah `#B91C1C`, oranye tua `#A14309`, hijau `#15803D` (masing-masing dengan latar badge muda), aksen `#1D4ED8`. Ada versi gelap via `prefers-color-scheme`. **Semua warna teks ≥ 4.5:1 (WCAG AA)** di kartu, kanvas, badge, highlight, dan sidebar, terang maupun gelap (dihitung sebelum dipakai).
- Status ditulis sebagai **badge** (titik + teks): **Perlu tindakan** (HIGH), **Pantau** (MEDIUM), **Perhatikan** (LOW), **Aman** (OK). Tidak pernah hanya warna. Artinya dijelaskan di *Cara membaca*.
- Angka `tabular-nums` agar kolom lurus. Dua bar progress dalam satu baris selalu mulai sejajar (kolom label lebar tetap).

**Halaman Dashboard (urutan dari atas):**
1. **Navbar:** judul *Dashboard* di kiri, chip *"Data per Selasa, 6 Oktober 2026, 17.00 WIB"* di kanan.
2. **Kartu pengantar (`Intro`)**, selalu tampil: aplikasi ini membandingkan apa yang dilaporkan penanggung jawab (PIC) dengan apa yang benar-benar tercatat di sistem produksi. Lalu panel **"Cara membaca dashboard ini"** (`<details>`, bisa dibuka dengan keyboard) berisi arti 4 status, legenda dua bar progress, cara hitung perkiraan selesai, seberapa baru datanya, dan **glosarium** (PIC, Tercatat di sistem, Perkiraan selesai, Meter linear, Endpoint, Sistem customer, DMS).
3. **Kartu KPI:** *Total project* (+ jumlah yang sedang berjalan), *Perlu tindakan*, *Perlu dipantau*, *Data belum cukup* (hanya jika ada), *Aman*, masing-masing dengan arti singkatnya.
4. **Kartu Perlu tindakan hari ini:** project aktif berstatus HIGH, masing-masing dengan nama, penanggung jawab + customer, alasan satu kalimat (`headline`), dan tombol "Lihat penjelasan →".
5. **Semua project:** tabel dalam kartu (di bawah).

**Istilah ("?"):** komponen `Term` menampilkan tombol "?" di sebelah label kunci (header kolom Progress & Perkiraan selesai, label *Laporan PIC* / *Tercatat di sistem*, judul *Jadwal & perkiraan selesai*, *Tahapan endpoint*). Enter membuka, Escape menutup, dan `aria-expanded` / `aria-controls` dipasang. Penjelasan memakai `position: fixed` yang dihitung dari posisi tombol dan dijepit di dalam layar (buka ke atas jika dekat bawah layar), supaya tidak terpotong kartu atau keluar layar; tertutup saat halaman di-scroll. Tombol "?" **tidak** ditaruh di dalam baris papan, karena baris adalah link dan tombol di dalam link tidak valid. Istilah juga dibereskan di sumber (backend): meter linear, sistem customer, mulai dipakai. Jenis project diterjemahkan (*Digitalisasi dokumen*, *Penataan arsip*, …).

**Tabel (`ProjectBoard`)** — judul *Semua project*, satu baris per project, kartu *Sedang berjalan* dan *Sudah selesai* (dengan jumlah):

| Kolom | Isi |
|---|---|
| Project | nama + PIC + customer |
| Status | badge Perlu tindakan / Pantau / Aman |
| Progress | dua bar tipis: *laporan PIC* vs *tercatat di sistem* (%) |
| Perkiraan selesai | ±tanggal + "N hari terlambat" (merah) jika lewat deadline, "tepat di hari deadline", "sebelum deadline", atau "seharusnya sudah selesai" jika perkiraan sudah lewat tetapi tidak ada laporan; "tidak dapat diperkirakan" jika tak ada data kuantitas; "Selesai" untuk project selesai |
| Deadline | tanggal + nama hari + sisa hari |
| Masalah utama | `headline` (= `summary` finding teratas) |

**Detail (`ProjectDetail`):**
Setiap bagian adalah kartu.
1. Kartu header: jenis project (Bahasa Indonesia), judul, badge status, penanggung jawab (PIC), deadline, status yang dilaporkan.
2. **Kesimpulan** (Fase 8b): paragraf `conclusion.text` + *Langkah pertama* (`conclusion.first_step`), di kartu dengan garis aksen kiri, langkah pertama di kotak biru muda.
3. **Jadwal & perkiraan selesai** dan **Dilaporkan vs tercatat** berdampingan (2 kolom, ≥ 1100px). **Garis waktu:** `Mulai ── Hari ini ── Deadline ┄┄ Perkiraan selesai` (perkiraan merah jika lewat deadline).
4. **Dilaporkan vs tercatat di sistem:** dua bar besar + angka + kapan masing-masing dicatat; funnel tahapan untuk integrasi.
5. **Masalah** (bernomor, `summary`) — tiap masalah punya tombol *"Lihat bukti & detail"* yang membuka evidence (label awam: "Pesan Nadia (PM) · 6 Okt 08.10", "Log mesin scanner · 5 Okt 23.59") dan detail teknis (`explanation`, nama rule, ID).
6. **Yang perlu dilakukan:** follow-up + hal yang perlu dikonfirmasi.
7. **Pesan yang perlu dibaca** (text signals) dan **Riwayat aktivitas** (timeline dengan nama sumber awam; data mentah bisa dibuka).

**Navigasi & responsive** (diputuskan saat implementasi — lihat catatan):
- Di **semua ukuran layar**, papan dan detail adalah dua halaman: `#` = papan, `#PRJ-xxx` = detail; kembali lewat breadcrumb *Dashboard* di navbar atau menu *Dashboard* di sidebar; tombol back browser bekerja.
- > 1500px: tabel 6 kolom penuh (sidebar memakan 232px).
- 960–1500px: kolom "Masalah utama" pindah ke baris sendiri di bawah setiap project.
- ≤ 1100px: Jadwal dan Dilaporkan vs tercatat di detail menjadi satu kolom.
- ≤ 960px: sidebar menjadi bar atas; setiap baris tabel menjadi blok bertumpuk dengan label di atas nilai (header tabel beserta tombol "?"-nya disembunyikan; penjelasannya tetap ada di *Cara membaca*).
- < 680px: kartu KPI 2×2, *Cara membaca*, "Dilaporkan vs sistem", dan "Yang perlu dilakukan" menjadi satu kolom.

> **Catatan:** rancangan awal menaruh papan dan detail berdampingan di desktop. Saat dibangun, 6 kolom papan (inti desain "Papan status") tidak muat di kolom kiri ±420px, sehingga desktop pun memakai pola dua halaman. Lebih sedikit kode, satu pola navigasi untuk semua layar.

**Garis waktu jadwal:** posisi titik proporsional terhadap tanggal; label *Mulai* & *Deadline* di atas garis, *Hari ini* di bawah, *Perkiraan selesai* di baris bawah kedua (tidak pernah menimpa "Hari ini" — sempat bertumpuk di PRJ-003 dan PRJ-002 layar 400px). Segmen deadline → perkiraan diberi garis putus merah jika terlambat.

- **Keyboard:** tombol *"Lewati ke konten"* muncul pada Tab pertama dan memindahkan fokus melewati sidebar (WCAG 2.4.1). Dibuat sebagai tombol, bukan link `#konten`, karena hash dipakai untuk navigasi project.
- **Error state:** fetch gagal → "Backend tidak dapat dihubungi…"; id tidak dikenal → "Project tidak ditemukan".
- **Papan kosong** (belum `ingest`): "Belum ada data project. Jalankan `python manage.py ingest`…". **Record sistem tanpa kosakata awam**: "Catatan sistem (lihat data mentah)."

## 9. Konfigurasi, Error Handling & Keamanan

- `settings.py` membaca `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DATA_DIR`, dan koneksi DB (`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`; default `tata/tata/tata@127.0.0.1:5432`) dari environment. Jika tidak di-set, nilai default dev dipakai. Tidak memakai `python-dotenv`: `.env` di-load dengan `set -a; . ./.env; set +a` atau cukup mengandalkan default.
- `TIME_ZONE = "Asia/Jakarta"`, `USE_TZ = True`. Ingest memakai `make_aware`, sehingga tidak ada warning naive datetime.
- `ingest` gagal dengan pesan jelas (`CommandError`) jika file hilang, JSON rusak, **atau isi data tidak valid** (kolom hilang, tanggal salah format, ID duplikat). Karena ada `transaction.atomic`, data lama tetap utuh. Timestamp yang sudah ber-zona waktu dipakai apa adanya; yang tanpa zona waktu dianggap WIB.
- Field numerik kosong disimpan sebagai `NULL`, dan rule yang membutuhkannya di-skip. `INSUFFICIENT_DATA` (LOW) muncul jika `target` kosong atau tidak ada data observed dari sistem; field kosong lain (mis. `reported_progress_pct`) hanya membuat rule terkait di-skip.
- **Guard secret key:** jika `DJANGO_DEBUG=0` dan `DJANGO_SECRET_KEY` tidak diatur, app menolak start (`ImproperlyConfigured`), karena kunci default ada di repo. Pengaturan HTTPS (HSTS, secure cookie, SSL redirect) **belum** dikonfigurasi; `check --deploy` menyisakan 4 peringatan ini, yang memang di luar scope prototype lokal. Blok `MAILERS` bawaan template dihapus karena app tidak mengirim email.
- `ingest` memberi WARNING jika salah satu file sumber kosong.
- Admin di-register read-only (`has_add/change/delete_permission = False`). Akses admin perlu `createsuperuser` dan bersifat opsional.
- Semua akses data lewat ORM, tanpa raw SQL.

## 10. Testing

`python manage.py test monitor` (Django otomatis membuat lalu menghapus DB `test_tata` di Postgres, sehingga role perlu `CREATEDB`):
- `test_assess.py` — unit test pure function, tanpa DB:
  - `pace_ratio` dengan konvensi §5 (timestamp snapshot, deadline inklusif);
  - severity `PACE_RISK` saat `required > stated_capacity`;
  - temuan `PACE_RISK` muncul **jika dan hanya jika** perkiraan selesai lewat deadline (termasuk rasio 1.0–1.1);
  - boundary threshold;
  - regex kapasitas, dan kapasitas hanya dipakai untuk project ber-unit `pages`;
  - `text_signals`: pesan kabar baik tidak tertangkap, dan frasa dicocokkan sebagai kata utuh;
  - perkiraan tanggal selesai;
  - regresi audit: `DATA_QUALITY_SKIP` hanya snapshot terbaru, record ber-unit berbeda diabaikan, `finding_order` untuk rule tak dikenal;
  - kasus pinggir (audit putaran 2): progress nol → HIGH, tanpa data sistem → LOW, target kosong → LOW, target terlampaui → OK.
- `test_api.py` — `call_command("ingest")` ke test DB, lalu:
  - attention dan rule per project sesuai tabel expected §6;
  - hasil `text_signals` sesuai tabel §6;
  - setiap `Finding.evidence[].ref_id` ada di raw tables;
  - urutan `/api/projects` sesuai §6, dan `/api/projects/PRJ-999` → 404;
  - ingest idempotent, dan data sumber rusak menghasilkan `CommandError` tanpa mengubah data lama;
  - bahasa awam (`PlainLanguageTests`): perkiraan per project, `summary`/`verify`/`follow_up` bebas jargon (regex `JARGON`: snake_case, ID, kode status kapital, dan kata teknis *production / go-live / environment / deployment / snapshot*), headline papan, kalimat kunci.

- `test_fuzz.py` — 500 project acak (seed 42) dengan field kosong, unit berbeda, angka ekstrem, dan semua tipe record: tidak boleh crash; setiap finding punya `summary` tanpa "None" dan evidence yang valid; perkiraan terlambat ⇒ ada `PACE_RISK`/`OVERDUE` dan status bukan "Aman"; project COMPLETED dengan data sistem < 95% target ⇒ HIGH. Saat audit juga dijalankan dengan 10.000 project tanpa crash.
- Audit putaran 3 juga menambahkan: list endpoint tetap 2 query dengan 100 project, id tidak valid → 404, dan perkiraan absurd tidak crash.

- Fase 8a: `conclusion` per project (pembuka, langkah pertama, bebas jargon), dan fuzz memastikan `conclusion` tidak crash dan tanpa "None".

Total **49 test** (31 di `test_assess.py`, 17 di `test_api.py`, 1 di `test_fuzz.py` yang memeriksa 500 project).

**Frontend:** `npm run build` + `npm run lint` harus bersih, ditambah checklist di Implementation Plan Fase 5 dan 7b (dijalankan dengan headless browser selama pengembangan; script-nya tidak disertakan).

## 11. Menjalankan (ringkas, detail di README)

```bash
# database (sekali saja, lihat §1 Setup database)
sudo -u postgres psql -c "CREATE ROLE tata LOGIN PASSWORD 'tata' CREATEDB;" -c "CREATE DATABASE tata OWNER tata;"

# backend
cd backend && python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate && python manage.py ingest
python manage.py runserver            # http://127.0.0.1:8000

# frontend (terminal lain)
cd frontend && npm ci && npm run dev  # http://localhost:5173
```
