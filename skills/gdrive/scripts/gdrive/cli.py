"""gdrive CLI entry point."""

import argparse
import json
import logging
import sys
from typing import List

from gdrive import brief, config, db, reindex, search, upload


def _setup_logging() -> None:
    log_path = config.get_log_path()
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handlers: List[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    try:
        handlers.append(logging.FileHandler(log_path))
    except OSError as e:
        print(f"[warn] Could not open log file {log_path}: {e}", file=sys.stderr)
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=handlers)


def _print_files_table(rows) -> None:
    try:
        from tabulate import tabulate
        data = [
            [
                row["name"][:60],
                row["mime_type"].split(".")[-1][:20] if row["mime_type"] else "",
                f"{int(row['size_bytes']) // 1024:,} KB" if row["size_bytes"] else "-",
                row["owner"] or "-",
                (row["modified_at"] or "")[:10],
                row["web_view_link"] or "",
            ]
            for row in rows
        ]
        headers = ["Name", "Type", "Size", "Owner", "Modified", "Link"]
        print(tabulate(data, headers=headers, tablefmt="simple"))
    except ImportError:
        # Fallback: TSV
        for row in rows:
            print("\t".join([
                row["id"],
                row["name"],
                row["mime_type"] or "",
                str(row["size_bytes"] or ""),
                row["owner"] or "",
                row["modified_at"] or "",
                row["web_view_link"] or "",
            ]))


# ── Subcommand handlers ────────────────────────────────────────────────────────

def cmd_reindex(args) -> int:
    dry_run = args.dry_run or config.is_dry_run()
    conn = db.connect(config.get_db_path())
    reindex.run(conn, dry_run=dry_run, limit=args.limit, incremental=not args.full)
    return 0


def cmd_search(args) -> int:
    conn = db.connect(config.get_db_path())
    rows = search.run(
        conn,
        name=args.name,
        mime=args.mime,
        owner=args.owner,
        parent_id=args.parent,
        limit=args.limit,
    )
    if not rows:
        print("No results found.")
        return 0
    if args.json:
        print(json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=2))
    else:
        _print_files_table(rows)
    print(f"\n{len(rows)} result(s).")
    return 0


def cmd_upload(args) -> int:
    dry_run = args.dry_run or config.is_dry_run()
    conn = db.connect(config.get_db_path())
    result = upload.run(
        conn,
        local_path=args.file,
        parent=args.parent,
        name=args.name,
        replace=args.replace,
        dry_run=dry_run,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if dry_run:
            print(f"[dry-run] Would upload: {args.file}")
        else:
            f = result.get("file") or result
            print(f"Uploaded: {f.get('name')} ({f.get('id')})")
            if f.get("webViewLink"):
                print(f"Link: {f['webViewLink']}")
    return 0


def cmd_brief(args) -> int:
    dry_run = args.dry_run or config.is_dry_run()
    conn = db.connect(config.get_db_path())
    brief.run(conn, dry_run=dry_run, limit=args.limit)
    return 0


# ── Argument parser ────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gdrive",
        description="Google Drive CLI backed by gog",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # reindex
    p_reindex = sub.add_parser("reindex", help="Index all My Drive files into SQLite")
    p_reindex.add_argument(
        "--dry-run", action="store_true",
        help="Simulate without writing to DB"
    )
    p_reindex.add_argument(
        "--limit", "-l", type=int,
        help="[Testing only] Cap number of files indexed. Do not use in production."
    )
    p_reindex.add_argument(
        "--full", action="store_true",
        help="Force full reindex, ignore last run timestamp."
    )
    p_reindex.set_defaults(func=cmd_reindex)

    # search
    p_search = sub.add_parser("search", help="Query local SQLite index")
    p_search.add_argument("--name", "-n", help="Filter by filename (substring)")
    p_search.add_argument(
        "--mime", "-m",
        help="Filter by MIME type or shortcut (doc, pdf, sheet, slide, image, folder, gdoc, gsheet, gslide)"
    )
    p_search.add_argument("--owner", "-o", help="Filter by owner email (substring)")
    p_search.add_argument("--parent", "-p", help="Filter by parent folder ID")
    p_search.add_argument("--limit", "-l", type=int, default=50, help="Max results (default: 50)")
    p_search.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    p_search.set_defaults(func=cmd_search)

    # upload
    p_upload = sub.add_parser("upload", help="Upload a file to Google Drive")
    p_upload.add_argument("file", help="Path to local file")
    p_upload.add_argument("--parent", "-p", help="Destination folder ID")
    p_upload.add_argument("--name", "-n", help="Override filename")
    p_upload.add_argument("--replace", "-r", help="Replace existing file ID (preserves link)")
    p_upload.add_argument("--dry-run", action="store_true", help="Simulate without uploading")
    p_upload.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    p_upload.set_defaults(func=cmd_upload)

    # brief
    p_brief = sub.add_parser("brief", help="Generate AI briefs for Drive documents (docx/pdf/xlsx/pptx)")
    p_brief.add_argument(
        "--limit", "-l", type=int, default=50,
        help="Max number of files to brief per run (default: 50)"
    )
    p_brief.add_argument(
        "--dry-run", action="store_true",
        help="Simulate without downloading or calling Gemini"
    )
    p_brief.set_defaults(func=cmd_brief)

    return parser


def main() -> None:
    _setup_logging()
    parser = build_parser()
    args = parser.parse_args()

    try:
        code = args.func(args)
        sys.exit(code)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
