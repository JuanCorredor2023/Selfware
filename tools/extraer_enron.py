"""
tools/extraer_enron.py -- Person 3.

Turns one Enron custodian's maildir into `enron_sample.jsonl`: one JSON object
per message, only the text its sender wrote, ready to be indexed and to write
evaluation questions against (D26).

    uv run python -m tools.extraer_enron \\
        --maildir ~/dev/atlas-lab/enron/maildir --custodian kaminski-v \\
        --out ~/dev/atlas-lab/enron/enron_sample.jsonl

Rules, in the order they are applied:

1. Only the folders the owner created. `inbox`, `sent`, `all_documents`,
   `discussion_threads` and friends are mail-client folders: they say nothing
   about how the owner organised their information, and they duplicate it.
2. The quoted thread is cut: what follows `-----Original Message-----`,
   `---- Forwarded by`, a `... wrote:` line, a Lotus Notes reply header (`<name> on <date>` followed
   by `To:`), an Outlook `From:`/`Sent:` block, or a line starting with `>`.
3. 200 to 4,000 characters of own text. Shorter is "FYI" or "thanks"; longer is
   usually a pasted document.
4. Deduplicated by `Message-ID` and then by the own text: the same message
   filed in two folders is one document, kept at the first path in sorted order.
5. With `--mapping`, each message gets the PARA `category` of its folder. The
   mapping is a JSON object from a folder path (`conferences`, or
   `c/technote/mail/projects`) to `projects`, `areas` or `resources`; the
   longest matching prefix wins. A folder the mapping leaves out is dropped.

The corpus never goes into the repo (D4): run this with `--out` outside it.
"""

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from pathlib import Path

#: Folders created by the mail client, not by the owner (rule 1).
SYSTEM_FOLDERS = frozenset(
    {
        "all_documents",
        "calendar",
        "contacts",
        "deleted_items",
        "discussion_threads",
        "drafts",
        "inbox",
        "junk",
        "junk_file",
        "notes_inbox",
        "outbox",
        "sent",
        "sent_items",
        "_sent_mail",
        "straw",
        "tasks",
        "to_do",
    }
)

MIN_CHARS = 200
MAX_CHARS = 4000

#: A line that starts the quoted part of the message (rule 2).
_CUT_LINE = re.compile(
    r"^\s*(-{2,}\s*Original Message\s*-{2,}"
    r"|-{2,}\s*Forwarded by"
    r"|>"
    r"|.*\bwrote:\s*$)",
    re.IGNORECASE,
)
#: Lotus Notes reply header: "Jane Doe@ECT on 01/04/2000 10:13 AM".
_NOTES_HEADER = re.compile(
    r"\bon\s+\d{1,2}/\d{1,2}/\d{2,4}\s+\d{1,2}:\d{2}(:\d{2})?\s*(AM|PM)?\s*$",
    re.IGNORECASE,
)
_HEADER_LINE = re.compile(r"^\s*(To|Sent|cc|Subject):", re.IGNORECASE)


def own_text(body: str) -> str:
    """The part of `body` its sender wrote, before any quoted thread (rule 2)."""
    lines = body.splitlines()
    for i, line in enumerate(lines):
        if _CUT_LINE.match(line):
            return "\n".join(lines[:i]).strip()
        nxt = [x for x in lines[i + 1 : i + 4] if x.strip()]
        if _NOTES_HEADER.search(line) and nxt and _HEADER_LINE.match(nxt[0]):
            return "\n".join(lines[:i]).strip()
        if re.match(r"^\s*From:\s", line) and any(
            re.match(r"^\s*Sent:\s", x) for x in nxt
        ):
            return "\n".join(lines[:i]).strip()
    return body.strip()


def _body(msg: EmailMessage) -> str:
    part = msg.get_body(preferencelist=("plain",)) or msg
    try:
        return part.get_content()
    except LookupError, KeyError, UnicodeError:
        payload = part.get_payload(decode=True) or b""
        return payload.decode("utf-8", errors="replace")


def _header(msg: EmailMessage, name: str) -> str:
    try:
        return str(msg.get(name, "") or "").strip()
    except Exception:  # noqa: BLE001 -- malformed headers raise many types
        return ""


def parse_message(path: Path, maildir: Path) -> dict:
    """One file of the maildir as the dict written to the JSONL."""
    with path.open("rb") as f:
        msg = BytesParser(policy=policy.default).parse(f)
    rel = path.relative_to(maildir)
    date_raw = _header(msg, "Date")
    try:
        date = parsedate_to_datetime(date_raw).isoformat()
    except TypeError, ValueError:
        date = ""
    return {
        "id": f"maildir/{rel.as_posix()}",
        "folder": rel.parts[1],
        "subfolder": "/".join(rel.parts[2:-1]),
        "message_id": _header(msg, "Message-ID"),
        "from": _header(msg, "From"),
        "to": _header(msg, "To"),
        "date": date,
        "subject": _header(msg, "Subject"),
        "text": own_text(_body(msg)),
    }


def category_of(row: dict, mapping: dict[str, str]) -> str | None:
    """PARA folder of a message: the longest mapping key its folder path starts
    with (rule 5). `None` if no key matches."""
    path = "/".join(x for x in (row["folder"], row["subfolder"]) if x)
    keys = [k for k in mapping if path == k or path.startswith(k + "/")]
    return mapping[max(keys, key=len)] if keys else None


def extract(
    maildir: Path, custodian: str, mapping: dict[str, str] | None = None
) -> tuple[list[dict], Counter]:
    """All the kept messages of one custodian, plus why the rest were dropped."""
    base = maildir / custodian
    dropped: Counter = Counter()
    kept: list[dict] = []
    seen_ids: set[str] = set()
    seen_text: set[str] = set()
    folders = sorted(
        p for p in base.iterdir() if p.is_dir() and p.name.lower() not in SYSTEM_FOLDERS
    )
    for folder in folders:
        for path in sorted(p for p in folder.rglob("*") if p.is_file()):
            try:
                row = parse_message(path, maildir)
            except Exception:  # noqa: BLE001 -- one bad file must not stop the run
                dropped["parse_error"] += 1
                continue
            n = len(row["text"])
            if n < MIN_CHARS:
                dropped["too_short"] += 1
                continue
            if n > MAX_CHARS:
                dropped["too_long"] += 1
                continue
            if not row["date"]:
                dropped["no_date"] += 1
                continue
            if mapping is not None:
                row["category"] = category_of(row, mapping)
                if row["category"] is None:
                    dropped["unmapped_folder"] += 1
                    continue
            if row["message_id"] and row["message_id"] in seen_ids:
                dropped["duplicate_message_id"] += 1
                continue
            digest = hashlib.sha256(" ".join(row["text"].split()).encode()).hexdigest()
            if digest in seen_text:
                dropped["duplicate_text"] += 1
                continue
            seen_ids.add(row["message_id"])
            seen_text.add(digest)
            kept.append(row)
    return kept, dropped


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m tools.extraer_enron")
    parser.add_argument("--maildir", type=Path, required=True)
    parser.add_argument("--custodian", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, help="folder -> PARA JSON (rule 5)")
    args = parser.parse_args(argv)

    maildir = args.maildir.expanduser()
    mapping = json.loads(args.mapping.read_text()) if args.mapping else None
    kept, dropped = extract(maildir, args.custodian, mapping)
    out = args.out.expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for row in kept:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"kept {len(kept)} messages -> {out}", file=sys.stderr)
    print(f"dropped: {dict(dropped)}", file=sys.stderr)
    for folder, n in Counter(r["folder"] for r in kept).most_common():
        print(f"  {folder:20} {n}", file=sys.stderr)
    if mapping is not None:
        print(
            f"by category: {dict(Counter(r['category'] for r in kept))}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
