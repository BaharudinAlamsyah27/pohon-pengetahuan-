# Log Perubahan Pohon Pengetahuan

Catatan kronologis (append-only).

[2026-11-22] INIT | Struktur Fase 1 (Fondasi) dibuat: indeks.md, log.md, persona.md, sumber/_katalog.md, kartu/, 7 cabang awal | catatan: lokasi periksa_kebocoran.py dirapikan ke .agents/skills/publikasi-situs/scripts/
[2026-11-22] SPEK | AGENTS.md Bagian 18.5 diperbarui sebagai satu sumber kebenaran: 2 tema (Terang default + Gelap), gaya skematik/diagram bersih (adaptasi, bukan jiplakan), kontrol status penerapan di node khusus lokal (dihilangkan di situs publik)
[2026-11-22] MASUK S-0001 → K-0001..K-0002 | cabang diperbarui: keuangan/monetisasi-konten, keuangan | catatan: disalin dari tangkapan layar postingan @sibambaang di X; sub-cabang baru monetisasi-konten dibuat
[2026-11-22] PERSONA | persona.md dilengkapi oleh pengguna (tahap 20-25, MagangHub BPRS Sragen, tujuan CPNS + beasiswa luar negeri + pendapatan tambahan); Fase 1 dinyatakan lolos uji oleh pengguna
[2026-11-22] BANGUN | scripts/bangun_pohon.py & scripts/template_peta.html dibuat; peta-pohon.html dan data.json dibangun (2 tema Terang/Gelap, 7 layar sesuai Bagian 18, audit STATUS/RAPIKAN --cek, siap mode publik Bagian 17)
[2026-11-22] FASE5 | Lengkapi batang tahap hidup & akar klikable di SVG Pohon (Bagian 18.3), pra-periksa keselamatan + halaman statis per kartu/cabang di mode publik (Bagian 17.2), dan uji lolos periksa_kebocoran.py
[2026-11-22] KECERDASAN | Tambah Bagian 21 di AGENTS.md; upgrade bangun_pohon.py (SQLite FTS5/BM25 --cari, --tetangga, --filter + tampilan tersimpan, --pindah-cabang, Teks Asli tidak ditanam di HTML); buat scripts/server_lokal.py (127.0.0.1 only); tambah hash routing & saved views di template_peta.html
[2026-11-22] MESIN-CERDAS | scripts/mesin_cerdas.py dibuat (0 dependensi): TF-IDF + Cosine (--mirip), Medoid Clustering (--klaster), SM-2/Leitner (--ulasan), Persona Recommender + MMR (--saran), Kahn Topological Sort + Cycle Detection (--roadmap), PageRank + Bridge Centrality (--fondasi), Shannon Entropy & HHI (--gema), Kalibrasi Sumber (--kalibrasi)
[2026-11-22] TANGKAP | Tambah scripts/ambil_link.py (X oEmbed, transkrip YouTube, artikel web) + endpoint /api/ambil-link & /api/simpan-sumber di server_lokal.py + layar Tangkap & Bookmarklet 1-Klik di template_peta.html (khusus lokal, tidak masuk situs/)
[2026-11-22] DOMINAN+BIGDATA | Tambah 4 bab dominan di indeks.md (AI + 5 sub-cabang, Bisnis, Sosmed, Digital Marketing), field opsional alat/tugas/tahap-kerja di AGENTS.md & FTS5, mesin --bandingkan/--playbook/--tren di mesin_cerdas.py, skill sintesis-playbook, dan tab Analisis + /api/analisis di server_lokal.py
[2026-11-22] PANDUAN | Buat PANDUAN.md berisi kamus perintah chat, bank pertanyaan masa depan, perintah terminal 0-token, dan pengingat Bookmarklet (lokal saja, tidak masuk situs/)

[2026-11-22] TANGKAP S-0002 | "Pro-tip: ketika bikin app, sangat recommended untuk bikin tone-of-voice" (X) | menunggu ekstraksi kartu
[2026-11-22] TANGKAP S-0003 | "Open-sourced my full SEO and AI-search stack for Claude Code and Cursor (30 skil" (X) -> draf K-0003 (ai)
[2026-11-22] TANGKAP S-0004 | "(79) Beranda / X" (X) -> draf K-0004 (keuangan)
[2026-11-22] TANGKAP S-0005 | "(79) Beranda / X" (X) -> draf K-0005 (ai)
[2026-11-22] FITUR-NYATA | Tambah Inbox Draf (--tampilan draf-otomatis + panel Tangkap), Fokus 1 Eksperimen Minggu Ini + catatan di Ulasan, Salin Brief Konteks AI di Analisis, Arsipkan Kartu (/api/arsipkan-kartu) di Halaman Kartu lokal, dan backup.bat
[2026-11-22] RUANG-TAMU | Tambah halaman Beranda (dashboard & portofolio produk) sebagai layar awal di template_peta.html, buat vercel.json (output situs/), perbarui PANDUAN.md, dan perbaiki tumpang tindih SVG Pohon Level 1-2 menjadi tata letak 3 kolom
[2026-11-22] TANYA-RAG | Tambah tab Tanya (Level 1 sintesis lokal 0 biaya + Level 2 Gemini 2.5 Flash-Lite RAG) di template_peta.html, --tanya & answer_question() di mesin_cerdas.py, POST /api/tanya di server_lokal.py, api/tanya.js untuk Vercel, serta .env.example & proteksi .gitignore
[2026-11-22] TANGKAP S-0006 | "Imagine being 29, looking back at 25 and realizing you spent 4 years worrying ab" (X) -> draf K-0006 (motivasi-dan-mindset)
[2026-11-22] TANGKAP S-0007 | "Take care of your appearance. Lift the weights. Eat healthy food. Sleep like an" (X) -> draf K-0007 (lainnya)
[2026-11-22] TANGKAP S-0008 | "🚨 谷歌黑五 $99/年 Google AI Pro 合法上车攻略！（截止 11 月 26 日）" (X) -> draf K-0008 (ai)
[2026-11-22] TANGKAP S-0009 | "🚨 谷歌黑五 $99/年 Google AI Pro 合法上车攻略！（截止 11 月 26 日）" (X) -> draf K-0009 (ai)
[2026-11-22] TANGKAP S-0010 | "🚨 谷歌黑五 $99/年 Google AI Pro 合法上车攻略！（截止 11 月 26 日）" (X) -> draf K-0010 (ai)
[2026-11-22] TANGKAP S-0011 | "how to start making more money on x" (X) -> draf K-0011 (ai/prompt-dan-agen)
[2026-11-22] PENERAPAN K-0011 -> sedang-dicoba
[2026-11-22] PENERAPAN K-0011 -> diterapkan
[2026-11-22] PENERAPAN K-0011 -> belum-dicoba
[2026-11-22] TANGKAP S-0012 | "爽！Google AI Ultra 20x，30TB，前三个月只要 $19.99/月！完整上车教程来了！🚀" (X) -> draf K-0012 (ai/coding-dan-proyek)
[2026-11-22] EDIT K-0001 | cabang: keuangan/monetisasi-konten
[2026-11-22] EDIT K-0001 | cabang: keuangan/monetisasi-konten
[2026-11-22] SAINS-DATA-DAN-CRUD | Rapikan legenda Pohon ke bawah kanvas, hapus tombol zoom, tambah Ringkasan & Aksi Cepat + bilah pintasan, tambah Audit Sains Data (--sains: matriks celah, peluruhan kesegaran, kredibilitas sumber, kandidat pertentangan, jembatan lintas-bidang), pencarian hibrida RRF dwibahasa (ID<->EN), umpan balik Tanya (/api/tanya-feedback), klasifikasi cabang dwibahasa + auto-cabang baru, penjaga duplikat & auto-reset form Tangkap, CRUD Edit/Arsip Kartu (/api/edit-kartu), rating 1-5 bintang + catatan khusus + filter bintang, menu hamburger <=1024px, dan perbaikan klik cabang Pohon (audit JS & logika bisnis PASS)
[2026-11-22] MATEMATIKA-AKAR-DAUN | Implementasi 5 mesin matematika gratis di mesin_cerdas.py & ambil_link.py: (1) Filter Shannon Entropy & penalti noise sosmed, (2) TextTiling deteksi batas segmen topik, (3) LexRank Eigenvector Centrality kalimat inti, (4) Maximal Marginal Relevance (MMR) ekstraksi 1-5 Daun bebas redundansi dari 1 Akar, (5) Algoritma HITS (Hubs=Kesuburan Akar, Authorities=Kematangan Daun), ditambah Text-to-Tag Density boilerplate removal, Recursive Link Chasing 1-hop, dan OCR Gambar gratis (Tesseract lokal / Gemini Vision Free Tier) di tab Tangkap

[2026-11-22] TANGKAP S-0013 | "posted this a month ago at $2M ARR. haven't hired a single sales rep since. we'r" (X) -> daun K-0013, K-0014 (ai/prompt-dan-agen)
[2026-11-22] TANGKAP S-0014 | "如果你已经订阅 google ai 套餐" (X) -> daun K-0015, K-0016, K-0017 (ai/coding-dan-proyek)
[2026-11-22] TANGKAP S-0015 | "if you drop a raw ElevenLabs voiceover straight into CapCut, Youtube already fla" (X) -> daun K-0018, K-0019, K-0020 (ai)
[2026-11-22] TANGKAP S-0016 | "Terjawab sudah rasa penasaran ku! 😳🌱" (X) -> daun K-0021 (ai/coding-dan-proyek)
[2026-11-22] RAPIKAN-DAN-PUBLIKASI | Terjemahkan & kurasi seluruh 22 kartu (K-0001..K-0022) ke Bahasa Indonesia, gabung duplikat K-0009 & K-0010 ke K-0008, pindahkan K-0007 ke kesehatan, K-0011 ke sosmed, K-0018..K-0020 ke ai/video-dan-clipping, K-0021 ke bisnis, ekstrak S-0002 menjadi K-0022 (ai/tulisan-dan-artikel), tandai 19 kartu terpilih menjadi publik: ya, serta tambah fitur Kantong Antrean Browser (localStorage) di + Simpan Baru saat laptop/server lokal mati
[2026-11-22] NEO-BRUTALISME-DAN-RILIS | Desain ulang UI gaya Neo-Brutalisme terinspirasi portfolio-alam (stempel SIDE-A/SIDE-B, kartu balik Kilas Wawasan, Musik & Suara Meja Web Audio Synth 3 mode Lo-Fi/Hujan/Pohon, laci bantuan tutorial '?' di semua 9 seksi), perapihan toolbar Cari Kartu & chip filter cepat, lolos audit kebocoran data (BERSIH), dan persiapan commit rilis publik Git/Vercel

[2026-11-26] TANGKAP S-0017 | "Same math applies to sleep." (X) -> daun K-0023 (kesehatan)
[2026-11-26] TANGKAP S-0018 | "(83) alexei di X: 'neuroscience shows that the easiest way to become confident and actually believe in yourself is to ch" (X) -> daun K-0024, K-0025, K-0026 (ai)
[2026-11-26] TANGKAP S-0019 | "neuroscience shows that the easiest way to become confident and actually believe" (X) -> daun K-0027, K-0028, K-0029 (motivasi-dan-mindset)
[2026-11-26] TANGKAP S-0020 | "Normalize being very direct. Very straight to the point. Very assertive. You'll get everyt" (X) -> daun K-0030 (motivasi-dan-mindset)
[2026-11-26] TANGKAP S-0021 | "Terlalu sering scrolling media sosial --> Gangguan reseptor dopamin di otak --> Brain rot" (X) -> daun K-0031 (kesehatan)
[2026-11-26] TANGKAP S-0022 | "science shows that complaining or talking about your problems the wrong way can actually m" (X) -> daun K-0032 (motivasi-dan-mindset)
[2026-11-26] PANDUAN-ONLINE | Tambah kotak panduan bahasa sederhana Mode Web Online (Antrean Browser) vs Mode Laptop (Otomatis) + pesan tombol ramah di tab + Simpan Baru (`scripts/template_peta.html`)
[2026-11-26] TOMBOL-CEPAT | Buat folder `tombol-cepat/` (`1-Buka-Aplikasi-Lokal.bat`, `2-Update-Web-Vercel.bat`, `BACA-SAYA.txt`) untuk akses lokal & publikasi Vercel 1-klik
[2026-11-26] KECERDASAN-V2 | Upgrade klasifikasi 3-lapis (Gemini Semantik + Multinomial Naive Bayes self-learning + Word-Boundary 447 istilah ID-EN + RRF), 420 sinonim dwibahasa, deteksi metadata otomatis (`jenis`, `dasar`, `kepercayaan`, `tahap`, `tag`), penjaga duplikat URL + 3-gram Jaccard, dan relasi tetangga otomatis
[2026-11-26] ARSITEKTUR-CLAUDE | Implementasi 1-panggilan JSON terstruktur (`extract_structured_cards_gemini`) dengan konteks Top-12 tetangga, validasi anti-halusinasi kutipan, multi-cabang per sumber, relasi 2 arah otomatis (`add_inverse_relation`), stemmer imbuhan ID (`stem_id`), indeks kedua SQLite FTS5 `kartu_trigram`, field `konsep:` abstrak, Quote Tweet rekursif (kedalaman <=2) + label `[teks dari gambar, ditranskrip AI]`
[2026-11-26] X-ARTICLES-DAN-BOOKMARKLET | Perbaiki Bookmarklet X agar mengunci penulis utama (abaikan komentar & feed AI bawah), tambah dukungan penuh X Articles (`twitterArticleReadView` & `tweet.article.content.blocks`) di `ambil_link.py` & Bookmarklet, serta ubah default simpan menjadi 1 Kartu Utuh berisi poin bernomor rapi
[2026-11-26] MULTI-AI-GRATIS | Upgrade default model ke `gemini-3.5-flash-lite` dan pasang cascade otomatis 6 penyedia AI gratis (`GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `MISTRAL_API_KEY`, `CEREBRAS_API_KEY`, `NVIDIA_API_KEY`) di `scripts/mesin_cerdas.py`, `api/tanya.js`, dan `.env.example`; hasil tes live: Gemini 3.5 Flash-Lite & OpenRouter `:free` AKTIF, Vercel `/api/tanya` AKTIF (`ai-rag (gemini-3.5-flash-lite)`)
[2026-11-26] AUDIT-LOGIKA-BISNIS | Perbaiki 7 bug logika bisnis: (1) pulihkan `translate_and_polish_card_gemini` via 6-AI cascade, (2) tangani `duplikat_dari` otomatis (gabung sumber ke kartu lama sesuai AGENTS.md Bagian 4.4) + toast UI, (3) hemat 50% panggilan AI saat simpan (hapus dobel `guess_branch` sebelum 1-call JSON), (4) arahkan `_classify_branch_gemini` ke 6-AI cascade, (5) kirim `kepercayaan` asli ke `sync_branch_and_index`, (6) perbaiki false-positive alat `make` -> `make.com` & bersihkan `K-0032`, (7) lengkapi 5 relasi 2 arah (`K-0003`, `K-0024`, `K-0025`, `K-0027`, `K-0028`) & skip kartu non-aktif pada audit 1-arah (`--cek` kini 0 relasi 1-arah, audit kebocoran BERSIH)
[2026-11-26] RAPIKAN-DAN-SELF-IMPROVING | Gabung duplikat K-0024..K-0029 (S-0018 & S-0019) menjadi 1 kartu utuh K-0027 (motivasi-dan-mindset) & terjemahkan K-0023, K-0032 ke Bahasa Indonesia lengkap dengan `konsep:`; tambah 4 fitur kecerdasan mandiri: (1) sintesis ringkasan cabang otomatis setiap >=5 kartu baru (`synthesize_branch_summary_llm`), (2) Active Learning koreksi cabang manual (`.koreksi_cabang.jsonl` bobot 5x di Naive Bayes), (3) pil Jembatan Konsep (`konsep:`) interaktif lintas bidang di halaman kartu & pencarian, (4) tombol 1-klik "Rapikan & Terjemahkan Draf" (`POST /api/rapikan-draf`)


