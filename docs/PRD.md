# PRD — Project Reality Check

> "Apa yang sebenarnya sedang terjadi?"
> Status: Draft v1 · Tanggal referensi dataset: 2026-10-06

## 1. Problem

Management tata.id menerima informasi kondisi project dari banyak sumber: project master, update dari PM/operator/vendor, dan data dari production system. Sumber-sumber ini sering **tidak konsisten**. Status di master bisa tertulis `ON TRACK`, padahal data produksi, laju kerja, atau blocker teknis menunjukkan hal lain. Management tidak punya waktu membaca semua raw update setiap hari.

Kondisi yang ditemukan di dataset:

| Project | Klaim master | Yang ditunjukkan sumber lain |
|---|---|---|
| PRJ-001 | 318 ML, ON TRACK | Yang VERIFIED baru 301.5 ML. Ada sengketa klasifikasi dan sebagian box di-hold. |
| PRJ-002 | 91,500 pages, ON TRACK | Log scanner 87,240. Laju yang dibutuhkan sekitar 2x kapasitas, dan 1 scanner LIMITED. |
| PRJ-003 | 94% | Hitungannya 92%. Tidak ada update selama 6 hari. |
| PRJ-004 | 52% | Hitungannya 45%. 3,200 record dilewati diam-diam. |
| PRJ-005 | 90% | 0 endpoint teruji di production, koneksi NOT_CONFIGURED. |
| PRJ-006 | COMPLETED | Konsisten, sistem ONLINE dan sudah dipakai. |

## 2. Goal

Management dapat menjawab enam pertanyaan berikut dalam waktu kurang dari 1 menit per project:

1. Project apa saja yang sedang berjalan?
2. Project mana yang perlu perhatian sekarang?
3. Mengapa project tersebut perlu perhatian?
4. Evidence apa yang mendasari kesimpulan tersebut? (bisa ditelusuri ke record sumber)
5. Informasi mana yang perlu diverifikasi?
6. Apa yang perlu di-follow up?

### Non-goals
- Bukan alat input atau edit data project. Prototype bersifat read-only terhadap sumber.
- Tidak ada autentikasi, multi-user, atau notifikasi.
- Tidak menggantikan judgement PM. Sistem memberi **sinyal beralasan**, bukan vonis.
- Tidak melakukan NLP atau LLM untuk memahami pesan bebas (lihat Tech Spec §6).

## 3. User

**Management / Head of Operations.** Memantau banyak project lintas jenis pekerjaan. Butuh ringkasan cepat, tetapi tetap bisa "drill down" ke bukti asli agar bisa menantang PIC dengan data.

## 4. User Stories

| ID | Sebagai management, saya ingin… | Supaya… |
|---|---|---|
| US-1 | melihat semua project dalam satu daftar yang diurutkan berdasarkan tingkat perhatian | tahu mana yang dibuka duluan |
| US-2 | melihat angka *reported* vs angka *observed* dari sistem secara berdampingan | tahu apakah laporan bisa dipercaya |
| US-3 | membaca alasan tiap flag dalam satu kalimat | tidak perlu menghitung sendiri |
| US-4 | klik sebuah alasan dan melihat record sumbernya (update_id / source_record_id) | bisa memverifikasi dan mengutip bukti ke PIC |
| US-5 | melihat timeline gabungan update manusia dan data sistem per project | memahami urutan kejadian |
| US-6 | melihat daftar "perlu diverifikasi" dan "saran follow-up" | tahu tindakan konkret berikutnya |

## 5. Functional Requirements

| ID | Requirement | Prioritas |
|---|---|---|
| FR-1 | Import ketiga file sumber (CSV, CSV, JSON) ke storage tanpa mengubah file asli. | Must |
| FR-2 | Menghitung metrik turunan per project: progress terhitung, progress observed, laju historis, laju yang dibutuhkan, sisa hari, umur update terakhir. | Must |
| FR-3 | Menjalankan rule engine yang menghasilkan *findings*. Setiap finding berisi kode, severity, penjelasan, dan **referensi evidence**. | Must |
| FR-4 | Menentukan *attention level* per project (`HIGH` / `MEDIUM` / `LOW` / `OK`) dari findings-nya. | Must |
| FR-5 | Papan *Semua project* dipisah menjadi **Sedang berjalan** dan **Sudah selesai**, didahului ringkasan *Perlu tindakan hari ini* (FR-15). Setiap baris berisi nama, PIC, customer, status perhatian, progress laporan PIC vs tercatat sistem, perkiraan selesai, deadline, dan masalah utama. | Must |
| FR-6 | Halaman detail project: perbandingan reported vs observed (beserta timestamp masing-masing), findings + evidence, timeline, item verifikasi, dan saran follow-up. | Must |
| FR-7 | Evidence dapat diklik dan menampilkan raw record aslinya. | Must |
| FR-8 | Bagian **"Pesan yang perlu dibaca"**: update yang mengandung frasa sinyal (mis. "hold", "error", "dicek kembali", "menunggu", dicocokkan sebagai kata utuh) ditampilkan beserta sumbernya. Frasa cukup spesifik sehingga kabar baik ("tidak/belum ada kendala") tidak tertangkap. Bagian ini **tidak** memengaruhi attention level. | Must |
| FR-9 | Data bisa di-reimport ulang dengan satu command (idempotent). | Should |
| FR-10 | Jawaban "Final Question" (maksimal 300 kata) ada di README. | Must |
| FR-11 | **Bahasa awam.** Setiap temuan punya satu kalimat yang bisa dipahami orang awam (tanpa nama rule, nama field, ID sumber, atau kode status). Istilah teknis, angka mentah, dan ID tetap tersedia di bagian "Detail". | Must |
| FR-12 | **Perkiraan tanggal selesai** untuk project berbasis kuantitas (jika kecepatan nyata dipertahankan), beserta selisihnya terhadap deadline dalam hari. | Must |
| FR-14 | **Konteks untuk orang awam:** pengantar singkat "aplikasi apa ini" selalu tampil, plus panel *Cara membaca* (arti status, dua angka progress, cara hitung perkiraan, glosarium istilah). | Must |
| FR-15 | **Ringkasan hari ini** di atas papan: project yang perlu tindakan beserta alasan satu kalimat, jumlah per status ditampilkan sebagai kartu KPI (FR-17). | Must |
| FR-16 | **Kesimpulan** di awal halaman detail: paragraf awam (status, maksimal 2 masalah utama) + langkah pertama. | Must |
| FR-17 | **Tampilan dashboard profesional:** sidebar navigasi (ringkasan + daftar project), kartu KPI jumlah per status, tabel dalam kartu, badge status, dan halaman detail berbasis kartu. | Must |
| FR-13 | **Responsive:** papan dan detail adalah dua halaman (via `#hash`) dengan tombol kembali di **semua ukuran layar**; tata letak papan menyesuaikan desktop, tablet, dan HP (≥ 400px). | Must |

## 6. Prinsip Desain

1. **Evidence-first.** Tidak ada kesimpulan tanpa pointer ke record sumber.
2. **Reported ≠ observed.** Angka dari PM dan angka dari sistem ditampilkan berdampingan, bukan digabung.
3. **Deterministik dan bisa dijelaskan.** Rule eksplisit dengan threshold yang terdokumentasi. Hasilnya sama setiap kali dijalankan.
4. **Jujur soal ketidakpastian.** Jika data tidak ada (mis. kapasitas per operator PRJ-004), sistem menyatakan "tidak tersedia", bukan mengarang angka.
5. **Bisa dipahami orang awam.** Tampilan utama memakai kalimat sehari-hari dan tanggal, bukan istilah teknis atau rasio. Detail teknis disembunyikan, bukan dihapus (evidence tetap bisa ditelusuri).
6. **Kecil dan bisa dijalankan.** Backend Django + frontend Vite/React, dengan dependency minimal. Setup dan menjalankan aplikasi cukup beberapa command yang terdokumentasi di README (detail stack di Tech Spec §1).

## 7. Success Criteria (untuk demo)

- PRJ-002 dan PRJ-005 muncul di urutan teratas (`HIGH`).
- PRJ-001 dan PRJ-004 bertanda `MEDIUM` dengan alasan pace dan selisih data. Hold/sengketa klasifikasi PRJ-001 terlihat di bagian sinyal update.
- PRJ-003 ditandai karena data basi dan selisih persentase.
- PRJ-006 `OK`.
- Setiap finding bisa ditelusuri ke minimal satu `update_id` atau `source_record_id`.

## 8. Asumsi Utama

- "Hari ini" = `generated_at` production data = **2026-10-06T17:00:00** (sesuai tanggal referensi di Data Dictionary).
- Angka dari production system lebih dipercaya untuk *quantity* daripada angka di master. Untuk PRJ-001 yang dihitung hanya `VERIFIED`.
- Progress dianggap linier terhadap waktu untuk project berbasis kuantitas (ML, pages, boxes, records). Ini tidak berlaku untuk System Integration dan DMS.
- **Perhitungan laju memakai timestamp snapshot observed**, bukan "hari ini", karena tiap sumber diperbarui pada waktu berbeda (mis. PRJ-003 terakhir 09-30).
- **Deadline bersifat inklusif** (pekerjaan boleh berlangsung sampai 23:59:59 pada tanggal deadline).
- **Hari kalender, bukan hari kerja.** Kalender kerja tiap project tidak tersedia. Catatan: deadline PRJ-002 (10-10) jatuh di hari Sabtu. Jika tim tidak bekerja di akhir pekan, risikonya lebih besar dari yang dihitung.
- **Laju historis adalah dasar penilaian pace.** Kapasitas harian yang disebut PM (PRJ-002: 4,500 halaman/hari) hanya *klaim* dan dipakai sebagai skenario terbaik, bukan dasar perhitungan.
- Jika angka reported **lebih baru** daripada observed, selisihnya diberi label "belum terverifikasi sistem", bukan "salah".
- Definisi "selesai" untuk endpoint = **sudah teruji di production**. Tahap developed/configured tetap ditampilkan.

## 9. Risiko / Open Questions

- Threshold rule (mis. "basi" = lebih dari 3 hari) adalah pilihan saya, bukan standar tata.id. Nilainya perlu dikalibrasi bersama management.
- Untuk PRJ-005, master mencatat 9/10 tetapi tidak ada sumber yang menjelaskan endpoint ke-10. Ini dijadikan item verifikasi.
- Frasa sinyal di pesan bisa menghasilkan false positive. Karena itu sinyal hanya ditampilkan untuk dibaca dan tidak memengaruhi attention level.
- **Batas HIGH untuk keterlambatan (rasio 1.5) belum dikalibrasi.** PRJ-004 diperkirakan terlambat 13 hari tetapi hanya MEDIUM (rasio 1.40), sama dengan PRJ-001 yang terlambat 2 hari. Batas MEDIUM sengaja 1.0 (setiap perkiraan terlambat menjadi temuan) supaya status konsisten dengan kolom perkiraan selesai. UI menampilkan tanggal perkiraan dan jumlah hari terlambat agar management bisa menilai sendiri.
