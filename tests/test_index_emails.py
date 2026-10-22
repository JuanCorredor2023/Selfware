import json

from scripts import index_emails
from scripts.index_emails import DEMO_EMAILS, demo_documents, plan, to_documents


def test_gmail_entries_become_uncategorised_documents():
    raw = [
        {
            "id": "m1",
            "ts": "2026-09-01T10:00:00+00:00",
            "subject": "Hi",
            "body": "Body text",
        }
    ]

    (doc,) = to_documents(raw, source="gmail")

    assert doc.source_id == "m1"
    assert doc.source == "gmail"
    assert doc.category is None  # the classifier fills it, not this script
    assert doc.date == "2026-09-01T10:00:00+00:00"
    assert doc.content == "Subject: Hi\n\nBody text"


def test_empty_emails_are_dropped():
    raw = [
        {"id": "a", "ts": "2026-09-01T10:00:00+00:00", "subject": "", "body": "  "},
        {"id": "b", "ts": "2026-09-01T10:00:00+00:00", "subject": "Real", "body": ""},
    ]

    assert [d.source_id for d in to_documents(raw, "gmail")] == ["b"]


def test_demo_emails_are_invented_unique_and_dated():
    docs = demo_documents()

    assert len(docs) == len(DEMO_EMAILS) == 12
    assert len({d.source_id for d in docs}) == 12
    assert all(d.source == "demo" and d.date for d in docs)


def test_estimate_is_small_and_positive_for_the_demo():
    estimate = plan(demo_documents())

    assert estimate.emails == 12
    assert 0 < estimate.total_usd < 0.01  # fractions of a cent


def test_without_yes_nothing_is_sent(capsys):
    assert index_emails.main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Dry run: nothing was sent" in out
    assert "12 emails" in out


def test_input_file_is_read(tmp_path, capsys):
    path = tmp_path / "emails.json"
    path.write_text(
        json.dumps(
            [
                {
                    "id": "m1",
                    "ts": "2026-09-01T10:00:00+00:00",
                    "subject": "S",
                    "body": "B",
                }
            ]
        )
    )

    assert index_emails.main(["--input", str(path)]) == 0
    assert "1 emails" in capsys.readouterr().out
