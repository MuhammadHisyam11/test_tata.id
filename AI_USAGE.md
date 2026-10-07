# AI Usage Disclosure

## 1. Tools Used

- **Claude Code** (model Claude Opus 5.5), dipakai lewat CLI di terminal sepanjang pengerjaan.

## 2. What I Used AI For

- **Analisis requirements:** membaca dan merangkum keenam file assessment, lalu mengidentifikasi inkonsistensi antara project master, update, dan production data.
- **Perencanaan:** menyusun draft PRD, Tech Spec, dan Implementation Plan (`docs/`), lalu mengaudit dokumen tersebut terhadap data asli.
- **Code generation:** hampir seluruh kode backend, frontend, dan test ditulis oleh AI, fase demi fase mengikuti Implementation Plan.
- **Testing & debugging:** menulis test, menjalankan *mutation check*, dan memverifikasi UI dengan headless browser.
- **Dokumentasi:** draft README (termasuk draft jawaban Final Question) dan file ini.

## 3. AI-Generated Work

Secara jujur: **sebagian besar kode dan dokumen dihasilkan oleh AI.** Peran saya adalah menentukan arah dan keputusan (lihat §6), mereview setiap fase sebelum lanjut, serta menolak atau mengubah usulan.

| Area | File |
|---|---|
| Dokumen perencanaan | `docs/PRD.md`, `docs/TECH_SPEC.md`, `docs/IMPLEMENTATION_PLAN.md` |
| Setup & ingest | `backend/config/settings.py` (penyesuaian), `monitor/models.py`, `monitor/admin.py`, `monitor/management/commands/ingest.py` |
| Rule engine | `monitor/assess.py` (metrik, 13 rule, text signals, kalimat awam, perkiraan selesai, kesimpulan), `monitor/services.py` |
| API | `monitor/views.py`, `monitor/urls.py`, `config/urls.py` |
| Test | `monitor/tests/test_assess.py`, `monitor/tests/test_api.py`, `monitor/tests/test_fuzz.py` |
| Frontend | `frontend/src/**` (dari template Vite React; boilerplate dihapus; didesain ulang di Fase 7b, 8b, dan 9 atas permintaan saya) |
| Dokumentasi | `README.md` (termasuk draft Final Question), `AI_USAGE.md` |

## 4. Review & Modification

Pengerjaan dibagi per fase. Di akhir setiap fase, AI menjalankan kriteria "Done ketika" dari Implementation Plan dan menjelaskan hasilnya, lalu saya mereview sebelum mengizinkan fase berikutnya.

Verifikasi yang dilakukan, dan apa yang ditemukan:

- **Audit dokumen sebelum coding.** Angka di Tech Spec dihitung ulang terhadap data. Ditemukan bahwa hasil PRJ-002 (HIGH vs MEDIUM) bergantung pada konvensi hitung hari yang belum ditulis di mana pun, sehingga konvensinya ditetapkan dan dijadikan asumsi tertulis.
- **Fase 1 (ingest):** jumlah row 6/23/12, ingest idempotent, timestamp tersimpan +07:00, pesan error saat folder data salah.
- **Fase 2 (rule engine):**
  - Output dicocokkan dengan tabel expected Tech Spec §6, dan hasilnya cocok untuk 6 project.
  - Semua evidence divalidasi ada di raw tables.
  - Setiap explanation dibaca manual. Ditemukan dan diperbaiki: angka 301.5 ML terbulatkan menjadi "302" (menyesatkan, padahal selisih 16.5 ML adalah inti temuan PRJ-001), serta dua kalimat yang mengklaim hal yang tidak dicek kode.
- **Fase 3 (test):** *mutation check*, yaitu logika `assess.py` dirusak satu per satu untuk memastikan test gagal. Tiga dari empat perubahan tertangkap. Yang keempat (penghapusan "penjaga negasi" pada sinyal teks) tidak tertangkap. Ternyata kode itu tidak pernah berpengaruh, sehingga dihapus.
- **Fase 4 (API):** dua assertion test yang ditulis AI ternyata salah (jumlah update PRJ-005, urutan timeline saat timestamp sama). Kodenya benar; ekspektasinya dikoreksi setelah dicek ke data.
- **Fase 5 (UI):** checklist dijalankan dengan headless Chromium, mencakup:
  - urutan daftar dan enam seksi detail;
  - 16/16 chip evidence menemukan sumbernya;
  - layar 400px dan error state.

  Dari screenshot ditemukan format angka tercampur (`91.500` di UI vs `4,500` di teks backend), lalu diseragamkan.

- **Fase 7a (bahasa awam + perkiraan selesai):** kalimat `summary` dibaca satu per satu. Lagi-lagi ditemukan klaim yang tidak dicek kode ("belum ada keputusan penanganannya") dan dihapus. Test "kalimat bebas jargon" awalnya **tidak** menangkap `SCN-B LIMITED` (dibuktikan dengan mutation), lalu polanya diperluas.

- **Fase 7b (redesign UI):** checklist dijalankan dengan headless browser di 3 ukuran layar (22/22). Dari review screenshot ditemukan dan diperbaiki: "Masalah utama" yang kurang penting di PRJ-003/004, label jadwal bertumpuk (percobaan pertama memakai jarak persen ternyata masih bertumpuk di layar 400px, lalu diganti pendekatan yang lebih sederhana), timestamp data mentah dalam UTC, dan teks tindak lanjut yang masih berjargon. Rancangan "papan + detail berdampingan di desktop" tidak dipakai karena 6 kolom papan tidak muat.

- **Audit pasca-7b:** audit mendalam kode backend & frontend, ditambah agent AI terpisah yang mengecek kesesuaian dokumen dengan kode. Ditemukan 2 bug nyata (temuan `DATA_QUALITY_SKIP` bisa dobel; React key bentrok) dan beberapa titik rapuh (frasa dicocokkan sebagai potongan kata, kapasitas berlaku untuk semua unit, rule `UNIT_MISMATCH` di dokumen yang tidak pernah dibuat, traceback mentah saat data rusak, pembulatan 79.5% → 80%). Semua diperbaiki dengan test (38 test). Dokumen yang tidak sesuai kode (jumlah rule, contoh API, nama seksi UI, FR-13) disinkronkan.
- **Audit putaran 2 (kasus pinggir):** rule engine di-probe dengan project fiktif yang tidak ada di dataset. Ditemukan alarm terlewat yang serius: **project tanpa progress sama sekali dinilai "Aman"**. Juga ditemukan: data/target kosong tidak ditandai, dan urutan papan tidak deterministik. Semua diperbaiki dengan test (42 test). Pelajaran: test yang hanya memakai dataset asli tidak menangkap kasus seperti ini. Pemeriksaan dokumen putaran ini juga menemukan klaim keliru yang bertahan sejak draft pertama dokumen buatan AI, termasuk di draft jawaban Final Question: "PRJ-001 bisa bergeser ke LOW". Ini tidak mungkin, karena PRJ-001 juga punya temuan MEDIUM lain. Klaimnya sudah dikoreksi.
- **Audit putaran 3 (fuzz, skala, keamanan, aksesibilitas, integritas data):** fuzz test dengan ribuan project acak menemukan crash yang tidak mungkin tertangkap dataset asli. Juga ditemukan: secret key default bisa terpakai di mode non-dev, ID berisi NUL menyebabkan error 500, dan kontras teks abu-abu gagal WCAG AA. Semua diperbaiki (46 test). Satu invariant fuzz yang ditulis AI awalnya terlalu sempit (mewajibkan `PACE_RISK`, padahal project yang sudah lewat deadline ditandai `OVERDUE`); ini kesalahan rumusan test, bukan bug kode.
- **Fase 8 (UX orang awam):** palet warna dihitung kontrasnya (WCAG) sebelum dipakai. Dari review screenshot ditemukan bar progress menyusut jadi ±20px, legenda yang terpecah, label terpotong, dan bar yang tidak sejajar; semua diperbaiki. Satu pengecekan otomatis sempat gagal (14/16 bukti) karena jeda tetap di script terlalu pendek untuk halaman yang lebih panjang; ini masalah script, bukan aplikasi, dan script diubah untuk menunggu dengan kriteria yang lebih ketat.
- **Fase 9 (tampilan dashboard):** dari review screenshot, kolom "Masalah utama" terpotong di layar 1360px setelah sidebar ditambahkan. Pengecekan keyboard juga menangkap bug CSS dari Fase 8b yang sebelumnya lolos: selector `.board-head span:last-child` ikut menyembunyikan tombol "?" di header tabel pada lebar 680–1100px. Pengecekan Fase 8b tidak menangkapnya karena hanya menguji keyboard di 1360px. Keduanya diperbaiki.
- **Audit pasca-Fase 9:** tooltip "?" ternyata terpotong atau keluar layar di 10 tempat. Ini lolos dari semua pengecekan sebelumnya karena tes hanya memastikan tooltip *ada* di DOM, bukan *terlihat*. Tes baru memeriksa keempat sudut tooltip benar-benar terlihat di layar. Ditambah tombol *Lewati ke konten* untuk pengguna keyboard.
- **Cek ulang terhadap requirements:** ditemukan kata "production" yang lolos di teks *Perlu dikonfirmasi* PRJ-005, serta label teknis di riwayat aktivitas. Ini lolos karena test jargon buatan AI hanya mencari kode dan huruf kapital, tidak mencari kata teknis biasa. Test diperluas, dibuktikan gagal dulu, lalu teksnya diperbaiki.

**Cara saya mereview:**

Sebelum menulis kode, saya membuat PRD (*Product Requirements Document*), Tech Spec, dan Implementation Plan di folder `docs/` supaya pengerjaan lebih terstruktur. Dokumen itu saya review dan revisi sampai sesuai, baru kemudian implementasi dimulai. Implementasi dikerjakan bertahap per fase, bukan sekaligus, supaya kesalahan cepat ketahuan.

Menurut saya AI itu seperti Google Maps: ia mencari jalur tercepat, tetapi tidak tahu ada hambatan apa di jalan. Karena itu saya tetap mereview kode dan logika yang dibuat AI. Contohnya:

- Sebelum mulai, saya mengecek dulu apakah requirements membolehkan penggunaan AI.
- Saya menjalankan `python manage.py ingest` sendiri dan mendapat error `ModuleNotFoundError` karena virtual environment belum aktif. Langkah aktivasi venv dan troubleshooting-nya kemudian ditambahkan ke README.
- Saya menilai UI terlalu teknis untuk orang awam, lalu meminta redesign tiga kali: bahasa awam dan perkiraan selesai (Fase 7), konteks dan kesimpulan untuk orang awam (Fase 8), dan tampilan dashboard yang lebih profesional (Fase 9).
- Saya memilih batas keterlambatan 1.0 (opsi a), setelah ditunjukkan bahwa dengan batas 1.1 sebuah project bisa tampil "terlambat" padahal statusnya "Aman".
- Saya melihat bahwa daftar project di sidebar tidak akan muat untuk ribuan project, sehingga daftar itu dikeluarkan dari sidebar.

## 5. One Example I Changed or Rejected

**AI mengusulkan stack Python stdlib (`http.server`) + SQLite + satu file HTML, tanpa dependency. Saya menolaknya dan memilih Django + PostgreSQL + Vite/React.**

Usulan AI masuk akal untuk prototype ±4 jam (nol dependency, satu command). Namun saya memilih stack lain karena saya sudah terbiasa dengan Django, PostgreSQL, dan Vite/React. Alasannya:

1. Lebih hemat waktu dalam timebox ±4 jam.
2. Strukturnya sudah saya pahami, jadi tidak perlu belajar dari awal dan lebih mudah saya pertanggungjawabkan saat technical discussion.
3. Frontend menjadi aplikasi interaktif berbasis komponen, bukan satu file HTML statis.
4. PostgreSQL dipilih, bukan SQLite bawaan Django, karena merupakan database server sungguhan yang lazim dipakai di production, dan data mentah dari sistem produksi bisa disimpan sebagai `jsonb` yang tetap bisa di-query.

Dampaknya: dokumen ditulis ulang untuk Django/Postgres/Vite, setup database ditambahkan, dan beberapa keputusan turunan muncul (API tanpa DRF, proxy Vite menggantikan CORS, Django Admin read-only untuk inspeksi data).

Contoh lain yang juga bisa dibahas: draft pertama rule `PACE_RISK` membagi laju yang dibutuhkan dengan `max(laju historis, kapasitas klaim PM)`. Saat audit dokumen, terlihat bahwa ini memakai klaim yang belum terbukti sebagai dasar. Saya menyetujui perubahan agar laju historis menjadi dasar, dan kapasitas klaim hanya skenario terbaik.

## 6. My Own Key Decisions

- **Stack:** Django + Vite/React, bukan stdlib + satu file HTML.
- **Database:** PostgreSQL, bukan SQLite.
- **Hasil audit dokumen yang saya setujui:**
  - konvensi waktu (timestamp snapshot, deadline inklusif, hari kalender);
  - kapasitas klaim bukan dasar perhitungan;
  - sinyal teks memakai frasa spesifik dan tidak memengaruhi tingkat perhatian.
- **Cara kerja:** per fase dengan review di setiap fase, bukan generate semuanya sekaligus. Keputusan ini saya ambil setelah mengecek aturan penggunaan AI di brief dan submission guide.
- **RBAC tidak diimplementasikan.** Requirements tidak memintanya, dan brief serta guide menekankan prototype kecil dalam timebox ±4 jam. RBAC disimpan sebagai bahan diskusi pengembangan.
- **Redesign UI setelah review:** saya menilai UI hasil Fase 5 terlalu teknis untuk orang awam dan terlihat seperti template AI. Saya memilih arah "Papan status", istilah teknis disembunyikan di "Detail", perkiraan tanggal selesai sebagai angka utama, dan pola daftar → halaman detail di HP.
- **Batas MEDIUM keterlambatan diturunkan dari 1.1 ke 1.0.** Dengan batas lama, project bisa tampil "terlambat" di kolom perkiraan tetapi berstatus "Aman". Saya memilih konsistensi tampilan (opsi a) daripada mencatatnya sebagai limitation.
- **Redesign UX kedua untuk orang awam (Fase 8):** saya menilai UI masih membingungkan bagi orang awam ("ini aplikasi apa?"). Saya memilih: pengantar + *Cara membaca*, ringkasan *Perlu tindakan hari ini* di atas papan, paragraf *Kesimpulan* di awal detail, dan gaya bersih & modern dengan font Plus Jakarta Sans.
- **Tampilan dashboard (Fase 9):** saya menilai UI masih terasa tidak profesional dan meminta tampilan seperti dashboard. Hasilnya sidebar navigasi, kartu KPI, tabel dalam kartu, dan badge status. Ini membatalkan prinsip "tanpa kartu/pil" dari Fase 7–8.
- **Layout dashboard (Fase 9b):** saya meminta daftar project dikeluarkan dari sidebar karena tidak akan muat untuk ribuan project, dan tanggal data dipindah ke navbar kanan. AI menjelaskan bahwa sidebar tidak menambah beban server (datanya sama dengan tabel); batas sebenarnya adalah API tanpa paginasi, yang kini dicatat sebagai limitation. Lalu saya meminta menu sidebar bernama "Dashboard" dan halaman detail tidak menambah menu di sidebar, cukup breadcrumb. Setelah itu saya minta namanya diseragamkan: judul halaman dan breadcrumb juga "Dashboard".