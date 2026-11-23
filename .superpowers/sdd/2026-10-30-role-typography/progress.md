# SDD ledger — plan: docs/superpowers/plans/2026-10-30-role-typography.md

## Setup

- Spec: `docs/superpowers/specs/2026-10-30-role-typography-design.md` (exist, dibaca, berlaku sebagai otoritas).
- Branch: `main`, dikerjakan langsung di working tree (pengguna memberi persetujuan pada sesi ini).
- Cara eksekusi: inline di sesi controller. Harness hanya menyediakan subagent Browser/CodeReview/ComputerUse — tidak ada tipe subagent implementer. Gate review: satu subagent `CodeReview` atas seluruh perubahan di akhir (plus satu re-review scoped bila ada temuan).
- Commit: ditunda sampai pengguna menyetujui (Global Constraints + git safety). Bukti per task = daftar file + output tes.

## Rulings (pre-flight)

1. `Ruling: implementasi tanpa commit per task — why: Global Constraints plan + aturan git (tidak commit tanpa permintaan eksplisit) — cost if wrong: perubahan antar task tidak terpisah di history, dimitigasi dengan daftar file per task di ledger ini.`
2. `Ruling: eksekusi inline menggantikan dispatch implementer subagent — why: tipe subagent implementer tidak tersedia di harness ini — cost if wrong: tidak ada review per task, risiko regresi baru tertangkap pada review akhir; dimitigasi dengan menjalankan tes tiap task sesuai plan.`
3. `Ruling: opsi <select> di TypographyEditor ditambah family yang sedang dipakai — why: family hasil resolve Google Fonts tidak ada di daftar opsi sehingga <select> tampil kosong walau nilai tersimpan — cost if wrong: daftar opsi sedikit lebih panjang dari template font, tanpa efek data.`

## Pre-flight conflict scan

| # | Task pair / konsumen | Produces → Consumes | Temuan |
|---|---|---|---|
| 1 | T1 → T5, T6 | `TypographyConfig`, `parse_typography`, `is_auto`, `merge_typography`, `required_families`, `ROLE_NAMES`, `UpdateTypographyRequest` | OK — semua diekspor di kode Task 1; T6 memakai `ROLE_NAMES` + `is_auto` + `parse_typography`. |
| 2 | T2 → T5, T11 | kolom `typography` pada `presentations` dan `slides` | OK — T2 menambah dua kolom; T5 menetapkan/tulis, T11 menambah field TS. |
| 3 | T3 → T5, T6 | `ensure_role_markers(html) -> (html, changed)` | OK — satu definisi, dua konsumen. |
| 4 | T4 → T10 | `POST /api/v1/ppt/fonts/google` → `{family, url, faces[]}` | OK — `GoogleFontResponse` di T10 cocok; `httpx` sudah dependensi runtime (`pyproject.toml:26`). |
| 5 | T5 → T6 | `apply_role_markers_to_presentation(session, id)` | OK — T6 mengimpor dari `services.typography_service`. |
| 6 | T5 → T11 | `PATCH /presentation/{id}/typography` body `{typography?, fonts?}` | OK — `TypographyService.updatePresentationTypography` mengirim bentuk yang sama; guard `model_fields_set` menjaga request fonts-only. |
| 7 | T5 → T11 | `slide_update` menerima `typography` | OK — `sqlmodel_update(model_dump(exclude={"id","presentation","index"}))` menerima kolom baru. |
| 8 | T7 → T8, T9, T10, T11 | `resolveTypography`, `isAutoTypography`, `typographyStyleCss`, `TYPOGRAPHY_ROLES`, tipe | OK — semua diekspor di Task 7. |
| 9 | T9 → T7 | `applyTypographyToSlide(layout, config)` | OK — konsumen tunggal `V1ContentRender`, hook dipindah sebelum early return. |
| 10 | T10 → T11 | props `value/onChange/templateFonts/scope/onFontResolved/resolveGoogleFont` | OK — T11 mengisi semua; `onClose` bukan prop. |
| 11 | T10 (internal) | daftar opsi `<select>` vs nilai tersimpan | TEMUAN — family hasil Google lookup tidak ada di opsi → lihat Ruling 3. |

Self-consistency per task (tes vs kode yang dispesifikasikan): T1 6 tes/6 fungsi; T2 migrasi + model; T3 5 tes; T4 cache Google + endpoint; T5 endpoint + backfill + 6 tes baru; T6 builder prompt + 2 tes; T7 3 tes/3 fungsi; T8 injeksi CSS; T9 transform layout + 1 tes; T10 panel + service; T11 wiring. Tidak ada task yang tes-nya bertentangan dengan kodenya.

Hal yang wajib diverifikasi saat task berjalan (belum bisa dipastikan dari plan): props `ConfigurationSelects` (`config`, `onConfigChange`), nama ekspor `PresentationGenerationApi`, bentuk `presentationData.slides`, head Alembic `026c0ba8b35c`, dan `mergeFont`/`mergeFontForTextSelection` meneruskan field `manual`.

## Progress

- Task 1: complete — `servers/fastapi/models/typography.py`, `tests/unit/test_typography_config.py` (6 passed).
- Task 2: complete — `models/sql/presentation.py`, `models/sql/slide.py`, `alembic/versions/a1c4e7b9d2f5_add_typography_columns.py`, `tests/unit/test_typography_columns.py` (2 passed; `alembic heads` = a1c4e7b9d2f5 saja).
- Task 3: complete — `services/smart_typography_roles.py`, `tests/unit/test_smart_typography_roles.py` (5 passed).
  - `Ruling: tes plan memakai text-2xl (24px) dengan title 48px — di luar band 0.6×title (28.8) sehingga kontradiksi dengan spec §7; diubah ke text-3xl (30px) — cost if wrong: kasus 24px tidak diuji eksplisit, tetap tercakup aturan band.`
  - `Ruling: tes plan membandingkan posisi atribut title dengan teks elemen itu sendiri (selalu lebih kecil) sehingga mustahil lulus; diganti menjadi elemen footer tidak ber-title dan title muncul setelah footer — cost if wrong: assert urutan lebih longgar, inti (footer bukan title) tetap teruji.`
- Task 4: complete — `services/google_fonts.py`, `api/v1/ppt/endpoints/fonts.py` (`POST /fonts/google`), `tests/unit/test_google_fonts.py` (3 passed).
- Task 5: complete — `services/typography_service.py`, `api/v1/ppt/endpoints/presentation.py` (param create, `PATCH /{id}/typography`, backfill `slide_update`), `models/generate_presentation_request.py`, tes service + API + slide_update (15 passed).
  - `Ruling: migrations.py REVISION_HEAD dinaikkan ke a1c4e7b9d2f5 dan ditambah tes migrasi kolom typography — why: test_migrations mengunci head sehingga 10 tes lama gagal setelah ada migrasi baru (gap plan) — cost if wrong: konstanta head harus ikut berubah bila migrasi berikutnya ditambah.`
  - Catatan lingkungan: tes backend di Windows butuh `APP_DATA_DIRECTORY` lokal (default `/tmp/presenton` tidak valid), dan 11 kegagalan sisa di `tests/unit` bersifat lingkungan (export runtime tidak ada, chmod/POSIX, path font nextjs) — bukan akibat perubahan ini.
- Task 6: complete — `utils/llm_calls/typography_prompt.py`, `utils/llm_calls/generate_smart_presentation.py` (import, param `typography` di `get_smart_messages` + `generate_smart_presentation`, `typography_block`, `+ typography_block`), `api/v1/ppt/endpoints/presentation.py` (`typography=presentation.typography` pada panggilan generate + backfill penanda setelah commit akhir), `tests/unit/test_typography_prompt.py` (2 passed; 44 passed bersama `test_smart_presentation_generation.py`; suite penuh 863 passed, 11 kegagalan lingkungan yang sama).
  - `Ruling: backfill penanda Smart diletakkan setelah commit akhir (bukan tepat setelah \`deck = await generation_task\`) lalu slide dimuat ulang — why: pada titik di plan, slide hasil recovery belum tersimpan sehingga tidak ikut ditandai, dan payload SSE selesai akan membawa HTML tanpa penanda — cost if wrong: satu query ulang slide per generasi Smart bertipografi.`
  - `Ruling: backfill hanya dijalankan bila presentasi punya tipografi non-Auto — why: mode Auto harus identik dengan perilaku lama, dan menulis ulang HTML tanpa manfaat melanggar Global Constraints — cost if wrong: penanda baru dibuat saat pengguna menyimpan tipografi (PATCH sudah memicunya).`
- Task 7: complete — `components/typography/effective.ts`, `tests/typography-effective.test.mjs` (3 passed via `node --test`).
  - Catatan lingkungan: `servers/nextjs` belum punya `node_modules`, jadi `npm ci` dijalankan lebih dulu (exit 0, 890 paket) agar esbuild tersedia untuk tes node.
- Task 8: complete — `SmartHtmlSlide.tsx` (prop `typography`, `<style>` di `previewDocument`, `useSlideFontAssets` menggabungkan CSS, diteruskan ke dua varian), `SmartHtmlEditor.tsx` (prop + injeksi CSS + fallback), `PresentationRender.tsx`, `SlideThumbnailCard.tsx`, `chat-widgets.tsx` (hitung `resolveTypography` dari state presentasi + slide). `npx tsc --noEmit` bersih; `npm run lint` exit 0 (67 warning lama, tidak ada temuan pada file yang diubah).
  - `Ruling: field `typography` ditambahkan ke tipe `Slide` (`app/(presentation-generator)/types/slide.ts`) sekarang, padahal plan menaruhnya di Task 11 — why: Task 8 membaca `slide.typography` sehingga kompilasi gagal tanpa field itu — cost if wrong: Task 11 cukup memakai field yang sudah ada, tidak ada duplikasi.`
- Task 9: complete — `components/typography/apply-to-slide.ts`, `components/slide-editor/types.ts` (`Font.manual`), `components/slide-editor/text/TextToolbar.tsx` (`updateFont` menandai manual), `app/(presentation-generator)/components/V1ContentRender.tsx` (transform via `typographyLayout`), `tests/typography-apply-to-slide.test.mjs` (4 passed; 7 passed bersama tes Task 7). `npx tsc --noEmit` bersih; `npm run lint` 0 error, tanpa temuan pada file yang diubah.
  - `Ruling: saat edit memakai selection range, `manual: true` juga dipasang pada `element.font` (bukan hanya run) — why: `applyTextRunFontToSelection` hanya menambal `runs`, sehingga transform akan tetap menimpa elemen yang sudah diedit pengguna — cost if wrong: satu field tambahan pada font elemen.`
  - `Ruling: `V1ContentRender` melewati `applyTypographyToSlide` bila konfigurasi Auto (`isAutoTypography`) — why: menjaga identitas objek layout agar Auto berperilaku persis seperti sebelumnya dan tidak memicu render ulang Konva tanpa alasan — cost if wrong: satu pemeriksaan tambahan per render.`
- Task 10: complete — `app/(presentation-generator)/typography/components/TypographyEditor.tsx`, `app/(presentation-generator)/services/api/typography.ts`. `npx tsc --noEmit` bersih; `npx eslint` pada dua file baru exit 0; tes node Task 7/9 tetap 7 passed.
  - `Ruling: tipe `ResolvedTypography` ditambahkan di `effective.ts` dan `resolveTypography` mengembalikannya — why: tipe `TypographyConfig` membuat `resolved.roles[role]` dianggap nullable sehingga panel tidak bisa dikompilasi tanpa cast di banyak tempat — cost if wrong: perubahan tipe tambahan (aditif), semua pemanggil lama tetap sah.`
  - `Ruling (Preflight Ruling 3): daftar opsi `<select>` keluarga font ikut memuat family yang sedang tersimpan pada `value` — why: family hasil resolusi Google Fonts tidak ada di opsi sehingga select tampil kosong/auto padahal nilai tersimpan berbeda — cost if wrong: opsi tambahan muncul hanya bila memang dipakai.`
- Task 11: complete — `upload/type.ts` (`typography`/`fonts` + import), `upload/components/UploadPage.tsx` (config default + dua payload `createPresentation`), `outline/components/OutlinePage.tsx` (config default), `services/api/presentation-generation.ts` (import, destructuring, tipe, body), `upload/components/ConfigurationSelects.tsx` (Popover "Tipografi" berisi `TypographyEditor`), `presentation/components/PresentationHeader.tsx` (prop `onOpenTypography` + tombol), `presentation/components/PresentationPage.tsx` (state, `openTypography`/`selectTypographyScope`/`saveTypography`, Dialog cakupan global/per slide). Verifikasi: `npx tsc --noEmit` bersih; `npm run lint` exit 0 (67 warning lama, satu-satunya temuan pada file berubah adalah warning `<img>` logo yang sudah ada di `PresentationHeader.tsx:575`); `npm run build` exit 0.
  - `Ruling: dialog tipografi memakai primitif shadcn `Dialog`/`DialogContent`/`DialogTitle`, bukan `import Modal from "./Modal"` seperti teks plan — why: halaman ini tidak punya komponen `Modal`; `Dialog` sudah dipakai `PresentationHeader` dan `react-dialog` sudah menjadi dependensi — cost if wrong: gaya dialog berbeda dari mockup plan, fungsi penyimpanan tidak berubah.`
  - `Ruling: panel di halaman upload dirender di dalam `Popover` (pemicu "Tipografi"), bukan blok inline setelah kontrol bahasa — why: `ConfigurationSelects` adalah satu baris pill flex, blok multi-baris akan merusak tata letak toolbar — cost if wrong: pengguna membuka panel lewat popover alih-alih melihatnya langsung.`
  - `Ruling: `DEFAULT_OUTLINE_CONFIG` di `outline/components/OutlinePage.tsx` ikut diisi `typography: null, fonts: {}` walau file ini tidak tercantum pada daftar file Task 11 — why: `PresentationConfig` mendapat dua field wajib sehingga `tsc` gagal tanpa nilai default di sini — cost if wrong: dua nilai default tambahan yang memang diperlukan tipe.`
  - `Ruling: `saveTypography` memakai state `typographySaving`/`typographyError` dan menampilkan pesan gagal di dialog — why: `saveTypography` asynchronous dari `onClick`, kegagalan PATCH tanpa penanganan akan menghasilkan unhandled rejection tanpa umpan balik — cost if wrong: dua state UI tambahan.`
  - `Ruling: prop `disabled` tombol Tipografi memakai `isStreaming === true` — why: `isStreaming` bertipe `boolean | null` sehingga `tsc` menolak — cost if wrong: tidak ada, semantik sama.`

## Review menyeluruh (whole-branch) dan fix round 1

Reviewer independen menemukan 4 BLOCKING + 5 SHOULD FIX. Semua BLOCKING dan S1–S4, N2, N3, N7 diperbaiki pada putaran ini:

- B1 (export PDF/PPTX mengabaikan tipografi pada slide Smart dan Template V2) — diperbaiki di `app/(export)/pdf-maker/PdfMakerPage.tsx`: CSS peran per slide (`scopeTypographyCss` memberi prefiks id slide karena seluruh deck adalah satu dokumen) untuk slide Smart, dan `applyTypographyToSlide` pada `slide.ui` untuk jalur `TemplateV2HtmlSlidePreview`. Thumbnail dashboard juga memakai jalur yang sama (`PresentationCard`).
- B2 (simpan tipografi global selalu 422 pada deck berbasis template) — `merge_font_urls` tidak lagi memvalidasi ulang entri yang tidak berubah; hanya URL baru/berubah yang diperiksa. Tes baru: `test_merge_keeps_already_stored_urls_without_revalidating`, `test_resaving_existing_font_entries_is_allowed`.
- B3 (input ukuran font tidak bisa diketik) — `TypographyEditor` memakai draft string per peran (`sizeDrafts`) dan memvalidasi saat blur, sehingga `12`, `16`, `20`, dan seterusnya bisa diketik.
- B4 (override render ikut tersimpan ke `slides.ui`) — `TemplateV2KonvaSlide` menerima prop `typography` dan menghitung `renderUi` untuk lapisan gambar + `StaticHtmlTextLayer`; `uiDraft` tetap berisi ukuran tersimpan sehingga `commitUi` tidak pernah menulis override. `V1ContentRender` kembali mengirim `baseLayout` + `typographyConfig`.
- S1: guard `not is_auto(...)` ditambahkan pada `PATCH /{id}/typography` (tes: `test_auto_typography_does_not_rewrite_smart_html`).
- S2: `SlideScale` menerima prop `typography`; `PresentationCard` mengirim data deck sendiri sehingga thumbnail tidak memakai state Redux presentasi lain.
- S3: blok `<style>` di `SmartHtmlSlide` memakai helper `styleBlock` yang meng-escape `</style`.
- S4: `slide_update` memvalidasi `typography` lewat `parse_typography` → 422 (tes: `test_slide_update_rejects_out_of_range_typography`).
- S5: `OutlinePage` meneruskan `typography`/`fonts` pada regenerasi outline.
- N2: tombol "Gunakan" Google Font mengisi peran yang belum punya family (bukan selalu `title`). N3: `PresentationData.typography` ditolak; N7: `review_diff.txt` dan `tmp_q.py` dihapus.
- Ditunda dengan sadar: N4 (rate-limit `/fonts/google`), N5 (heuristik penanda: early-return bila sudah ada satu penanda, elemen footer/badge jatuh ke `body`), N6 (otorisasi `PATCH /typography` sama dengan endpoint tetangga). Tidak ada tes DOM untuk input ukuran/paritas export (tidak ada harness React di repo).
- Verifikasi putaran fix: `pytest` pada 3 file tes terkait 20 passed; `node --test` 7 passed; `npx tsc --noEmit` bersih; `npm run lint` exit 0 (67 warning lama); `npm run build` exit 0.


## Re-review putaran fix 1 (scoped) dan adjudikasi

Re-reviewer independen memverifikasi sembilan temuan: B1-B4, S1-S5 semuanya ADDRESSED (bukti file:line pada laporan). Diff: `.superpowers/sdd/2026-10-30-role-typography/round1-fix.diff`.

Temuan baru dari re-review:

- CRITICAL (di luar diff fix, load-bearing) - `PresentationWithSlides` tidak punya field `typography`, sehingga Pydantic membuang nilai dari `_presentation_response_data` pada `GET /{id}`, `GET /all`, `PATCH /update`, `duplicate`, dan stream SSE. Akibatnya `presentationData.typography` selalu `undefined` di frontend: dialog tipografi terbuka kembali sebagai Auto setelah simpan, dan export/thumbnail pada cakupan global tetap tampil Auto (sisa gejala B1/S2). Diperbaiki: field `typography: Optional[dict[str, Any]] = None` pada `models/presentation_with_slides.py`; tes `test_presentation_response_exposes_typography`.
- MINOR - CSS peran disuntikkan ke `document.head` tanpa scope pada renderer in-page (`SmartHtmlSlide` varian Linux/Electron dan `SmartHtmlEditor`), sehingga pada dokumen yang memuat beberapa slide Smart CSS slide terakhir menang untuk semua slide. Diperbaiki dengan `scopeTypographyCss` yang dipindah ke `components/typography/effective.ts` (dipakai ulang oleh `PdfMakerPage`) dan scope `[data-smart-slide-instance="<id>"]` per instance; tes node `scoping prefixes every rule with the slide container`.

Ruling: field `typography` ditambahkan pada model response (bukan diambil dari `model_dump` lewat `extra="allow"`) - why: konsisten dengan `fonts`/`theme` dan menjaga kontrak response tetap eksplisit - cost if wrong: satu field tambahan pada schema response.

Verifikasi: `pytest tests/unit -k presentation` 153 passed; `node --test` 8 passed; `npx tsc --noEmit` bersih; `npm run lint` exit 0 (67 warning lama); `npm run build` exit 0 (Compiled successfully).

## Verifikasi Akhir

- pytest penuh `tests/unit`: 869 passed, 11 failed - kegagalan yang sama seperti sebelum fitur (runtime export tidak ada, chmod/POSIX, path font nextjs, auth bootstrap). Tidak ada kegagalan baru.
- `node --test tests/typography-effective.test.mjs tests/typography-apply-to-slide.test.mjs`: 8 passed.
- `npx tsc --noEmit`: bersih. `npm run lint`: exit 0, 67 warning lama. `npm run build`: exit 0, "Compiled successfully".
- `uv run alembic heads`: satu head, `a1c4e7b9d2f5`.
- Regresi bahasa: label "Indonesian (Bahasa Indonesia)" masih ada di `upload/type.ts:97`.
- Image Docker: BELUM terverifikasi. `docker compose up -d --build production` berjalan sampai tahap "naming to docker.io/library/presenton-production:latest" lalu gagal: `failed to receive status: rpc error: code = Unavailable desc = error reading from server: EOF`; percobaan ulang gagal dengan `Docker Desktop is unable to start` dan daemon tetap mati setelah menunggu. Ini kegagalan lingkungan (Docker Desktop), bukan kegagalan build - seluruh tahap kompilasi image selesai.
- Cek manual paritas preview vs PDF dan tampilan Auto belum bisa dijalankan karena aplikasi butuh container yang sedang mati.

### Pembaruan Verifikasi Akhir (setelah restart Docker Desktop)

- `docker compose up -d --build production`: exit 0, `Image presenton-production Built` + container dijalankan ulang.
- `docker compose logs --tail=60 production`: `Nginx started successfully`, `Ready in 0ms`, `Started server process`, `Migrations run successfully`; tidak ada Traceback.
- `alembic heads` di dalam container: satu head `a1c4e7b9d2f5`; `alembic current`: `a1c4e7b9d2f5 (head)`.
- Model response pada image yang berjalan: `'typography' in PresentationWithSlides.model_fields` -> True (bukti Critical dari re-review sudah ikut ter-build).
- Endpoint HTTP tidak bisa dipakai untuk smoke test karena deployment ini mengaktifkan auth (`/openapi.json` dan `/presentation/all` sama-sama 401), jadi verifikasi kontrak memakai tes unit + introspeksi model di container.
- Sisa yang hanya bisa dilakukan manual oleh pengguna: buat presentasi Smart dengan Judul 52 px/Inter lalu bandingkan preview vs PDF export, dan pastikan presentasi Auto tampil sama seperti sebelumnya.
