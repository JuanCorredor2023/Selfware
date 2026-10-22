"""ingest/normalize.py: turning a Gmail payload into clean text. Pure logic, no
network."""

import base64

import pytest

from selfware.ingest.normalize import decode, extract_body, normalize_body
from tests.fakes.gmail_fake import b64, text_part


def test_decode_handles_missing_padding():
    # "ab" encodes to "YWI=", Gmail sends it as "YWI"
    assert decode("YWI") == "ab"


def test_decode_keeps_utf8_accents():
    assert decode(b64("café, niño")) == "café, niño"


def test_decode_replaces_invalid_utf8():
    data = base64.urlsafe_b64encode(b"ok \xff\xfe").decode()
    assert decode(data) == "ok ��"


def test_extract_body_single_part_plain():
    assert extract_body(text_part("Hello there")) == "Hello there"


def test_extract_body_prefers_plain_over_html():
    payload = {
        "mimeType": "multipart/alternative",
        "body": {"size": 0},
        "parts": [
            text_part("<p>Hello html</p>", "text/html"),
            text_part("Hello plain"),
        ],
    }
    assert extract_body(payload) == "Hello plain"


def test_extract_body_finds_nested_parts():
    payload = {
        "mimeType": "multipart/mixed",
        "body": {"size": 0},
        "parts": [
            {
                "mimeType": "multipart/alternative",
                "body": {"size": 0},
                "parts": [text_part("Deep text"), text_part("<p>x</p>", "text/html")],
            }
        ],
    }
    assert extract_body(payload) == "Deep text"


def test_extract_body_skips_attachments():
    payload = {
        "mimeType": "multipart/mixed",
        "body": {"size": 0},
        "parts": [
            {
                "mimeType": "application/pdf",
                "filename": "invoice.pdf",
                "body": {"attachmentId": "att-1", "size": 1234},
            },
            text_part("See attached"),
        ],
    }
    assert extract_body(payload) == "See attached"


def test_extract_body_falls_back_to_html():
    """Pins current behaviour: with no text/plain part the HTML is returned
    with its tags. Change this test if tags start being stripped."""
    payload = {
        "mimeType": "multipart/alternative",
        "body": {"size": 0},
        "parts": [text_part("<p>Only html</p>", "text/html")],
    }
    assert extract_body(payload) == "<p>Only html</p>"


def test_extract_body_returns_empty_when_no_text():
    payload = {
        "mimeType": "multipart/mixed",
        "body": {"size": 0},
        "parts": [{"mimeType": "image/png", "body": {"attachmentId": "a", "size": 9}}],
    }
    assert extract_body(payload) == ""


def test_normalize_body_strips_english_quoted_reply():
    raw = (
        "Thanks, see you Monday.\n\n"
        "On Mon, Oct 5, 2026 at 10:00 AM Ana <ana@example.com> wrote:\n"
        "> Are we meeting?\n"
    )
    assert normalize_body(raw) == "Thanks, see you Monday."


@pytest.mark.xfail(
    strict=True,
    reason="mailparser_reply does not strip Gmail's Spanish reply header yet",
)
def test_normalize_body_strips_spanish_quoted_reply():
    raw = (
        "Gracias, nos vemos el lunes.\n\n"
        "El lun, 5 oct 2026 a las 10:00, Ana (<ana@example.com>) escribió:\n"
        "> ¿Nos reunimos?\n"
    )
    assert normalize_body(raw) == "Gracias, nos vemos el lunes."


def test_normalize_body_without_reply_is_unchanged():
    assert normalize_body("  Just one message.\n") == "Just one message."


def test_normalize_body_whitespace_only():
    assert normalize_body("   \n\t ") == ""
