# SKILL: Email Processor

## Overview
> Memproses email notes di `00 - Inbox/Emails/` yang sudah di-review oleh Pak Bos. Membaca action checklist di setiap note, mengeksekusi aksi yang dicentang (Archive, Reply, Forward, Create Task), lalu memindahkan note ke `05 - Archive/Emails/`. Jika hanya `[x] Read` yang dicentang dan aksi lainnya kosong, file di-delete permanently. Jika tidak ada yang dicentang sama sekali, file dilewati.

## Prerequisites

- `gog` — Google OAuth CLI tool (untuk reply/forward via Gmail)
- `VAULT_PATH` — path ke Obsidian vault

## Usage

### How to invoke this skill
Jalankan setelah Pak Bos selesai review email di `00 - Inbox/Emails/` dan sudah mencentang action yang diinginkan.

```bash
cd skills/email-processor
export VAULT_PATH="/path/to/obsidian/vault"
uv run email_processor.py
```

### Input
- `.md` files di `{VAULT_PATH}/00 - Inbox/Emails/`
- File harus mengikuti format template `email-reader/template/Email.md`
- File dengan frontmatter `status: Processed` akan dilewati (idempotent)

### Output
- File dengan aksi → dieksekusi → dipindah ke `{VAULT_PATH}/05 - Archive/Emails/`
- File dengan hanya `[x] Read` yang dicentang → di-delete permanently
- File tanpa aksi apa pun → dilewati
- Frontmatter `status` di-update ke `Processed` sebelum dipindah

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `VAULT_PATH` | ✅ | — | Absolute path ke Obsidian vault |
| `GOG_BIN` | ❌ | `gog` | Path ke `gog` binary |
| `GEMINI_MODEL` | ❌ | `gemini-2.5-flash-lite` | Gemini model (untuk assist reply) |

## Script Logic: `email_processor.py`

### 1. Entrypoint & Validation
```
main()
  └── validate_env()         # cek VAULT_PATH exists, gog binary ada
  └── get_inbox_files()      # glob semua *.md di {VAULT_PATH}/00 - Inbox/Emails/
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
     * task      → str (ambil teks setelah "→")

3. Jika TIDAK ADA aksi yang checked (semua false/None):
   - skip file (belum di-review)
   - return

4. Jika HANYA `read` yang checked (dan lainnya false/None):
   - os.remove(filepath)
   - log: "Deleted {filename} (read only, no action)"
   - return

5. Eksekusi aksi (urutan: task → reply → forward → archive):
   - execute_create_task(filepath, task_detail)
   - execute_reply(filepath)
   - execute_forward(filepath, forward_target)

6. Update frontmatter status → "Processed"

7. move_to_archive(filepath)
   - Pindah ke {VAULT_PATH}/05 - Archive/Emails/{filename}
   - Jika file sudah ada di archive → tambah suffix timestamp
```

### 3. `parse_actions(filepath) → dict`
```
Baca file line by line, cari section "## # Action"
Parse baris dengan pattern: "- [x] <action>"

Return:
{
  "read": True/False,
  "reply": True/False,
  "archive": True/False,
  "forward": "email@example.com" atau None,
  "task": "nama task → [[Project]]" atau None
}
```

### 4. `execute_reply(filepath)`
```
1. Ambil Gmail ID dari filename: YYYY-MM-DD-{gmail_id}.md
2. Ambil sender dari frontmatter
3. Baca konten section "## Reply" dari file
4. Jika section Reply kosong atau hanya placeholder:
   - log warning: "Reply section empty, skipping send"
   - return (jangan gagalkan seluruh proses)
5. Jalankan: gog gmail reply {gmail_id} -a {account} --body "{reply_content}"
6. Jika gagal → raise Exception (STOP-ON-FAIL, file tidak dipindah)
```

### 5. `execute_forward(filepath, target)`
```
1. Ambil Gmail ID dari filename
2. Jalankan: gog gmail forward {gmail_id} -a {account} --to "{target}"
3. Jika gagal → raise Exception (STOP-ON-FAIL)
```

### 6. `execute_create_task(filepath, task_detail)`
```
1. Parse task_detail:
   - Format: "nama task → [[Project Name]]"
   - Ekstrak: task_name, project_link
2. Cari file project di {VAULT_PATH}/02 - Projects/Active/{project_name}/
3. Append ke section "### Backlog" di project file:
   "- [ ] {task_name} (from email: [[{email_filename}]])"
4. Jika project tidak ditemukan → log warning, lanjut (jangan stop)
```

### 7. `move_to_archive(filepath)`
```
1. Pastikan dir {VAULT_PATH}/05 - Archive/Emails/ exists (mkdir jika perlu)
2. shutil.move(filepath, archive_dir / filepath.name)
```

## Behavior Rules
- **STOP-ON-FAIL:** Jika reply/forward gagal, jangan pindahkan file ke archive
- **Idempotent:** File dengan `status: Processed` di frontmatter → skip
- **Sequential:** Proses satu file per satu, tidak paralel
- **Only Read = Delete:** Jika hanya `[x] Read` yang dicentang, lakukan `os.remove()`
- **No action = Skip:** Jika belum dicentang apa pun, lewati file.
- **Empty reply section:** Log warning tapi lanjut proses, jangan stop
- **Missing project:** Log warning tapi lanjut proses, jangan stop

## Error Handling
- `gog` binary tidak ditemukan → `exit(1)` dengan pesan jelas
- `VAULT_PATH` tidak ada → `exit(1)`
- Reply/Forward gagal → log error, **JANGAN** pindah file, lanjut ke file berikutnya
- File permission error → log error, skip file tersebut

## Example
```bash
export VAULT_PATH="/home/toni/obsidian/second-brain"
uv run email_processor.py
# Processing: 2026-04-27-19dce188c43be970.md
#   [REPLY] Sending reply to info@futureskills.id...
#   [ARCHIVE] Moved to 05 - Archive/Emails/
# Processing: 2026-04-26-19dc97c483b45cd7.md
#   [DELETE] Only Read checked. Deleting...
# Done. 1 processed, 1 deleted.
```

## Changelog
| Version | Date | Notes |
|---|---|---|
| 0.1.0 | 2026-04-27 | Initial spec |
