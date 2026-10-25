"""Classifier against a faked core.llm.call: no network, no credits."""

import pytest

from selfware.context import classifier as classifier_module
from selfware.context.classifier import Classifier
from selfware.context.domain import ParaFolder


@pytest.fixture
def fake_call(monkeypatch):
    seen = {}

    def install(content):
        def call(tier, messages, **kwargs):
            seen.update(tier=tier, **kwargs)
            return content, None

        monkeypatch.setattr(classifier_module, "call", call)
        return seen

    return install


def test_room_for_reasoning(fake_call):
    seen = fake_call("\n\nprojects")
    assert Classifier().classify_query("q") == ParaFolder.PROJECTS
    assert seen["tier"] == "super"
    assert seen["max_tokens"] >= 512


def test_none_content_falls_back_to_default(fake_call):
    # What Token Factory returns when the reasoning eats the whole budget.
    fake_call(None)
    assert Classifier().classify_document("an email") == ParaFolder.RESOURCES
