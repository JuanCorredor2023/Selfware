import base64

from mailparser_reply import EmailReplyParser

REPLY_PARSER = EmailReplyParser(languages=["en", "es"])


def normalize_body(raw_text):
    replies = REPLY_PARSER.read(text=raw_text).replies
    if not replies:
        return raw_text.strip()
    return replies[0].body.strip()


def decode(data):
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode(
        "utf-8", errors="replace"
    )


def find_text(payload, mime_type):
    if payload.get("mimeType") == mime_type and payload.get("body", {}).get("data"):
        decoded_text = decode(payload["body"]["data"])
        return normalize_body(decoded_text)
    for part in payload.get("parts", []):
        text = find_text(part, mime_type)
        if text:
            return text
    return None


def extract_body(payload):
    return find_text(payload, "text/plain") or find_text(payload, "text/html") or ""
