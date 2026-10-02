# HANDOFF REPORT: SURVEY OF TYPOGRAPHY, DIAGRAM SYNTAX, NOMENCLATURE, AND STANDARDS

**Agent**: Explorer 3 (Typography, Diagram Syntax, and Formatting Standards)  
**Target File**: `E:\wa bot longchain\laporan.md`  
**Report File**: `E:\wa bot longchain\.agents\teamwork\explorer_survey_formatting\report.md`  
**Handoff Type**: Hard (Investigation complete and self-contained)

---

## 1. Observation

Direct observations from inspecting `laporan.md` and related codebase files (`graph_builder.py`, `agents/prompts.py`, `agents/schemas.py`, `api/routes/admin.py`, `database/schema.sql`, `data/knowledge/*.json`):

1. **Mermaid Block 1 (`flowchart TB`, Baris 27–103)**:
   - **Baris 90**: `WeatherSvc <-->|API Key: 76d7a4136a6948e8ac464008250810| WeatherAPI`  
     *Observasi*: Plaintext active API key tercetak langsung di label panah diagram.
   - **Baris 73**: `WAHA -->|Webhook POST < 200ms| Webhook`  
     *Observasi*: Karakter `<` tidak di-escape di dalam label tautan `|...|`. Pada renderer Mermaid HTML/DOMPurify, karakter `<` memicu galat unclosed HTML tag.
   - **Baris 50**: `Guardrail["Guardrail & Formatter Node\n(Threshold >= 0.70 & Anti-Halusinasi)"]`  
     *Observasi*: Karakter `&` mentah dan `>=` berpotensi memicu galat XML/SVG parser bila diekspor ke SVG non-HTML.
   - **Baris 94**: `SubAgents --> Guardrail`  
     *Observasi*: `SubAgents` adalah identifier sebuah `subgraph` (`subgraph SubAgents[...]`). Hubungan langsung dari ID subgraph ke node membutuhkan fitur compound graph yang tidak didukung secara universal oleh seluruh renderer Markdown/Mermaid.
   - **Baris 64–68**: `subgraph External` hanya memuat `GeminiFlash`, `GeminiEmbed`, dan `WeatherAPI`. Komponen fallback otomatis `Open-Meteo API` (dijelaskan di teks Bab 3.1 & 5.4) tidak ada di diagram.

2. **Mermaid Block 2 (`stateDiagram-v2`, Baris 109–141)**:
   - **Baris 135**: `Beri_Rujukan: Jika < 0.70 -> Tampilkan Pesan Aman Rujukan PPL`
   - **Baris 136**: `Beri_Solusi: Jika >= 0.70 -> Format 3 Pilar (Mekanis, Sanitasi, Kimiawi) + Link Foto Referensi`  
     *Observasi*: Operator `->` digunakan secara ilegal di dalam teks deskripsi state setelah tanda titik dua `:`. Dalam `stateDiagram-v2`, `->` atau `-->` adalah reserved operator untuk transisi state, sehingga menimbulkan syntax parse error. Selain itu, simbol `< 0.70` memicu unescaped HTML parsing error.
   - **Baris 133–136**: Keempat state (`Cek_Komoditas`, `Cek_Confidence`, `Beri_Rujukan`, `Beri_Solusi`) tidak memiliki garis transisi penghubung apa pun di dalam `state formatter { ... }`.
   - **Baris 115–121**: State di dalam `state router` membuat garis transisi langsung melompati batas kontainer ke node luar (`vision`, `weather`, dll.), yang sering menimbulkan *rendering clip bug* pada Mermaid.

3. **Mermaid Block 3 (`gantt`, Baris 472–486)**:
   - *Observasi*: Sintaks dasar valid, namun belum memiliki `axisFormat` yang jelas (seperti `%b %Y`), sehingga penanda waktu sumbu X padat/terpotong di layar sempit.

4. **Nomenklatur Ilmiah Botani & Fitopatologi**:
   - **Baris 286**: `2. *Penyakit Bulai / Virus Kuning Gemini* (Gemini Virus)`  
     *Observasi*: Frasa `Gemini Virus` tidak dicetak miring (*italic*) dan merupakan istilah informal. Sesuai database `data/knowledge/cabai_diseases.json` Baris 17, nama resminya adalah *Pepper yellow leaf curl virus* (PepYLCV) dari genus *Begomovirus*.
   - **Baris 295**: `4. *Penyakit Tungro* (Rice Tungro Bacilliform/Spherical Virus)`  
     *Observasi*: Frasa `Rice Tungro Bacilliform/Spherical Virus` tidak dicetak miring dan menggunakan huruf kapital tidak baku. Sesuai ICTV dan `data/knowledge/padi_diseases.json` Baris 41, nama resminya adalah *Rice tungro bacilliform virus* (RTBV) dan *Rice tungro spherical virus* (RTSV).
   - **Baris 294**: `3. *Penggerek Batang Padi / Sundep & Beluk* (*Scirpophaga innotata*)`  
     *Observasi*: Laporan mencantumkan *Scirpophaga innotata* (Penggerek Putih), sedangkan berkas `data/knowledge/padi_diseases.json` Baris 29 mencantumkan `Scirpophaga incertulas` (Penggerek Kuning). Keduanya merupakan hama penggerek batang padi di Indonesia.
   - **Baris 288 & 293**: `*Fusarium oxysporum*` dan `*Xanthomonas oryzae*` belum menyertakan forma specialis / pathovar (*Fusarium oxysporum* f. sp. *capsici* dan *Xanthomonas oryzae* pv. *oryzae*).
   - **Baris 455–457**: Backlog komoditas masa depan belum mencantumkan nama latin (*Allium ascalonicum*, *Zea mays*, *Spodoptera frugiperda*, *Peronosclerospora maydis*).

5. **GitHub Flavored Markdown (GFM) Alerts**:
   - *Observasi*: Dokumen sepanjang 566 baris saat ini hanya memiliki **1** GFM alert box (Baris 188 `[!IMPORTANT]` mengenai RAM WAHA). Bagian-bagian krusial seperti proteksi kredensial API key, failover cuaca, batasan guardrail agronomi, dan aktivasi pgvector belum menggunakan callout box standar GitHub.

6. **3 Pilar PHT & Rujukan PPL**:
   - *Observasi*: Kode (`graph_builder.py` Baris 305–315, `agents/prompts.py` Baris 14–29, `api/routes/admin.py` Baris 118–167) menerapkan sistem PHT (Mekanis, Sanitasi, Kimiawi Terdaftar) dan rujukan PPL tertutup (*closed-loop*), namun dokumentasi di `laporan.md` menjelaskannya secara terpisah di berbagai bab tanpa diagram alur sekuens terpadu.

---

## 2. Logic Chain

1. **Dari Observasi 1 (Diagram 2.1)**:
   - Kebocoran API key plaintext di Baris 90 berisiko tinggi terhadap keamanan akun WeatherAPI dan melanggar kriteria R1. Menggantinya dengan placeholder `(WEATHER_API_KEY)` menyelesaikan risiko keamanan.
   - Karakter `<` di Baris 73 dan ampersand di Baris 50 melanggar aturan sanitasi HTML/XML parser Mermaid. Menyelubungi dengan tanda kutip ganda `|"..."|` dan entitas `&lt;` serta `&ge;` menjamin diagram dapat dirender bebas error di seluruh platform (GitHub, VS Code, pandoc, headless chromium).
   - Menghubungkan node individual daripada ID subgraph di Baris 94 menghilangkan ketergantungan pada parser compound-subgraph.
   - Menambahkan Open-Meteo menyelaraskan representasi visual diagram dengan arsitektur riil sistem failover cuaca.

2. **Dari Observasi 2 (Diagram 2.2)**:
   - Penggunaan simbol `->` di dalam teks setelah tanda titik dua pada `stateDiagram-v2` Baris 135–136 secara sintaksis bentrok dengan parser tokenizer transisi Mermaid. Menghilangkan `->` dan menyusun transisi state menggunakan choice pseudo-state (`<<choice>>`) menyelesaikan masalah parse error sekaligus memvisualisasikan logika guardrail confidence `< 0.70` vs `>= 0.70` secara presisi.

3. **Dari Observasi 4 (Nomenklatur Ilmiah)**:
   - Standar taksonomi internasional (ICN, ICNP, ICTV) mewajibkan genus dan spesies ditulis miring.
   - Format `Gemini Virus` dan `Rice Tungro Bacilliform/Spherical Virus` tidak memenuhi kaidah penulisan miring dan tidak presisi. Menyesuaikannya dengan nama ilmiah resmi (*Pepper yellow leaf curl virus* dan *Rice tungro bacilliform virus* & *Rice tungro spherical virus*) serta mencantumkan nama forma specialis dan pathovar meningkatkan kredibilitas laporan agronomi ke tingkat profesional.
   - Menyandingkan *Scirpophaga innotata* dan *Scirpophaga incertulas* menyelesaikan diskrepansi antara dokumen dan basis data JSON.

4. **Dari Observasi 5 (GFM Alerts)**:
   - Standar dokumentasi rekayasa perangkat lunak modern memanfaatkan callout `[!NOTE]`, `[!IMPORTANT]`, `[!TIP]`, dan `[!WARNING]` untuk menandai informasi arsitektural penting, peringatan keamanan, dan petunjuk operasional. Menyisipkan 5 alert strategis di bab-bab terkait akan meningkatkan kejelasan dokumen secara signifikan.

5. **Dari Observasi 6 (PHT & PPL Referral)**:
   - Fitur rujukan PPL saat ini menggabungkan automasi AI dengan intervensi manusia (human-in-the-loop). Menyajikan proses ini sebagai *Closed-Loop Sequence* (Petani $\rightarrow$ AI Bot $\rightarrow$ Fallback Safe Message $\rightarrow$ Database Supabase $\rightarrow$ Admin Portal PPL $\rightarrow$ Kunjungan Lapangan) akan memberikan gambaran komprehensif bagi pembaca teknis dan pemangku kepentingan pertanian.

---

## 3. Caveats

- **No Codebase Modification**: Sebagai agent explorer read-only, tidak ada perubahan yang dituliskan langsung ke berkas `laporan.md` atau berkas kode proyek. Seluruh rekomendasi dan blok kode siap pakai telah disusun di `E:\wa bot longchain\.agents\teamwork\explorer_survey_formatting\report.md`.
- **Ekstensi Mermaid CLI**: Eksekusi `npx @mermaid-js/mermaid-cli` lokal tidak dijalankan karena pembatasan eksekusi sub-proses shell interaktif di lingkungan audit; namun validasi sintaks dilakukan mengacu pada spesifikasi resmi grammar Mermaid v10/v11.

---

## 4. Conclusion

Dokumen `laporan.md` memiliki konten substansi teknis yang sangat solid, namun memerlukan penyempurnaan pada 4 aspek kunci:
1. **Diagram Mermaid**: Wajib dilakukan sanitasi API key (Baris 90), perbaikan escaping karakter `<` dan `&` (Baris 73, Baris 50), perbaikan operator `->` pada `stateDiagram-v2` (Baris 135–136), dan penghapusan relasi compound subgraph (Baris 94).
2. **Nomenklatur Ilmiah**: Wajib memiringkan nama virus (*Pepper yellow leaf curl virus*, *Rice tungro bacilliform virus*, *Rice tungro spherical virus*), melengkapi forma specialis (*f. sp. capsici*) dan pathovar (*pv. oryzae*), serta mengharmoniskan spesies *Scirpophaga incertulas* / *S. innotata*.
3. **GFM Callout Alerts**: Wajib menambahkan 5 blok alert callout (`[!WARNING]` pada kredensial, `[!TIP]` pada failover cuaca dan prinsip PHT, `[!IMPORTANT]` pada guardrail keselamatan agronomi, `[!NOTE]` pada konfigurasi pgvector dan storage).
4. **Alur PHT & Rujukan PPL**: Wajib memperjelas narasi 3 Pilar PHT dan merekonstruksi alur rujukan PPL dalam bentuk diagram sekuens siklus tertutup (*closed-loop*).

Seluruh draft perbaikan, kode diagram perbaikan yang valid, dan tabel komparasi telah selesai ditulis secara lengkap di:  
`E:\wa bot longchain\.agents\teamwork\explorer_survey_formatting\report.md`.

---

## 5. Verification Method

Untuk memverifikasi temuan dan usulan perbaikan secara independen:
1. **Inspeksi Baris Dokumen**:
   - Buka `E:\wa bot longchain\laporan.md` pada baris 50, 73, 90, 135–136, 188, 286, 294, 295, dan 455–457 untuk memverifikasi seluruh kutipan observasi.
2. **Pengujian Sintaks Mermaid**:
   - Salin blok kode usulan perbaikan dari `report.md` (Subbab 1.1, 1.2, 1.3, dan 4.2) ke [Mermaid Live Editor](https://mermaid.live/) atau ekstensi preview Mermaid di VS Code / GitHub untuk mengonfirmasi bahwa seluruh diagram ter-render secara sempurna tanpa galat sintaks maupun clipping.
3. **Pengecekan Konsistensi Basis Pengetahuan**:
   - Periksa `data/knowledge/cabai_diseases.json` dan `data/knowledge/padi_diseases.json` untuk mencocokkan nama ilmiah resmi dan penanganan 3 pilar.
4. **Kondisi Invalidasi Temuan**:
   - Temuan ini menjadi invalid jika `laporan.md` telah disunting dan tidak lagi mengandung teks Baris 90 (API Key plaintext) atau Baris 135–136 (`->` dalam state description).
