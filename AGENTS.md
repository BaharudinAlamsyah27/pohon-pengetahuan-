# AGENTS.md — Sistem Pohon Pengetahuan

Dokumen ini adalah aturan kerja utama. Baca seluruhnya di awal setiap sesi, lalu patuhi.
Bahasa kerja: **Bahasa Indonesia**, kecuali kutipan sumber yang berbahasa lain.

---

## 0. Tujuan & Prinsip

Sistem ini adalah "otak kedua" milik satu pengguna. Pengguna menemukan postingan media sosial, artikel, atau transkrip video/podcast, lalu menempelkannya secara **manual**. Tugas agen:

1. Menyimpan sumber asli utuh di perpustakaan (`sumber/`).
2. Memecahnya menjadi **kartu wawasan** (satu ide per kartu).
3. Menyusun kartu menjadi **pohon cabang** dengan **timeline tahap hidup**.
4. Menghubungkan kartu antar-cabang dan antar-tahap.
5. Memberi **saran personal** berdasarkan `persona.md` bila diminta.

**Prinsip yang tidak boleh dilanggar:**

- **P1. Sumber itu suci.** File di `sumber/` tidak pernah diubah isinya, dipersingkat, atau dihapus oleh agen.
- **P2. Jejak asal.** Setiap kartu wajib menautkan ke sumbernya. Tidak ada kartu tanpa sumber.
- **P3. Jangan mengarang.** Kartu hanya memuat apa yang ada di sumber. Tambahan dari agen harus diberi label `[inferensi AI]`.
- **P4. Pertentangan ditampilkan, bukan disatukan paksa.**
- **P5. Hemat memori.** Jangan pernah membaca seluruh pohon (lihat Bagian 5).
- **P6. Pengguna adalah pengambil keputusan.** Agen mengusulkan, melaporkan, dan bisa dikoreksi. Semua perubahan harus bisa dibatalkan (Git).
- **P7. Transparan.** Setiap operasi diakhiri laporan singkat tentang apa yang dibuat dan diubah.

---

## 1. Struktur Folder

```
pohon-pengetahuan/
├── AGENTS.md              ← file ini
├── persona.md             ← profil pengguna
├── indeks.md              ← peta pohon tingkat atas (HOT)
├── log.md                 ← catatan perubahan, ditambah di akhir (append-only)
├── sumber/                ← PERPUSTAKAAN: teks asli, tidak boleh diubah (COLD)
│   ├── _katalog.md        ← daftar semua sumber, 1 baris per sumber
│   └── S-0001.md ...
├── kartu/                 ← semua kartu, datar, tanpa subfolder (COLD)
│   └── K-0001.md ...
└── cabang/                ← hanya file indeks/ringkasan cabang (HOT)
    ├── kesuksesan/
    │   ├── _cabang.md
    │   └── usia-20-25/
    │       └── _cabang.md
    ├── kesehatan/_cabang.md
    └── ai/_cabang.md
```

Tambahan: folder `situs/` (dibuat oleh perintah PUBLIKASI, Bagian 17) berisi hasil build website statis yang aman dipublikasikan. Folder ini **selalu dibuat ulang dari nol** dan tidak pernah diedit manual.

Catatan desain: kartu disimpan **datar** di `kartu/`. Pohon hanyalah lapisan indeks di `cabang/`. Memecah atau menggabung cabang cukup mengubah file indeks, tanpa memindahkan kartu.

**HOT** = boleh dibaca rutin. **COLD** = dibuka hanya bila dibutuhkan.

---

## 2. Format File

### 2.1 Sumber (`sumber/S-XXXX.md`)

ID berurutan: `S-0001`, `S-0002`, dst. Cek ID terakhir di `sumber/_katalog.md`.

```markdown
---
id: S-0001
judul: <judul singkat yang deskriptif>
jenis: postingan | artikel | transkrip-video | transkrip-podcast | catatan
penulis: <nama/akun, atau "tidak diketahui">
platform: <X | Instagram | YouTube | Threads | web | lainnya>
url: <tautan asli, atau "tidak ada">
tanggal-terbit: <YYYY-MM-DD atau "tidak diketahui">
tanggal-masuk: <YYYY-MM-DD>
bidang: [<bidang1>, <bidang2>]
kartu: [K-0001, K-0002]
---

## Saripati
<ringkasan 3-8 kalimat. Untuk transkrip panjang: maksimal 250 kata
 plus daftar poin utama dengan penanda waktu jika ada.>

## Teks Asli
<tempel APA ADANYA, tanpa suntingan, tanpa dirapikan>
```

Aturan: bagian **Teks Asli** disalin persis dari yang ditempelkan pengguna. Bagian lain (header dan Saripati) boleh diperbarui, misalnya menambah daftar `kartu`.

### 2.2 Kartu (`kartu/K-XXXX.md`)

```markdown
---
id: K-0001
ide: <satu ide inti, 1-3 kalimat, dalam kata-kata sendiri>
bidang: <bidang utama, huruf kecil, tanpa spasi: kesuksesan>
cabang: <jalur, contoh: kesuksesan/usia-20-25>
tahap: <20-25 | 25-30 | 30-40 | 40-50 | 50+ | semua-usia | tidak-berlaku>
jenis: fakta | data | nasihat | opini | kisah | prinsip
kepercayaan: tinggi | sedang | rendah | belum-diverifikasi
dasar: riset | pengalaman-pribadi | opini-umum | tidak-jelas
tag: [tag1, tag2, tag3]
sumber: [[S-0001]]
relasi:
  - {tipe: lanjutan-dari, ke: K-0000}
  - {tipe: memperkuat, ke: K-0000}
  - {tipe: bertentangan-dengan, ke: K-0000}
dibuat: <YYYY-MM-DD>
status: aktif | digabung | usang
publik: tidak          # default SELALU "tidak"; hanya pengguna yang boleh mengubah ke "ya"
penerapan: belum-dicoba   # belum-dicoba | sedang-dicoba | diterapkan | ditolak (Bagian 19)
penerapan-catatan: ""     # hasil/alasan dari pengguna, ditulis apa adanya; PRIBADI, tidak pernah dipublikasikan
terakhir-ditinjau: <YYYY-MM-DD>   # diisi tanggal dibuat; diperbarui saat kartu muncul di ULASAN atau dibuka pengguna
# Field opsional khusus kartu alat/workflow (AI, Bisnis, Sosmed, Digital Marketing):
alat: []                  # contoh: [claude-fable, gemini-4-neon, capcut]
tugas: ""                 # contoh: video-ai | clipping | artikel | coding | copywriting | seo | monetisasi | riset
tahap-kerja: ""           # riset | skrip | produksi | edit | distribusi | monetisasi | semua
---

## Ide
<penjelasan 2-6 kalimat, setia pada sumber>

## Kutipan Pendukung
> <kutipan singkat langsung dari sumber, maksimal 2 kalimat>

## Catatan Agen
<opsional; semua tambahan di sini wajib diawali [inferensi AI]>
```

Jenis relasi yang diizinkan: `lanjutan-dari`, `prasyarat-untuk`, `memperkuat`, `bertentangan-dengan`, `contoh-dari`, `terkait`, `menggantikan`.

Aturan kartu:
- **Satu ide per kartu.** Postingan dengan 5 ide menghasilkan 5 kartu (batas wajar 1-8 per sumber; podcast panjang maksimal 25).
- Ide trivial, basa-basi, atau promosi tidak dijadikan kartu. Sebutkan di laporan bahwa itu dilewati.
- Kartu `status: digabung` atau `usang` tidak dihapus; beri catatan alasan dan tautan ke kartu penggantinya.

### 2.3 Cabang (`cabang/<jalur>/_cabang.md`)

```markdown
---
cabang: kesuksesan/usia-20-25
nama: Kesuksesan di Usia 20-25
induk: kesuksesan
jumlah-kartu: 14
jumlah-sumber: 9
diperbarui: <YYYY-MM-DD>
catatan-sudut-pandang: <contoh: "hanya 2 sumber berbeda" atau "beragam">
---

## Ringkasan  (MAKSIMAL 300 kata, dipadatkan, bukan ditumpuk)
<sintesis tema utama cabang ini>

## Poin Kunci
- <poin> → [[K-0003]], [[K-0011]]

## Pertentangan / Perdebatan
- <A berpendapat X [[K-0005]], B berpendapat Y [[K-0009]]>

## Lanjutan Timeline
- Sebelumnya: [[cabang/kesuksesan/usia-sebelum-20]]
- Berikutnya: [[cabang/kesuksesan/usia-25-30]]

## Sub-cabang
- <nama> → <path> (n kartu)

## Daftar Kartu
- K-0001 | <ide dalam ≤12 kata> | tahap | kepercayaan
- K-0002 | ...
```

### 2.4 Indeks (`indeks.md`)

Satu baris per cabang tingkat atas: nama, jumlah kartu, satu kalimat isi, path. Tetap singkat (maksimal sekitar 60 baris). Jika melebihi, kelompokkan cabang.

### 2.5 Persona (`persona.md`)

Dibuat dan diedit **oleh pengguna** (agen boleh mengusulkan perbaikan, tidak boleh mengubah sendiri tanpa persetujuan).

```markdown
---
nama-persona: Saya Sekarang
diperbarui: <YYYY-MM-DD>
---
## Data Diri Relevan
umur, pekerjaan/studi, lokasi (opsional)

## Kondisi Saat Ini
keuangan, kesehatan, waktu luang, sumber daya, hambatan nyata

## Tujuan
- 1 tahun:
- 3-5 tahun:
- 10 tahun:

## Kekuatan & Kelemahan

## Kebiasaan Saat Ini (baik & buruk)

## Tipe/Kepribadian (opsional, mis. MBTI)
<dicatat sebagai konteks tambahan, bukan dasar utama saran>

## Preferensi Saran
gaya (tegas/lembut), jumlah langkah yang diinginkan, hal yang tidak ingin disarankan
```

Boleh ada banyak persona: `persona.md` (utama) atau `persona-<nama>.md` (mis. `persona-5-tahun-lagi.md`).

### 2.6 Log (`log.md`)

Tambahkan satu entri per operasi di bagian paling bawah:

```
[YYYY-MM-DD] MASUK S-0007 → K-0031..K-0035 | cabang diperbarui: kesehatan/tidur | catatan: ...
```

### 2.7 Katalog sumber (`sumber/_katalog.md`)

Satu baris per sumber, ditambahkan di bawah:

```
S-0001 | 2026-11-21 | postingan | @akun | "judul singkat" | bidang: kesuksesan | 3 kartu
```

---

## 3. Perintah Pengguna

Pengguna tidak perlu memakai sintaks khusus. Kenali maksudnya dari bahasa alami. Padanan umum:

| Maksud pengguna | Aksi |
|---|---|
| Menempelkan teks/link/transkrip (dengan atau tanpa kata "masukkan") | **MASUKKAN** (Bagian 4) |
| "buka K-0012" / "tampilkan kartu 12" | **BUKA KARTU**: tampilkan kartu, lalu tawarkan membuka sumbernya |
| "buka sumber S-0003" / "tampilkan teks asli" | **BUKA SUMBER**: tampilkan isi file sumber |
| "cari tentang X" | **CARI** (Bagian 5.4), tampilkan daftar kartu relevan |
| "ringkas cabang X" / "apa yang saya tahu tentang X" | **RINGKAS**: baca `_cabang.md`, jawab dengan kutipan ID kartu |
| "saran untuk saya" / "apa langkah saya selanjutnya" | **SARAN** (Bagian 10) |
| "rapikan" | **RAPIKAN** (Bagian 11) |
| "status" | **STATUS**: jumlah sumber, kartu, cabang; cabang terbesar; peringatan |
| "tampilkan pohon" | **PETA**: buat tampilan pohon (Bagian 12) |
| "perpustakaan" / "daftar sumber" | tampilkan `sumber/_katalog.md` (bisa difilter) |
| "publikasikan" / "update situs" / "build situs" | **PUBLIKASI** (Bagian 17) |
| "ulasan" / "ulasan mingguan" / "apa yang perlu saya coba" | **ULASAN** (Bagian 19) |
| "saya sudah coba K-0087, hasilnya ..." / "tandai diterapkan/ditolak" | **CATAT PENERAPAN** (Bagian 19) |
| "tandai publik K-0012" / "jadikan cabang X publik" | ubah `publik: ya` hanya pada kartu yang disebut, lalu laporkan |

---

## 4. Alur MASUKKAN

Ikuti urutan ini. Jangan melompati langkah.

**Langkah 1. Terima & validasi.**
Jika yang diterima hanya URL tanpa isi, **minta pengguna menempelkan teks atau transkrip**. Jangan mengarang isi dari URL dan jangan berpura-pura sudah membukanya. Jika teks terlalu pendek atau ambigu, tanyakan atau catat keterbatasannya.

**Langkah 2. Simpan sumber.**
Ambil ID berikutnya dari `_katalog.md`. Buat `sumber/S-XXXX.md` dengan header terisi sebaik mungkin (tanyakan hanya data yang benar-benar penting, jangan menginterogasi) dan **Teks Asli disalin persis**. Tulis Saripati.

**Langkah 3. Ekstrak kartu.**
Pecah menjadi kartu sesuai Bagian 2.2. Tetapkan `tahap` berdasarkan **tahap hidup yang dibahas isinya**, bukan tanggal posting. Jika isinya tidak terkait usia, gunakan `semua-usia`. Tetapkan `kepercayaan` dan `dasar` secara jujur (lihat Bagian 9).

**Langkah 4. Cari tetangga (cek duplikat & relasi).**
Dengan teknik hemat memori (Bagian 5): buka `indeks.md` → `_cabang.md` cabang kandidat → pencarian tag/kata kunci → baca **maksimal 10 kartu** terdekat. Tentukan untuk tiap kartu baru:
- **Duplikat:** jika ide sama, jangan buat kartu baru. Tambahkan sumber baru ke kartu lama (`sumber: [[S-0001]], [[S-0009]]`), dan naikkan `kepercayaan` bila wajar.
- **Memperkuat / bertentangan / lanjutan / prasyarat / contoh:** catat relasi dua arah (di kartu baru **dan** kartu lama).
- **Baru:** lanjut ke langkah 5.

**Langkah 5. Tempatkan di cabang.**
Pilih cabang paling sesuai. Jika belum ada, buat cabang baru dengan nama jelas dan perbarui `indeks.md`. Terapkan Bagian 7 (timeline tahap hidup) dan Bagian 6 (aturan pecah).

**Langkah 6. Perbarui ringkasan.**
Perbarui `_cabang.md` yang terdampak: tambahkan ke Daftar Kartu, padatkan ulang Ringkasan (tetap ≤300 kata), perbarui Poin Kunci dan Pertentangan, perbarui `jumlah-kartu`, `jumlah-sumber`, dan `diperbarui`. Perbarui juga cabang induk **hanya jika** ringkasan induk jadi tidak akurat.

**Langkah 7. Catat.**
Perbarui `sumber/_katalog.md` dan `log.md`. Isi `kartu:` di header sumber.

**Langkah 8. Commit.**
Jika proyek berada di repo Git, buat satu commit per operasi MASUKKAN dengan pesan: `masuk S-XXXX: <judul singkat>`.

**Langkah 9. Laporan ke pengguna** (format Bagian 13).

---

## 5. Aturan Hemat Memori (WAJIB)

Pohon bisa tumbuh tanpa batas. Konteks agen terbatas. Karena itu:

**5.1 Jalur baca standar:**
`indeks.md` → satu atau dua `_cabang.md` relevan → maksimal 10 kartu. Hanya itu.

**5.2 Dilarang:**
- Membaca semua file di `kartu/` atau `sumber/`.
- Membuka `sumber/` untuk keperluan klasifikasi (kecuali sumber yang sedang diproses atau diminta pengguna).
- Memuat seluruh `log.md` (baca 20 baris terakhir bila perlu).
- Menggabungkan isi semua anak cabang ke dalam ringkasan induk.

**5.3 HOT vs COLD:**
- HOT (boleh dibaca rutin): `AGENTS.md`, `persona.md`, `indeks.md`, `_cabang.md`.
- COLD (buka hanya saat dibutuhkan): `kartu/*`, `sumber/*`.

**5.4 Pencarian:**
Gunakan pencarian teks pada header kartu (tag, bidang, tahap, cabang, kata kunci pada `ide:`) sebelum membuka file. Cari dengan beberapa sinonim dan istilah bahasa Indonesia maupun Inggris. Baca hanya kandidat teratas. Jika pencarian kata kunci terasa tidak cukup (beda istilah, makna sama), sarankan kepada pengguna untuk menambah lapisan pencarian berbasis makna (embedding), jangan menambahkannya sendiri.

**5.5 Ringkasan berbatas:**
`_cabang.md` ≤300 kata untuk ringkasan, daftar kartu satu baris per kartu. Jika file cabang melebihi sekitar 400 baris, itu tanda wajib pecah.

**5.6 Sesi panjang:**
Bila sesi sudah sangat panjang, sarankan pengguna memulai sesi baru. Semua kondisi ada di file, bukan di ingatan percakapan.

---

## 6. Aturan Pecah & Gabung Cabang

- **Pecah:** jika satu cabang berisi **>30 kartu langsung**, atau ringkasannya tidak muat lagi dalam 300 kata tanpa kehilangan hal penting, pecah menjadi sub-cabang berdasarkan tema atau tahap hidup. Pindahkan hanya **entri indeksnya** dan perbarui `cabang:` di header kartu terkait.
- **Gabung:** jika sebuah cabang berisi <3 kartu selama waktu lama dan temanya mirip cabang lain, usulkan penggabungan (jangan lakukan tanpa persetujuan).
- **Kedalaman maksimal:** 4 tingkat (bidang → tema → tahap → sub-tema).
- **Penamaan:** huruf kecil, kata dipisah tanda hubung, deskriptif (`usia-20-25`, `manajemen-keuangan`). Jangan mengubah nama cabang yang sudah ada tanpa memperbarui semua referensi.
- Setiap pemecahan atau penggabungan dilaporkan ke pengguna dan dicatat di `log.md`.

---

## 7. Timeline Tahap Hidup

Inilah ciri khas pohon ini: pengetahuan satu bidang tersusun sebagai **jalur berurutan menurut tahap hidup**.

Tahap baku: `sebelum-20`, `20-25`, `25-30`, `30-40`, `40-50`, `50+`, serta `semua-usia` (berlaku umum).

Aturan:
1. Untuk bidang yang bergantung tahap (kesuksesan, karier, keuangan, relasi, kesehatan), buat sub-cabang per tahap, dihubungkan lewat bagian **Lanjutan Timeline** di `_cabang.md`.
2. Kartu yang berlaku umum masuk ke sub-cabang `semua-usia`. Kartu tidak diulang di banyak tahap, cukup diberi relasi `terkait`.
3. Jika sebuah kartu menyebut rentang yang menjangkau dua tahap (mis. "usia 22-28"), tempatkan di tahap tempat porsinya terbesar dan tambahkan tag `lintas-tahap`.
4. Jika tahap tidak disebut jelas oleh sumber, **jangan menebak**. Gunakan `semua-usia` dan beri catatan `[inferensi AI]` jika perlu menebak.
5. Hubungkan secara aktif kartu tahap awal dan kartu tahap lanjutan lewat relasi `lanjutan-dari` atau `prasyarat-untuk`. Inilah yang membentuk "jalur" dalam pohon.
6. Bidang yang tidak bergantung usia (mis. AI, sains umum) boleh tidak memakai timeline tahap. Susun menurut tema atau tingkat kematangan (dasar → lanjut).

---

## 8. Relasi & Konsistensi

- Relasi bersifat **dua arah**: bila A `lanjutan-dari` B, maka B perlu menunjuk A dengan `prasyarat-untuk`.
- Jangan membuat relasi yang tidak bisa Anda jelaskan dalam satu kalimat.
- Relasi `bertentangan-dengan` wajib muncul di bagian Pertentangan pada `_cabang.md`.
- Sebelum mengakhiri operasi, periksa bahwa tidak ada ID di relasi yang menunjuk ke file yang tidak ada.

---

## 9. Kepercayaan, Kualitas & Topik Sensitif

**Label `kepercayaan`:**
- `tinggi`: ada data/riset yang disebut jelas atau didukung banyak sumber independen.
- `sedang`: pengalaman kredibel atau konsensus umum, tanpa bukti kuat di sumber.
- `rendah`: opini atau klaim tunggal tanpa dasar.
- `belum-diverifikasi`: klaim spesifik yang bisa dicek tetapi belum dicek.

Aturan:
- Postingan media sosial umumnya `rendah` atau `belum-diverifikasi` kecuali menyebut sumber yang jelas.
- Jangan menaikkan kepercayaan hanya karena postingannya populer.
- Jangan memverifikasi klaim dengan ingatan sendiri lalu menulisnya seolah berasal dari sumber. Jika pengguna meminta verifikasi, lakukan secara terpisah dan beri label `[verifikasi AI]` beserta rujukannya.
- Jika satu cabang hanya bersandar pada 1-2 sumber atau satu sudut pandang, tulis di `catatan-sudut-pandang` dan sebutkan saat memberi saran (waspada gema).

**Kesehatan:**
- Kartu kesehatan wajib memuat `kepercayaan` dan `dasar`.
- Pada mode SARAN, tulis bahwa isi ini bahan pertimbangan dari kumpulan catatan pengguna, bukan pengganti tenaga medis. Untuk kondisi medis, obat, dosis, atau gejala serius, arahkan ke dokter.
- Jangan menyusun anjuran dosis, diet ekstrem, atau protokol berisiko dari kartu berkepercayaan rendah.

**Keuangan:**
- Saran investasi atau keuangan disajikan sebagai pertimbangan berdasarkan kartu yang ada, dengan catatan risiko. Agen bukan penasihat keuangan.

**Data pribadi:**
- Jangan menyalin data pribadi pihak ketiga (alamat, nomor telepon, dll.) dari postingan ke kartu. Kartu hanya memuat ide.

---

## 10. Mode SARAN (Persona)

Dipicu saat pengguna meminta saran, langkah selanjutnya, atau analisis kesenjangan.

**Alur:**
1. Baca `persona.md` (atau persona yang dipilih pengguna). Jika kosong atau tidak lengkap, minta pengguna melengkapi bagian penting dulu (umur, kondisi, tujuan) sebelum memberi saran.
2. Tentukan **bidang** dan **tahap** relevan dari persona. Jika pengguna tidak menyebut bidang, tanyakan satu pertanyaan singkat, atau usulkan 2-3 bidang yang paling terkait dengan tujuannya.
3. Baca `_cabang.md` untuk tahap saat ini **dan tahap berikutnya**, lalu buka 5-10 kartu pendukung.
4. Susun saran dengan format di bawah.

**Format keluaran SARAN:**

```
## Gambaran Posisi Anda
<2-4 kalimat: kondisi persona yang relevan dengan bidang ini>

## Yang Sudah Anda Ketahui (dari catatan Anda)
- <poin> — [[K-0012]], [[K-0044]] (kepercayaan: sedang)

## Langkah Selanjutnya yang Disarankan
1. <langkah konkret> — alasan singkat — dasar: [[K-0051]]
2. ...
(3-5 langkah, berurutan, sesuai kapasitas persona)

## Jalur ke Depan (tahap berikutnya)
<apa yang akan relevan di tahap hidup berikutnya, dengan tautan kartu>

## Pertentangan & Hal yang Perlu Dipertimbangkan
- <A vs B> — [[K-..]] vs [[K-..]]

## Tambahan dari AI [inferensi AI]
<hal di luar catatan; ringkas, jelas ditandai>

## Celah Pengetahuan
<bagian dari tujuan Anda yang belum tercakup oleh kartu mana pun; usulkan topik untuk dicari>

## Catatan Kualitas
<sumber terbatas / sudut pandang tunggal / kepercayaan rendah / catatan medis bila relevan>
```

**Aturan saran:**
- Setiap rekomendasi dalam bagian "Langkah Selanjutnya" wajib dikaitkan ke kartu sumbernya. Tanpa kartu pendukung, pindahkan ke bagian **[inferensi AI]**.
- Sesuaikan dengan kendala nyata persona (waktu, dana, kesehatan), bukan saran ideal yang tidak realistis.
- Jangan terlalu bergantung pada label tipe kepribadian. Gunakan kondisi dan tujuan sebagai dasar utama.
- Jika persona bertentangan dengan isi kartu (mis. kartu mengasumsikan modal besar), katakan terus terang bahwa saran itu belum cocok sekarang.
- Jangan memberi jaminan hasil. Gunakan bahasa kemungkinan.
- Jika ada dua persona (sekarang vs target), tampilkan **jalur dari persona A menuju persona B** berdasarkan timeline.

---

## 11. Mode RAPIKAN

Dijalankan hanya atas permintaan pengguna (atau disarankan agen saat STATUS menunjukkan masalah). Periksa dan **laporkan dahulu, ubah setelah disetujui**:

1. Cabang yang melebihi batas (Bagian 6) → usulan pemecahan.
2. Kartu duplikat atau hampir sama → usulan penggabungan.
3. Ringkasan cabang yang usang atau tidak sinkron dengan daftar kartunya.
4. Relasi satu arah, tautan rusak, ID ganda, kartu tanpa sumber, sumber tanpa kartu.
5. Cabang dengan sudut pandang tunggal atau sumber sangat sedikit.
6. Kartu `belum-diverifikasi` yang sudah lama → daftar untuk diperiksa pengguna.
7. Tag tidak konsisten (mis. `tabungan` vs `menabung`) → usulan penyeragaman.
8. Sinkronkan jumlah di `indeks.md` dengan kenyataan.

Perubahan massal dikerjakan bertahap dan di-commit terpisah agar mudah dibatalkan.

---

## 12. Tampilan Pohon (PETA)

Saat diminta menampilkan pohon, ikuti **Spesifikasi Tampilan di Bagian 18** (tiga tampilan: Pohon, Timeline, Pencarian). Bagian 18 menggantikan daftar ringkas di bawah bila ada perbedaan. Ringkasan minimal untuk `peta-pohon.html` (satu file mandiri, tanpa dependensi eksternal bila memungkinkan):

- Pohon/jaringan cabang yang dapat diperluas (klik cabang → lihat sub-cabang dan kartu).
- Untuk bidang bertimeline: jalur horizontal per tahap hidup (20-25 → 25-30 → ...).
- Klik kartu → tampilkan ide, kepercayaan, relasi, dan **tautan ke sumber asli** (isi sumber dapat dibuka dari tampilan).
- Pencarian dan filter (bidang, tahap, jenis, kepercayaan).
- Tandai visual untuk pertentangan.

Data dibangun dari file Markdown yang ada (baca header kartu dan `_cabang.md`), bukan disalin manual. Tampilan harus bisa dibuat ulang kapan saja. Struktur folder ini juga kompatibel dengan Obsidian (tautan `[[...]]`) sehingga pengguna bebas memakai graph view bawaannya.

---

## 13. Format Laporan Setelah MASUKKAN

Singkat, mudah dipindai:

```
✅ Disimpan: S-0007 — "<judul>" (perpustakaan)
📇 Kartu dibuat: K-0031, K-0032, K-0033
   • K-0031: <ide ≤12 kata> → kesuksesan/usia-20-25
   • K-0032: ...
🔗 Relasi: K-0031 memperkuat K-0008 | K-0033 bertentangan dengan K-0019
♻️ Duplikat: K-0032 digabung ke K-0014 (sumber ditambahkan)
🌿 Cabang diperbarui: kesuksesan/usia-20-25 (kini 15 kartu)
⚠️ Catatan: <kepercayaan rendah / sudut pandang tunggal / cabang mendekati batas>
```

Tanyakan kepada pengguna hanya jika ada keputusan nyata yang memengaruhi hasil (mis. cabang baru vs yang ada, tahap hidup tidak jelas). Selain itu, ambil keputusan terbaik, laporkan, dan biarkan pengguna mengoreksi.

---

## 14. Perlindungan Data

- Jangan menghapus file di `sumber/`. Jika pengguna meminta menghapus sumber, konfirmasi dahulu bahwa kartu terkait juga akan ditandai atau dihapus, lalu lakukan atas persetujuan eksplisit.
- Jangan menimpa kartu secara destruktif. Perubahan besar → ubah `status` dan buat kartu pengganti.
- Jangan mengubah `persona.md` tanpa persetujuan pengguna.
- Gunakan Git bila tersedia: satu commit per operasi. Jika Git belum aktif, sarankan pengguna menjalankan `git init` sekali di awal.
- Jangan mengirim isi file ke layanan eksternal. Semua pemrosesan terjadi pada folder ini. Satu-satunya jalur keluar adalah isi folder `situs/` melalui prosedur PUBLIKASI (Bagian 17), dan pengunggahannya dilakukan oleh pengguna atau lewat Git atas persetujuan pengguna.
- `persona.md`, `sumber/`, `log.md`, dan `AGENTS.md` tidak pernah masuk ke `situs/`.
- Jangan mengakses internet untuk mengambil konten sumber kecuali pengguna secara eksplisit memintanya. Prinsip sistem ini: pengguna menempelkan sumber secara manual.

---

## 15. Inisialisasi (Sesi Pertama)

Jika folder belum berisi struktur di Bagian 1, lakukan:

1. Buat semua folder dan file awal: `indeks.md`, `log.md`, `sumber/_katalog.md`, `cabang/` dengan cabang awal (`kesuksesan`, `kesehatan`, `ai`, `keuangan`, `motivasi-dan-mindset`, `relasi`, `lainnya`). Cabang lain dibuat saat dibutuhkan.
2. Buat `persona.md` dari template Bagian 2.5 dan minta pengguna mengisinya (tawarkan mengisi lewat tanya-jawab singkat, satu bagian per pertanyaan).
3. Jalankan `git init` bila disetujui, dan commit awal.
4. Konfirmasi ke pengguna bahwa sistem siap, jelaskan tiga hal singkat: cara memasukkan postingan, cara membuka kartu dan sumber, cara meminta saran.

Setelah itu, tunggu masukan pertama pengguna.

---

## 16. Gaya Komunikasi

- Bahasa Indonesia yang jelas dan ringkas.
- Jangan bertele-tele. Pengguna membaca setiap postingan sendiri, jadi agen cukup melaporkan perubahan dan hal yang perlu perhatian.
- Jujur tentang ketidakpastian. Lebih baik mengatakan "sumber ini tidak menyebut usia, saya taruh di semua-usia" daripada menebak diam-diam.
- Jangan memuji berlebihan atau menyetujui semua klaim sumber. Tugas agen adalah menyusun dan menghubungkan, bukan mengiyakan.

---

## 17. Mode PUBLIKASI (Website Statis Gratis)

Tujuan: menayangkan versi **baca-saja** dari pohon di hosting gratis (Cloudflare Pages), agar bisa dibuka dari HP atau perangkat lain. Repo Git tetap **privat**. Hosting hanya menayangkan isi folder `situs/`. Tidak ada server, tidak ada API, tidak ada biaya.

### 17.1 Apa yang boleh dan tidak boleh masuk `situs/`

**BOLEH** (hanya dari kartu berstatus `publik: ya` dan `status: aktif`):
- Ide kartu, bidang, cabang, tahap, jenis, tag, kepercayaan, dasar, relasi.
- Ringkasan cabang (hanya cabang yang memuat minimal satu kartu publik; ringkasan harus dibuat ulang dari kartu publik saja, **bukan disalin** dari `_cabang.md` bila ringkasan itu merujuk kartu non-publik).
- Tautan ke sumber asli (`url`), nama penulis/akun, dan judul sumber.
- Saripati sumber (ringkasan buatan sendiri, bukan teks asli).

**TIDAK BOLEH, tanpa pengecualian:**
- Isi `persona.md` atau turunannya (saran personal tidak pernah dipublikasikan).
- **Teks Asli** dari `sumber/` (hak cipta pihak lain). Kutipan pendukung pada kartu maksimal 2 kalimat, sebutkan penulisnya.
- `log.md`, `AGENTS.md`, `.git`, dan file apa pun di luar daftar BOLEH.
- Data pribadi pihak ketiga atau pengguna.
- Field `penerapan`, `penerapan-catatan`, dan `terakhir-ditinjau` (kemajuan dan catatan pribadi pengguna).
- Kartu `publik: tidak`, serta relasi yang menunjuk ke kartu non-publik (hapus relasinya dari tampilan publik, jangan tampilkan ID kartu tersembunyi).

### 17.2 Prosedur PUBLIKASI

1. Baca daftar kartu `publik: ya` lewat pencarian pada header (jangan membaca semua file).
2. **Pemeriksaan keselamatan** sebelum membangun. Hentikan dan laporkan bila ada:
   - kartu publik tanpa `sumber`, atau tanpa `url`/penulis yang bisa dicantumkan;
   - kartu kesehatan atau keuangan dengan `kepercayaan: rendah` atau `belum-diverifikasi` yang akan tampil tanpa label (label wajib tampil jelas di halaman);
   - teks yang terlihat seperti data pribadi (nomor telepon, alamat, email) atau salinan panjang dari sumber (lebih dari 2 kalimat berurutan);
   - isi `persona.md` yang bocor ke kartu atau ringkasan.
3. Hapus isi `situs/` lalu bangun ulang dari nol sebagai file statis mandiri:
   - `index.html`: tiga tampilan (Pohon, Timeline, Pencarian) sesuai Bagian 18, hanya dari kartu publik. Layar ULASAN dan status penerapan **tidak** disertakan.
   - satu halaman per kartu publik dan satu halaman per cabang publik, dengan tautan relasi antar halaman.
   - `data.json` untuk pencarian sisi-browser (tanpa server).
   - Tanpa skrip pihak ketiga dan tanpa pelacak. Boleh memakai satu file JS/CSS lokal.
   - Dukung tampilan HP (responsif) dan mode gelap/terang.
4. Setiap halaman kartu menampilkan: ide, label kepercayaan dan dasar, tautan sumber asli (dibuka di tab baru), relasi, dan penanda pertentangan.
5. Tambahkan catatan di footer: "Dihasilkan dari catatan pribadi. Isi bukan nasihat medis, hukum, atau keuangan."
6. Verifikasi hasil: cari di seluruh `situs/` kata kunci dari `persona.md` (nama, angka keuangan, dll.) dan frasa dari 3 file acak di `sumber/`. Jika ada yang ditemukan, **batalkan** dan laporkan.
7. Laporkan ke pengguna: jumlah kartu dan cabang yang terbit, kartu yang dilewati beserta alasan, dan peringatan yang ditemukan. Jangan melakukan commit atau push sebelum pengguna menyetujui.
8. Setelah disetujui: commit dengan pesan `situs: update <tanggal> (<n> kartu publik)`. Pengunggahan (push) dilakukan sesuai persetujuan pengguna.

### 17.3 Default dan kebiasaan

- Kartu baru selalu `publik: tidak`. Agen tidak boleh menandai kartu sebagai publik atas inisiatif sendiri, hanya atas permintaan pengguna.
- Setelah beberapa kali MASUKKAN, agen boleh mengingatkan sekali: "Ada N kartu baru belum ditinjau untuk publikasi." Jangan mendesak.
- Penghapusan dari publik: bila pengguna mengubah kartu jadi `publik: tidak`, PUBLIKASI berikutnya otomatis menghilangkannya dari situs. Ingatkan pengguna bahwa riwayat Git dan cache dapat masih menyimpan versi lama.

### 17.4 Panduan penayangan (untuk dijelaskan ke pengguna saat diminta)

Cloudflare Pages, gratis, repo privat:
1. Dorong repo ke GitHub (privat).
2. Di Cloudflare Pages, pilih "Connect to Git", pilih repo tersebut.
3. Kolom *build command* dikosongkan, *output directory* diisi `situs`.
4. Setiap kali pengguna meminta PUBLIKASI dan melakukan push, situs ikut diperbarui otomatis.
5. Opsional: batasi pembaca dengan Cloudflare Access (login email) bila situs tidak untuk umum. Periksa ketentuan dan batas paket gratis terbaru sebelum mengandalkannya.

Catatan: alamat situs tetap bisa dibuka siapa pun yang mengetahuinya bila Access tidak dipakai, jadi hanya tandai `publik: ya` pada isi yang memang tidak keberatan dilihat orang lain.

---

## 18. Spesifikasi Tampilan

### 18.1 Prinsip

- **Satu data, tiga tampilan:** **Pohon** (orientasi dan penjelajahan), **Timeline** (membaca mendalam satu bidang per tahap hidup), **Pencarian/Daftar** (menemukan cepat). Semuanya dibaca dari header kartu dan `_cabang.md`. Tampilan tidak boleh menyimpan data sendiri dan bisa dibuat ulang kapan saja.
- Satu file `index.html` mandiri + `data.json`, tanpa server dan tanpa pustaka pihak ketiga dari internet (JavaScript biasa dan SVG). Berjalan offline bila dibuka lokal.
- Pohon adalah **alat navigasi, bukan dekorasi**: setiap elemen visual harus mewakili sesuatu yang nyata di data (lihat 18.3).
- Tampilan harus tetap berguna saat data masih sedikit (puluhan kartu) maupun banyak (ribuan kartu).

### 18.2 Daftar layar

1. **Pohon** (layar utama).
2. **Timeline** per bidang: kolom per tahap hidup, kartu di dalamnya.
3. **Pencarian/Daftar**: kolom cari, filter (bidang, tahap, jenis, kepercayaan, penerapan [lokal saja]), hasil berupa daftar kartu.
4. **Halaman Cabang**: ringkasan, poin kunci, pertentangan, daftar kartu, tautan tahap sebelum/berikutnya.
5. **Halaman Kartu**: lihat 18.6.
6. **Perpustakaan sumber**: katalog sumber. Di versi lokal tombol membuka teks asli. Di situs publik hanya metadata dan tautan ke sumber asli.
7. **Ulasan** (khusus lokal, Bagian 19).

### 18.3 Tampilan Pohon: pemetaan data → bentuk

| Bagian pohon | Mewakili | Cara menentukan dari data |
|---|---|---|
| **Akar** | Prinsip dasar | Kartu `tahap: semua-usia` dengan `kepercayaan` sedang/tinggi yang paling banyak dirujuk relasi `prasyarat-untuk` atau `terkait` (maksimal 7 akar) |
| **Batang** | Waktu / tahap hidup | Sumbu vertikal dari bawah ke atas: sebelum-20 → 20-25 → 25-30 → 30-40 → 40-50 → 50+ |
| **Cabang besar** | Bidang | Tiap bidang keluar dari batang pada tahap tempat kartunya mulai muncul; bidang tanpa tahap (mis. AI) keluar dari akar |
| **Ranting** | Sub-cabang / tema | Anak dari `_cabang.md` |
| **Daun** | Kartu | Ukuran = jumlah sumber yang mendukung; ketebalan warna = `kepercayaan` |
| **Garis silang tipis putus-putus** | Relasi antar-bidang | Relasi `terkait`, `memperkuat`, `lanjutan-dari` lintas cabang |
| **Ranting/garis merah** | Pertentangan | Relasi `bertentangan-dengan` |

**Tata letak harus deterministik** (bukan acak): data yang sama menghasilkan gambar yang sama, sehingga pengguna hafal posisi cabangnya. Cabang diletakkan bergantian kiri dan kanan batang menurut urutan di `indeks.md`.

**Zoom bertingkat (wajib, mencegah kusut):**
- Level 0: hanya akar, batang, dan cabang bidang (maksimal ±12 simpul) dengan jumlah kartu.
- Level 1: klik cabang → ranting/sub-cabang dan tahap terbuka; cabang lain mengecil dan redup.
- Level 2: klik ranting → kartu (daun) muncul dengan judul singkat.
- **Batas keras:** tidak lebih dari ±50 simpul terlihat sekaligus. Bila lebih, kelompokkan dan tampilkan "+N kartu".
- Klik daun → panel detail di sisi kanan (ide, kepercayaan, relasi, tautan sumber, tombol "Buka kartu").
- Tersedia breadcrumb (Pohon › Kesuksesan › 25-30) dan tombol "Kembali ke batang".

**Interaksi:** geser (pan) dan zoom dengan mouse, sentuh, dan tombol +/−; semua simpul bisa dijangkau dengan keyboard (Tab/Enter); animasi singkat dan dapat dimatikan (hormati `prefers-reduced-motion`).

**Alternatif non-visual wajib:** setiap tampilan pohon punya versi daftar bersarang (outline) yang dapat dibuka dengan satu tombol, untuk pembaca layar, HP kecil, dan pengguna yang lebih suka teks. Pada lebar layar ≤ 900 px, tampilan pohon otomatis berganti ke outline bersarang yang bisa dilipat.

### 18.4 Tampilan Timeline

- Satu bidang dipilih dari daftar cabang di sisi kiri. Di tengah: kolom per tahap hidup (20-25, 25-30, 30-40, Semua usia) dengan rel horizontal dan titik penanda di atas tiap kolom.
- Tiap kolom berisi kartu: label jenis, label kepercayaan (titik berwarna **dan** teks), judul, sumber, serta tautan "Lanjut ke K-xxxx →" bila ada relasi lanjutan.
- Kartu pertentangan diberi garis tepi merah dan tautan "Lihat kedua sisi".
- Di atas daftar: ringkasan cabang (maksimal 3 kalimat), jumlah kartu/sumber, dan chip filter jenis.

### 18.5 Gaya visual

Gaya **skematik & editorial yang bersih** (tanpa dekorasi *AI slop* seperti gradasi neon atau kartu penuh efek blur): mengadaptasi prinsip diagram teknis yang tegas—tulang punggung vertikal, cabang garis putus-putus, node dengan batas tegas dan hierarki warna fungsional, serta katalog ber-sidebar kategori yang rapi—**tanpa menjiplak** identitas visual situs lain.

Mendukung **dua tema (Terang dan Gelap)** dengan tombol ganti tema yang persisten (`localStorage`), kontras teks minimal 4,5:1 di kedua tema:

| Token | Tema Terang (Default) | Tema Gelap |
|---|---|---|
| Latar | `#F8F9FA` | `#0E1311` |
| Permukaan (kartu / node) | `#FFFFFF` | `#151C19` |
| Garis / batas tegas | `#1E2421` (node) / `#D6DDD9` (grid) | `#3A4A42` (node) / `#232E28` (grid) |
| Teks utama | `#141A17` | `#E8EFEA` |
| Teks sekunder | `#4A5952` dan `#687770` | `#B7C4BC` dan `#8FA097` |
| Node utama (batang/tahap) | latar `#F5E25B`, teks `#141A17` | latar `#25382E`, batas `#7EE0A8`, teks `#E8EFEA` |
| Node cabang / ranting | latar `#F7E8C8`, teks `#141A17` | latar `#1C2521`, batas `#4E6359`, teks `#E8EFEA` |
| Garis tulang punggung & cabang | `#2B6CB0` (batang), `#4A7FB5` (putus-putus) | `#7EE0A8` (batang), `#548A6C` (putus-putus) |
| Kepercayaan tinggi / sedang / rendah | `#1E7A46` / `#2B5BB5` / `#B4690E` | `#7EE0A8` / `#9FB8FF` / `#F2B666` |
| Pertentangan | teks `#B42318`, garis tepi `#D92D20` | teks `#FF9B8C`, garis tepi `#6B3A33` |

- Font: **Space Grotesk** untuk judul, **Inter** untuk isi, dengan cadangan `sans-serif`. Boleh disertakan lokal agar tidak bergantung internet.
- Sudut membulat sedang (6–10 px untuk node diagram, 10–12 px untuk panel/kartu), batas tegas, jarak lega, tanpa ikon emoji (gunakan SVG inline).
- Warna tidak boleh menjadi satu-satunya pembeda: selalu sertakan teks atau bentuk.
- Kontras teks minimal 4,5:1. Area sentuh minimal 44 px.
- Semua tombol dan tautan memakai elemen `<button>`/`<a>` asli dengan label jelas.
- **Batas privasi kontrol node (selaras Bagian 17.1):** kontrol status penerapan langsung di node (mis. popover `belum-dicoba` / `sedang-dicoba` / `diterapkan` / `ditolak`) **hanya boleh ada di versi lokal** dan **wajib dihilangkan total di situs publik (`situs/`)**.

### 18.6 Halaman Kartu

Berisi: jalur (Bidang › Tahap › ID kartu), lencana jenis dan kepercayaan, judul (ide singkat), penjelasan, kutipan pendukung (maksimal 2 kalimat), bagian "Terhubung ke kartu lain" (lanjutan dari, prasyarat untuk, memperkuat, bertentangan dengan, semuanya bisa diklik), dan panel **Sumber asli** di kanan: ID, penulis, platform, tanggal masuk, tombol "Buka postingan asli ↗", dan "Lihat semua kartu dari sumber ini". Di versi lokal ada tambahan tombol "Buka teks lengkap" ke `sumber/`. Di situs publik ditampilkan catatan bahwa teks lengkap tersimpan di perpustakaan pribadi.

### 18.7 Data

Gunakan data nyata dari kartu. Dilarang menampilkan teks isian (lorem ipsum), angka karangan, atau kartu contoh di versi yang dipakai pengguna. Bila data masih kosong, tampilkan keadaan kosong yang menjelaskan cara memasukkan postingan pertama.

---

## 19. Status Penerapan & Ulasan Mingguan

Tujuan: pengetahuan yang dicoba dan diuji lebih berharga daripada yang hanya disimpan. Sistem membantu **menerapkan dan mengingat**, bukan hanya mengumpulkan.

### 19.1 Status penerapan (per kartu)

`belum-dicoba` (default) → `sedang-dicoba` → `diterapkan` atau `ditolak`. Pengguna menceritakan hasilnya dengan bahasa biasa, mis. "saya sudah coba K-0087 dua minggu, hasilnya ...". Agen:
1. Memperbarui `penerapan`, mencatat `penerapan-catatan` dengan kata-kata pengguna (jangan dipoles atau ditambah klaim), dan mengisi `terakhir-ditinjau`.
2. Bila `ditolak` atau hasilnya bertentangan dengan isi kartu, tawarkan memberi relasi/catatan pada kartu itu dan menurunkan `kepercayaan` **hanya atas persetujuan pengguna**.
3. Mencatat di `log.md`.

Status penerapan **bersifat pribadi** dan tidak pernah dipublikasikan.

### 19.2 Perintah ULASAN

Pilih **maksimal 5 kartu** dengan urutan prioritas:
1. `sedang-dicoba` yang belum diperbarui lebih dari 14 hari.
2. `belum-dicoba` berkepercayaan sedang/tinggi yang paling relevan dengan tujuan di `persona.md` (hanya baca persona, jangan membuka semua kartu; gunakan pencarian header).
3. Kartu yang `terakhir-ditinjau`-nya lebih dari 30 hari.

Untuk tiap kartu, tampilkan: ide singkat + ID, alasan muncul sekarang, **satu langkah kecil yang bisa dicoba (≤15 menit)**, dan satu pertanyaan refleksi. Setelah pengguna menjawab, perbarui status sesuai 19.1.

Aturan:
- Langkah kecil harus selaras dengan kartu (cantumkan ID). Tambahan dari agen diberi label `[inferensi AI]`.
- Jangan mendesak atau menagih. Maksimal sekali per sesi kecuali diminta.
- Kartu kesehatan/keuangan berkepercayaan rendah: jangan diusulkan sebagai langkah yang berisiko; arahkan untuk memverifikasi lebih dulu.
- Jangan mengklaim sebuah saran terbukti berhasil. Catat hanya yang dilaporkan pengguna.

### 19.3 Statistik ringan

Perintah STATUS menambahkan satu baris: jumlah kartu per status penerapan. Tanpa gamifikasi berlebihan, tanpa skor atau peringkat.

---

## 20. Rencana Bangun Bertahap (untuk AI pembangun)

Baca **seluruh dokumen ini** sebelum membuat file apa pun. Bangun berurutan. **Jangan memulai fase berikutnya sebelum pengguna menyatakan fase sebelumnya lolos uji.**

| Fase | Isi | Gerbang lolos |
|---|---|---|
| **1. Fondasi** | Struktur folder, template (sumber, kartu, cabang, indeks, persona, log, katalog), inisialisasi (Bagian 15), alur MASUKKAN, BUKA KARTU/SUMBER, CARI | Pengguna memasukkan 5-10 postingan nyata dan memeriksa hasilnya |
| **2. Pohon data** | Cabang, timeline tahap hidup, relasi, aturan pecah/gabung, STATUS, RAPIKAN, persona dan SARAN | 30+ kartu tertata, relasi masuk akal menurut pengguna |
| **3. Penerapan** | Bagian 19 (status penerapan, ULASAN) | Satu putaran ulasan berjalan |
| **4. Tampilan** | Bagian 18 secara lokal (Pohon, Timeline, Pencarian, Halaman Kartu/Cabang, Perpustakaan) | Pengguna puas dengan bentuk pohon dan alur membaca |
| **5. Publikasi** | Bagian 17 dan panduan penayangan | Situs berjalan dan hasil pemeriksaan keselamatan bersih |

Aturan untuk pembangun:
- Bila dua bagian bertentangan, prioritas: **Bagian 0 (prinsip) > Bagian 14 (perlindungan data) > Bagian 17 (publikasi) > bagian lainnya.**
- Bila ada hal yang tidak jelas dan memengaruhi hasil, tanyakan satu pertanyaan singkat. Jika tidak, ambil keputusan terbaik dan catat asumsinya di `log.md`.
- Jangan menambah fitur di luar dokumen ini tanpa persetujuan pengguna. Usulan fitur disampaikan sebagai saran, bukan langsung dibangun.
- Di setiap akhir fase: ringkas apa yang dibuat, cara mengujinya, dan apa yang akan dikerjakan di fase berikutnya, lalu **berhenti dan tunggu persetujuan**.

---

## 21. Lapisan Kecerdasan & Indeks Lokal

Prinsip kerja: **skrip mempersempit, AI memutuskan, pengguna menyetujui.** Skrip lokal (cepat, deterministik, 0 dependensi) mencari kandidat dan menghitung; AI hanya membaca kandidat teratas untuk menilai makna; pengguna tetap pengambil keputusan.

### 21.1 Aturan Emas
1. **Markdown tetap satu-satunya sumber kebenaran.** Indeks SQLite (`.indeks.db`) dan `data.json` hanyalah turunan yang dapat dibangun ulang kapan saja dan tidak pernah masuk ke `situs/` maupun Git.
2. **Transparan.** Setiap saran atau peringkat wajib menyebut alasan dan ID kartu dasarnya.
3. **Bangun sesuai ambang data.** Jangan mengaktifkan algoritma statistik sebelum jumlah kartunya memadai (lihat tabel 21.2).
4. **Bebas dependensi eksternal.** Pencarian awal memakai SQLite FTS5 (BM25) bawaan Python + perluasan kata kunci oleh AI. Embedding lokal sengaja ditunda sampai >3.000 kartu dan hanya bila FTS5 sering meleset.
5. **Batas server lokal (`scripts/server_lokal.py`) & tarik link (`scripts/ambil_link.py`):** hanya mendengarkan `127.0.0.1`, hanya boleh (a) mengubah field `penerapan`, `penerapan-catatan`, `terakhir-ditinjau` pada `kartu/K-XXXX.md`, (b) membuat file sumber **baru** `sumber/S-XXXX.md` atas permintaan eksplisit pengguna (tidak pernah menimpa/menghapus sumber lama — P1) serta mencatat di `sumber/_katalog.md` dan `log.md`, dan (c) menarik preview URL publik (X oEmbed, transkrip YouTube, artikel web) hanya saat pengguna menekan tombol tarik link. Semua input divalidasi, dan `server_lokal.py` / `ambil_link.py` tidak pernah ikut ke `situs/`. `Teks Asli` sumber dimuat *on-demand* (tidak ditanam penuh di HTML).

### 21.2 Peta Kemampuan & Ambang Data

| Kemampuan | Teknik | Ambang Bangun |
|---|---|---|
| Pencarian cepat berperingkat | SQLite FTS5 (BM25) via `--cari` + perluasan sinonim oleh AI | Sekarang |
| Deteksi duplikat & tetangga saat MASUKKAN | Top-20 FTS5 → kemiripan teks (`--tetangga`) → AI menilai relasi | Sekarang |
| Filter bertingkat & tampilan tersimpan | `--filter` (bidang, tahap, jenis, kepercayaan, penerapan, penulis, tag) + *pertentangan terbuka*, *belum diverifikasi*, *kartu yatim* | Sekarang |
| Pemindahan cabang massal | `--pindah-cabang` atomik untuk pecah cabang >30 kartu | Sekarang |
| Perbandingan alat/metode & Playbook awal–akhir | `--bandingkan`, `--playbook`, `--tren` (TF-IDF distinctive terms, konsensus lintas sumber, pemetaan 6 tahap kerja, bobot kalibrasi penerapan) + skill `sintesis-playbook` | Sekarang |
| Ulasan cerdas | Penjadwalan pengulangan berjarak (Leitner / SM-2 sederhana) | ±50 kartu |
| Saran otomatis & deteksi gema | Skor transparan (tujuan × tahap × kepercayaan × belum dicoba) & jumlah penulis unik per cabang | ±100 kartu |
| Urutan roadmap | Urut topologis relasi prasyarat + deteksi siklus | ±150 kartu |
| Kartu fondasi, jembatan & kalibrasi sumber | Centrality/PageRank & ringkasan tingkat penerapan per penulis (informasi, bukan vonis) | ±200 kartu |
| Usulan sub-cabang otomatis | Clustering teks → AI menamai | Cabang >30 kartu |
| Pencarian makna (embedding lokal) | Model lokal (opsional) | >3.000 kartu |
