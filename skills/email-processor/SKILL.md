# SKILL: Email Processor

## Overview
> Memproses email notes di `00 - Inbox/Emails/` yang sudah di-review oleh Pak Bos. Membaca action checklist di setiap note, mengeksekusi aksi yang dicentang (Archive, Reply, Forward), lalu memindahkan note ke `05 - Archive/Emails/`. Jika hanya `[x] Read` yang dicentang dan aksi lainnya kosong, file di-delete permanently. Jika tidak ada yang dicentang sama sekali, file dilewati.

## Prerequisites

- `gog` — Google OAuth CLI tool (untuk reply/forward via Gmail)
- `OV_INBOX_PATH` — path ke Obsidian Inbox folder

## Usage

### How to invoke this skill
Jalankan setelah Pak Bos selesai review email di `00 - Inbox/Emails/` dan sudah mencentang action yang diinginkan.

```bash
cd skills/email-processor
export OV_INBOX_PATH="/path/to/obsidian/inbox"
uv run email_processor.py
```

### Input
- `.md` files di `{OV_INBOX_PATH}/Emails/`
- File harus mengikuti format template `email-reader/template/Email.md`
- File dengan frontmatter `status: Processed` akan dilewati (idempotent)

### Output
- File dengan `[x] Archive` → dieksekusi → dipindah ke `{OV_INBOX_PATH}/../05 - Archive/Emails/`
- File dengan `[x] Reply` atau `[x] Forward` → dieksekusi → **tidak** otomatis dipindah kecuali `[x] Archive` juga dicentang
- File dengan hanya `[x] Read` yang dicentang → di-delete permanently
- File tanpa aksi apa pun → dilewati
- Frontmatter `status` di-update ke `Processed` sebelum dipindah

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `OV_INBOX_PATH` | ✅ | — | Absolute path to the Obsidian Inbox folder |
| `GOG_BIN` | ❌ | `gog` | Path ke `gog` binary |
| `GEMINI_MODEL` | ❌ | `gemini-2.5-flash-lite` | Gemini model (untuk assist reply) |

## Script Logic: `email_processor.py`

### 1. Entrypoint & Validation
```
main()
  └── validate_env()         # cek OV_INBOX_PATH exists, gog binary ada
  └── get_inbox_files()      # glob semua *.md di {OV_INBOX_PATH}/Emails/
  └── for each file → process_email(file)
```

### 2. `process_email(filepath)`
```
1. parse_frontmatter(filepath)
   - Jika status == "Processed" → skip (log: already processed)

2. parse_actions(filepath)
   - Baca section "## # Action"
   - Deteksi checkbox yang checked [x]:
     * read      → bool
     * reply     → bool
     * archive   → bool
     * forward   → str (ambil teks setelah "→")

3. Jika TIDAK ADA aksi yang checked (semua false/None):
   - skip file (belum di-review)
   - return

4. Jika HANYA `read` yang checked (dan lainnya false/None):
   - os.remove(filepath)
   - log: "Deleted {filename} (read only, no action)"
   - return

5. Eksekusi aksi (urutan: reply → forward):
   - execute_reply(filepath)   # hanya jika reply == True
   - execute_forward(filepath, forward_target)  # hanya jika forward != None

6. Jika `archive` == True:
   - Update frontmatter status → "Processed"
   - move_to_archive(filepath)
     - Pindah ke {OV_INBOX_PATH}/../05 - Archive/Emails/{filename}
     - Jika file sudah ada di archive → tambah suffix timestamp
```

### 3. `parse_actions(filepath) → dict`
```
Baca file line by line, cari section "## # Action"
Parse baris dengan pattern (case-insensitive): "- [x] <action>"

Nama action yang valid (sesuai template Email.md):
  - "Read"    → read: True/False
  - "Reply"   → reply: True/False
  - "Archive" → archive: True/False
  - "Forward" → forward: str (teks setelah "→") atau None
                  - Jika baris: "- [x] Forward → email@example.com" → forward = "email@example.com"
                  - Jika baris: "- [x] Forward → " (kosong) → forward = None (skip, jangan execute)

Return:
{
  "read": True/False,
  "reply": True/False,
  "archive": True/False,
  "forward": "email@example.com" atau None
}
```

### 4. `execute_reply(filepath)`
```
1. Ambil Gmail ID dari filename: YYYY-MM-DD-{gmail_id}.md
2. Ambil `account` dari frontmatter field `to` (email address penerima asli = akun Gmail kita)
3. Baca konten section "## Reply" dari file
4. Jika section Reply kosong atau hanya mengandung placeholder
   "*(isi di sini → AI agent akan otomatis kirim)*":
   - log warning: "Reply section empty, skipping send"
   - return (jangan gagalkan seluruh proses)
5. Jalankan (sync, wait): gog gmail reply {gmail_id} -a {account} --body "{reply_content}"
6. Jika gagal → raise Exception (STOP-ON-FAIL, file tidak dipindah, archive dibatalkan)
```

### 5. `execute_forward(filepath, target)`
```
1. Ambil Gmail ID dari filename: YYYY-MM-DD-{gmail_id}.md
2. Ambil `account` dari frontmatter field `to`
3. Jalankan (sync, wait): gog gmail forward {gmail_id} -a {account} --to "{target}"
4. Jika gagal → raise Exception (STOP-ON-FAIL, file tidak dipindah, archive dibatalkan)
```

### 6. `move_to_archive(filepath)`
```
1. Pastikan dir {OV_INBOX_PATH}/../05 - Archive/Emails/ exists (mkdir jika perlu)
2. shutil.move(filepath, archive_dir / filepath.name)
```

## Behavior Rules
- **STOP-ON-FAIL:** Jika reply atau forward gagal (raise Exception), **batalkan seluruh sisa aksi** termasuk archive — file tetap di inbox, lanjut ke file berikutnya.
- **Idempotent:** File dengan `status: Processed` di frontmatter → skip
- **Sequential:** Proses satu file per satu, tidak paralel
- **Sync execution:** Eksekusi command `gog` selalu ditunggu (sync), no timeout.
- **Only Read = Delete:** Jika hanya `[x] Read` yang dicentang, lakukan `os.remove()`
- **No action = Skip:** Jika belum dicentang apa pun, lewati file.
- **Empty reply section:** Log warning tapi lanjut proses (jangan stop), archive tetap bisa jalan.
- **Forward empty target:** Jika teks setelah `→` kosong, skip execute_forward (log warning), lanjut.

## Error Handling
- `gog` binary tidak ditemukan → `exit(1)` dengan pesan jelas
- `OV_INBOX_PATH` tidak ada → `exit(1)`
- Reply/Forward gagal → log error, **JANGAN** pindah file, lanjut ke file berikutnya
- File permission error → log error, skip file tersebut

## Example
```bash
export OV_INBOX_PATH="/home/toni/obsidian/second-brain/00 - Inbox"
uv run email_processor.py
# Processing: 2026-04-27-19dce188c43be970.md
#   [REPLY] Sending reply to info@futureskills.id...
#   [ARCHIVE] Moved to 05 - Archive/Emails/
# Processing: 2026-04-27-19dce1aabb3f1234.md
#   [REPLY] Sending reply to boss@company.com...
#   (no [x] Archive → file stays in inbox)
# Processing: 2026-04-26-19dc97c483b45cd7.md
#   [DELETE] Only Read checked. Deleting...
# Done. 2 processed, 1 deleted.
```

## Changelog
| Version | Date | Notes |
|---|---|---|
| 0.3.0 | 2026-04-27 | Patch: clarify action names, account source, forward empty, STOP-ON-FAIL scope |
| 0.2.0 | 2026-04-27 | Sync env to OV_INBOX_PATH; archive only when [x] Archive is checked |
| 0.1.0 | 2026-04-27 | Initial spec |
