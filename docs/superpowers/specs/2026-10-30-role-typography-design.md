# Spesifikasi: Tipografi Berbasis Peran (Judul, Sub Judul, Deskripsi)

- Tanggal: 2026-10-30
- Pendekatan terpilih: **A — override saat render**
- Status: desain disetujui, siap dibuatkan rencana implementasi

## 1. Tujuan

1. Pengguna dapat memilih **jenis font** dan **ukuran font** untuk tiga peran teks: Judul, Sub Judul, Deskripsi.
2. Pilihan tersedia saat generate (halaman upload) dan setelah generate (editor), dengan cakupan **seluruh presentasi** dan **override per slide**.
3. Setiap field bersifat **Auto** bila tidak diisi; Auto berarti memakai nilai template/LLM apa adanya.
4. **Preview dan hasil export identik**, termasuk pada mode Smart yang sebelumnya tidak bisa diatur ukuran fontnya.

## 2. Non-tujuan

- Mengedit font per elemen pada slide Smart (kontrol tetap berbasis peran).
- Font weight, line-height, letter-spacing per peran.
- Menulis ulang HTML/layout secara permanen sehingga Auto tidak bisa dikembalikan.
- Mengubah runtime `@presenton/export-core` (versi tetap `v1.0.34`).

## 3. Keputusan yang dikunci

| Aspek | Keputusan |
|---|---|
| Tempat memilih | Halaman upload dan editor |
| Cakupan editor | Global presentasi + override per slide |
| Sumber font | Font lokal yang tersedia + Google Fonts |
| Peran pada slide Smart | Ditandai saat generate (`data-text-role`) + fallback heuristik |

## 4. Model data

### 4.1 `presentations.typography` (JSON, nullable)

```json
{
  "version": 1,
  "roles": {
    "title":    { "family": "Inter", "size": 52 },
    "subtitle": { "family": null,    "size": 28 },
    "body":     { "family": null,    "size": null }
  }
}
```

- `null` pada `family` atau `size` berarti Auto untuk field tersebut.
- `size` adalah piksel pada kanvas 1280×720.
- Presentasi lama: kolom `NULL` → perilaku render tidak berubah sama sekali.

### 4.2 `slides.typography` (JSON, nullable)

Bentuk objek sama, hanya berisi field yang di-override. Merge dilakukan per field:

```
efektif.roles.<role>.<field> = slide.typography ?? presentation.typography ?? null
```

### 4.3 `presentation.fonts` (sudah ada)

Peta `family -> URL` tetap menjadi satu-satunya sumber berkas font untuk preview, Konva, dan Chromium export. Setiap family yang dipilih wajib punya entri di sini.

### 4.4 Model SQLAlchemy/SQLModel

- `servers/fastapi/models/sql/presentation.py`: tambah `typography: Optional[dict] = Field(sa_column=Column(JSON), default=None)`, salin di `get_new_presentation()`.
- `servers/fastapi/models/sql/slide.py`: tambah `typography: Optional[dict] = Field(sa_column=Column(JSON), default=None)`, salin di `get_new_slide()`.

### 4.5 Migrasi Alembic

- File baru di `servers/fastapi/alembic/versions/`, `down_revision = "026c0ba8b35c"` (head saat ini).
- Menambah dua kolom `sa.JSON()` nullable: `presentations.typography` dan `slides.typography`.
- Wajib memakai pola guard seperti `9b2d1c4e5f6a_add_fonts_column_to_presentations.py` (`_has_table` + `_has_column`) agar aman dijalankan berulang dan pada SQLite.
- `downgrade()` menghapus kedua kolom dengan guard yang sama.
- Migrasi tidak mengisi data lama (biarkan `NULL`).

## 5. Skema dan validasi backend

File baru `servers/fastapi/models/typography.py`:

- `TypographyRoleConfig`: `family: Optional[str]` (strip, string kosong → `None`, maksimum 120 karakter), `size: Optional[int]` (`ge=8`, `le=200`). `model_config = ConfigDict(extra="forbid")`.
- `TypographyRoles`: `title`, `subtitle`, `body` bertipe `TypographyRoleConfig` (default kosong).
- `TypographyConfig`: `version: Literal[1] = 1`, `roles: TypographyRoles`.
- `merge_typography(base, override) -> TypographyConfig`: merge per field, `None` di override berarti "tidak menimpa".
- `is_auto(typography) -> bool`: `True` bila semua field `None` (dipakai untuk melewati seluruh logika tipografi).

Titik masuk request yang diperluas (semua opsional, default `None` sehingga request lama tetap valid):

- `POST /presentation/create` (`create_presentation` di `servers/fastapi/api/v1/ppt/endpoints/presentation.py`): dua parameter `Body` baru, `typography: Optional[TypographyConfig]` dan `fonts: Optional[dict[str, str]]`. Ini jalur yang dipakai UI untuk mode Standard maupun Smart (`generation_mode`).
- `GeneratePresentationRequest` dan `GenerateSmartPresentationRequest` di `servers/fastapi/models/generate_presentation_request.py`: field yang sama, untuk paritas API sync/async.

## 6. Registry dan penyimpanan font

Tiga sumber family:

1. **Font presentasi** — sudah ada di `presentation.fonts` (font template, community, upload).
2. **Font lokal bawaan** — berkas statis `/vendor/fonts/...` yang didefinisikan di `servers/nextjs/components/slide-editor/text/local-fonts.ts` (`LOCAL_FONT_OPTIONS`).
3. **Google Fonts** — diunduh dan di-cache oleh backend.

### 6.1 Endpoint Google Fonts

`POST /api/v1/ppt/fonts/google` (ditambahkan di `servers/fastapi/api/v1/ppt/endpoints/fonts.py`):

```json
{ "family": "Playfair Display", "weights": [400, 700] }
```

Respons:

```json
{
  "family": "Playfair Display",
  "url": "/app_data/fonts/google/playfair-display/400.woff2",
  "faces": [
    { "weight": 400, "style": "normal", "url": "/app_data/fonts/google/playfair-display/400.woff2" },
    { "weight": 700, "style": "normal", "url": "/app_data/fonts/google/playfair-display/700.woff2" }
  ]
}
```

Aturan implementasi:

- Slug: nama family di-lowercase, karakter non-alnum menjadi `-`, maksimum 60 karakter.
- Ambil CSS dari `https://fonts.googleapis.com/css2?family=<Family>:wght@400;700&display=swap` dengan `User-Agent` modern agar Google mengembalikan `woff2`.
- Unduh maksimum 2 berkas (400 normal, 700 normal), masing-masing ≤ 5 MB, timeout 10 detik.
- Simpan ke `app_data/fonts/google/<slug>/<weight>.woff2` + `manifest.json`; cache hit mengembalikan hasil tanpa jaringan.
- Berkas disajikan lewat mount `/app_data` yang sudah ada di FastAPI; URL dikembalikan melalui `absolute_fastapi_asset_url()` agar tetap benar pada Electron/split origin.
- Kegagalan unduh → `502` dengan pesan jelas; tidak ada state yang tersimpan.
- Nama family yang tidak ditemukan → `404`.

### 6.2 Penggabungan ke `presentation.fonts`

Body `PATCH /presentation/{id}/typography` dan field `fonts` pada request generate menerima `dict[str, str]`. Backend hanya **menambahkan** entri (tidak pernah menghapus entri lama).

Validasi URL font: harus diawali `/vendor/fonts/` atau `/app_data/fonts/google/` (termasuk bentuk absolut yang dihasilkan `absolute_fastapi_asset_url`). Nilai lain → `422`.

Validasi family: setiap `family` non-null pada `typography` harus ada di gabungan `presentation.fonts` + registry lokal. Jika tidak ada → `422` dengan `detail` berisi daftar family yang belum ter-resolve.

## 7. Alur generate

### 7.1 Mode Standard / Template

- `typography` dan `fonts` disimpan pada presentasi baru. Layout dan struktur tidak diubah.
- Tidak ada perubahan prompt.

### 7.2 Mode Smart

Jika minimal satu field tidak Auto, prompt di `servers/fastapi/utils/llm_calls/generate_smart_presentation.py` menerima blok tambahan (hanya peran yang diisi):

```text
Typography roles:
- title: font "Inter", 52px
- subtitle: 28px
- body: auto

Mark every text container with data-text-role="title" | "subtitle" | "body".
Exactly one title per slide. Use subtitle only for a visible secondary heading.
All remaining body copy, card text, labels, and captions use body.
Never add data-text-role to decorative layers (data-decorative="true").
```

Jika semua Auto, prompt tidak berubah dan penanda tidak diminta.

### 7.3 Backfill penanda peran (fallback)

Modul baru `servers/fastapi/services/smart_typography_roles.py`:

`ensure_role_markers(html: str) -> tuple[str, bool]` — mengembalikan HTML dan status perubahan.

- Jika HTML sudah memuat `data-text-role`, kembalikan apa adanya (`False`).
- Kandidat: elemen yang memiliki teks langsung, bukan `aria-hidden="true"`, bukan `data-decorative="true"`, bukan `script`/`style`/`svg`.
- Skor ukuran font per kandidat, berurutan prioritas:
  1. inline `style="font-size:NNpx"`,
  2. kelas Tailwind `text-[NNpx]`,
  3. skala Tailwind (`text-9xl`=128, `text-8xl`=96, `text-7xl`=72, `text-6xl`=60, `text-5xl`=48, `text-4xl`=36, `text-3xl`=30, `text-2xl`=24, `text-xl`=20, `text-lg`=18, `text-base`=16, `text-sm`=14, `text-xs`=12),
  4. default tag (`h1`=48, `h2`=36, `h3`=30, lainnya 16).
- `title` = skor tertinggi (jika seri, yang lebih dulu di DOM).
- `subtitle` = skor tertinggi berikutnya dengan `0.6 × title ≤ skor < title`; jika tidak ada, tidak dipasang.
- `body` = seluruh kandidat sisanya.
- Penulisan atribut memakai `html.parser` stdlib agar teks dan atribut lain tidak berubah; hasil harus idempoten.
- Setelah diterapkan, set `slide.properties["typography_roles_version"] = 1` agar tidak dijalankan ulang.

Backfill dijalankan saat: (a) generate smart dengan tipografi tidak Auto, (b) pertama kali `typography` disimpan pada presentasi/slide smart yang sudah ada. Slide tanpa teks tidak ditandai dan tidak ditandai sebagai sudah diproses.

## 8. Render

### 8.1 Nilai efektif

File baru `servers/nextjs/components/typography/effective.ts`:

- `resolveTypography(presentation, slide): TypographyConfig` — merge per field.
- `isAutoTypography(config): boolean`.
- Tipe TypeScript `TypographyConfig`, `TypographyRoleConfig` di file yang sama.

### 8.2 Mode Smart

`SmartHtmlSlide` menerima prop `typography?: TypographyConfig`:

- Membangun CSS:
  ```
  section[data-slide-type] [data-text-role="title"]{font-family:"Inter",sans-serif!important;font-size:52px!important;line-height:1.1!important}
  section[data-slide-type] [data-text-role="subtitle"]{...}
  section[data-slide-type] [data-text-role="body"]{...}
  ```
  Hanya field yang tidak Auto yang ditulis; `line-height:1.1`/`1.3` ditambahkan hanya saat `size` diisi agar teks tidak bertumpuk.
- Disuntik pada dua jalur render: `previewDocument()` (iframe) dan `useSlideFontAssets()` (renderer in-page Linux).
- Font-family memakai `cssFontFamilyStack` yang sudah ada.
- Prop yang sama diteruskan oleh `SmartHtmlEditor`, `PresentationRender`, `SlideThumbnailCard`, serta pratinjau di `presentation/components/chat/chat-widgets.tsx`, untuk setiap tempat yang merender `SmartHtmlSlide` di dalam konteks presentasi (bukan pratinjau community/template yang tidak memiliki konfigurasi tipografi).
- `data-decorative="true"` dikecualikan lewat `:not([data-decorative="true"])`.

### 8.3 Mode Standard / V2 (Konva)

File baru `servers/nextjs/components/typography/apply-to-slide.ts`:

`applyTypographyToSlide(slideLayout, typography) -> slideLayout` (mengembalikan salinan, tidak memutasi state):

- Kumpulkan elemen teks (`type` mengandung `text`), abaikan yang `font.manual === true`.
- Peran ditentukan **berdasarkan peringkat ukuran font** di dalam slide:
  - `title` = `font.size` terbesar,
  - `subtitle` = ukuran berbeda berikutnya dengan `0.6 × title ≤ size < title`,
  - `body` = sisanya.
- Elemen dengan nama/id mengandung `footer`, `page_number`, `badge`, `caption`, `label`, `kicker` dikecualikan dari kandidat `title`/`subtitle` dan selalu dianggap `body`.
- Terapkan `font.family` dan `font.size`; untuk `runs` yang punya `font.size` eksplisit, skalakan dengan rasio `size_baru / size_lama` agar hierarki run tetap.
- Dipakai pada jalur render slide: `TemplateV2KonvaSlide` (lewat data slide yang dioper) dan `StaticHtmlTextLayer`, serta thumbnail.

### 8.4 Presedensi

```
edit manual elemen (font.manual === true)
  > slides.typography
    > presentations.typography
      > Auto (nilai template/LLM)
```

`TextToolbar.updateFont` menandai `manual: true` pada font elemen saat pengguna mengubah family/size/weight/style/color. Tipe `Font` di `servers/nextjs/components/slide-editor/types.ts` mendapat field opsional `manual?: boolean` (backward compatible: `undefined` = belum pernah diedit manual).

## 9. Paritas preview dan export

- Export memakai `ExportTaskService.export_from_url()`: Chromium headless membuka URL presentasi yang sama lalu menyimpan PDF/PPTX. Tidak ada renderer kedua.
- Karena tipografi diterapkan pada komponen render yang sama dengan input yang sama (`presentation.typography` + `slides.typography` + `presentation.fonts`), hasil export mengikuti preview tanpa penanganan khusus.
- Syarat yang harus dipenuhi: (a) semua family ada di `presentation.fonts`, (b) font selesai dimuat sebelum pengukuran Konva, (c) CSS tipografi disuntik pada kedua jalur render smart.
- Verifikasi: buka halaman presentasi dengan tipografi terisi, catat `getComputedStyle` elemen title/subtitle/body, lalu export PDF dan bandingkan ukuran visual pada slide yang sama.

## 10. API

| Endpoint | Perubahan |
|---|---|
| `POST /presentation/create` | parameter `Body` opsional `typography`, `fonts` (dipakai Standard dan Smart) |
| `POST /presentation/generate` | field opsional `typography`, `fonts` |
| `POST /presentation/generate/async` | idem |
| `PATCH /presentation/{id}/typography` (baru) | body `{ typography?, fonts? }`; `typography` hanya diubah bila field itu dikirim, `fonts` selalu di-merge, backfill penanda dijalankan untuk presentasi smart |
| `PATCH /presentation/slide_update` (sudah ada) | otomatis menerima `typography` karena `SlideModel` diperluas, dan menjalankan backfill penanda untuk slide smart yang tipografinya tidak Auto |
| `POST /ppt/fonts/google` (baru) | resolve + cache Google Fonts (berkas disajikan lewat mount `/app_data`) |
| `GET /presentation/{id}` | `typography` ikut pada respons presentasi dan slide |

Otorisasi mengikuti pola endpoint presentasi yang ada (owner check).

## 11. UI

### 11.1 Komponen bersama

`servers/nextjs/app/(presentation-generator)/typography/components/TypographyEditor.tsx` (baru):

- Props: `value`, `onChange`, `scope: "presentation" | "slide"`, `templateFonts`, `onFontResolved(family, url)`, `resolveGoogleFont(family)`.
- Tiga baris peran: label, pemilih family, input ukuran; kosong berarti Auto.
- Pemilih family berupa `<select>` berisi `Auto` + family template (`templateFonts`) + family lokal (`LOCAL_FONT_OPTIONS`). Memilih family lokal langsung memanggil `onFontResolved` dengan `sourceUrl` dari `localFontOptionForFamily` agar family tercatat di `presentation.fonts`.
- Input teks Google Fonts terpisah: unduhan baru terjadi saat pengguna menekan "Gunakan" → `POST /ppt/fonts/google`, lalu family dipasang ke peran Judul dan URL-nya diteruskan lewat `onFontResolved`.
- Input ukuran: mode Auto (default) atau angka bulat 8–200; peringatan inline bila `title > 96`, `subtitle > 60`, atau `body > 32`.
- Menampilkan status kesalahan resolve font secara inline; nilai tidak tersimpan bila resolve gagal.

### 11.2 Halaman upload

- `servers/nextjs/app/(presentation-generator)/upload/components/ConfigurationSelects.tsx`: blok "Typography" yang dapat dilipat, isinya `TypographyEditor` dengan `scope="presentation"`.
- State disimpan pada konfigurasi di `upload/type.ts` dan dikirim bersama request generate (`typography`, `fonts`).

### 11.3 Editor presentasi

- Tombol "Tipografi" di header halaman presentasi membuka dialog `TypographyEditor`.
- Switch cakupan di dalam dialog: **Seluruh presentasi** (`PATCH /presentation/{id}/typography`) atau **Slide ini** (`slides.typography` lewat `slide_update`).
- Memilih family baru di cakupan slide mengirim `fonts` lebih dulu lewat `PATCH /presentation/{id}/typography` (tanpa field `typography`) agar berkas font tetap terdaftar di presentasi.

### 11.4 Editor Smart

- Dialog tipografi yang sama dipakai untuk slide Smart (tidak ada toolbar terpisah di `SmartHtmlEditor`).
- Pratinjau perubahan langsung terlihat setelah disimpan karena `SmartHtmlSlide` menerima nilai efektif dari state presentasi yang di-refresh, dan backfill penanda peran berjalan otomatis saat penyimpanan per slide.

## 12. Pengujian

Backend (pytest):

- `tests/unit/test_typography_config.py`: validasi skema (rentang ukuran, string kosong → null, field asing ditolak), merge per field, `is_auto`.
- `tests/unit/test_smart_typography_roles.py`: fixture HTML smart untuk kelas Tailwind, `text-[NNpx]`, inline font-size, heading tag, HTML tanpa teks, HTML yang sudah bertanda, elemen dekoratif, dan idempotensi.
- `tests/unit/test_presentation_typography_api.py`: `PATCH /typography` menyimpan dan menggabungkan `fonts`, `422` untuk family tak dikenal, `422` untuk URL font di luar prefix yang diizinkan, `404` untuk presentasi yang tidak ada, dan request `{fonts}` saja tidak mengubah `typography`.
- `tests/unit/test_presentation_slide_update_api.py`: slide yang diberi `typography` mendapat penanda peran, dan slide dengan typography Auto tidak diubah.
- `tests/unit/test_google_fonts_endpoint.py`: cache hit tanpa jaringan, kegagalan unduh → `502`, nama tak dikenal → `404` (gunakan mock HTTP).

Frontend (node --test, mengikuti pola `tests/*.test.mjs` dengan `esbuild`):

- `tests/typography-effective.test.mjs`: `resolveTypography` (presedensi global vs slide vs Auto), `isAutoTypography`, dan `typographyStyleCss` (hanya field non-Auto).
- `tests/typography-apply-to-slide.test.mjs`: `applyTypographyToSlide` (peringkat ukuran, pengecualian label/footer, pelewatan `font.manual`, penskalaan run).
- Komponen `TypographyEditor` dan tombol header diverifikasi lewat `npm run lint` dan `npm run build`, bukan tes komponen otomatis.

Paritas:

- Verifikasi manual: buat presentasi dengan Judul 52 px / Inter, catat `getComputedStyle` elemen `[data-text-role="title"]` pada preview, lalu export PDF dan bandingkan ukuran visual slide yang sama.
- Verifikasi manual: pastikan presentasi tanpa tipografi (Auto) tampil identik dengan sebelum perubahan.

## 13. Risiko dan mitigasi

| Risiko | Mitigasi |
|---|---|
| Model tidak menaati permintaan penanda | Backfill heuristik otomatis saat tipografi diterapkan |
| Google Fonts gagal diunduh / offline | Resolve eksplisit, error `502`, nilai tidak tersimpan, UI tetap Auto; berkas di-cache lokal |
| Font berubah tidak memicu render ulang Konva | Sertakan versi tipografi pada key/prop komponen slide |
| Ukuran ekstrem membuat teks meluber | Validasi 8–200 + peringatan UI; tidak mengubah aturan `overflow` template |
| Nama elemen kartu mengandung "heading" | Peran ditentukan peringkat ukuran, bukan nama, kecuali pengecualian label/footer |
| Presentasi lama berubah tampilan | Kolom `NULL` = perilaku lama; backfill hanya menambah atribut, bukan gaya |

## 14. Kompatibilitas

- Request tanpa `typography` tetap valid → perilaku saat ini.
- Presentasi tanpa `typography` dirender seperti sebelumnya.
- Skema JSON diberi `version: 1` agar perubahan bentuk di masa depan bisa dimigrasikan.
- `font.manual` opsional sehingga data slide lama tidak perlu dimigrasi.
