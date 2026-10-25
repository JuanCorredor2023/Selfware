from collections.abc import Callable

from selfware.context.domain import ParaFolder
from selfware.core.llm import call
from selfware.core.schemas import TierCall

# Categoría por defecto cuando la respuesta del LLM no mapea a ninguna.
_DEFAULT_CATEGORY = ParaFolder.RESOURCES

_QUERY_PROMPT = (
    "You are a PARA classifier. Classify the user's QUERY into exactly one "
    "PARA category, based on what the query is about:\n"
    "- projects: a specific effort with a concrete goal and an end "
    "(a deliverable, a trip being planned, a task with a deadline).\n"
    "- areas: an ongoing responsibility with no end date "
    "(health, finances, a role, a recurring relationship).\n"
    "- resources: a topic or reference material of ongoing interest "
    "(notes, documentation, things to look up).\n"
    "- archive: something inactive, completed, or no longer in use.\n"
    "Respond with ONLY one word: projects, areas, resources, or archive. "
    "No punctuation, no explanation."
)

_DOCUMENT_PROMPT = (
    "You are a PARA classifier. Classify this EMAIL into exactly one PARA "
    "category, based on what the email is about:\n"
    "- projects: tied to a specific effort with a concrete goal and an end "
    "(a deliverable, an event being organized, a task with a deadline).\n"
    "- areas: about an ongoing responsibility with no end date "
    "(health, finances, a role, a recurring relationship).\n"
    "- resources: reference material or a topic of ongoing interest "
    "(a newsletter, documentation, something to keep for later).\n"
    "- archive: about something inactive, completed, or no longer in use.\n"
    "Respond with ONLY one word: projects, areas, resources, or archive. "
    "No punctuation, no explanation."
)

# Query classification runs in runtime, few calls, needs reasoning -> Super.
# Document classification runs in batch over the whole corpus, cheap+massive
# -> Nano.
_QUERY_TIER = "super"
_DOCUMENT_TIER = "nano"

# Nemotron reasons before it answers, and the reasoning counts against
# max_tokens. With 4 tokens it is cut mid-thought and `content` comes back
# None (measured 2026-10-25: 3 of 3 queries). Super used 99-286 output tokens
# to emit the one word; 1024 leaves room for longer emails.
_MAX_TOKENS = 1024


class Classifier:
    def __init__(self, on_tier_call: Callable[[TierCall], None] | None = None):
        # Called with the TierCall of every LLM call, so the caller (api/) can
        # price it and show it in /cost. None keeps the old behaviour.
        self._on_tier_call = on_tier_call

    def classify_query(self, query: str) -> ParaFolder:
        return self._classify(query, _QUERY_PROMPT, _QUERY_TIER)

    def classify_document(self, content: str) -> ParaFolder:
        return self._classify(content, _DOCUMENT_PROMPT, _DOCUMENT_TIER)

    def _classify(self, text: str, system_prompt: str, tier: str) -> ParaFolder:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ]
        response, tier_call = call(
            tier, messages, temperature=0, max_tokens=_MAX_TOKENS
        )
        if self._on_tier_call is not None:
            self._on_tier_call(tier_call)
        return self._parse_to_para_folder(response)

    def _parse_to_para_folder(self, text: str | None) -> ParaFolder:
        # None = the model was cut off before answering: same as no match.
        cleaned = (text or "").strip().lower()
        for category in ParaFolder:
            if category.value in cleaned:
                return category
        return _DEFAULT_CATEGORY


class FakeClassifier:
    """Configurable fake for tests: returns the category you give it, for both
    entry points. Same shape as Classifier."""

    def __init__(self, category_to_return: ParaFolder):
        self.category_to_return = category_to_return

    def classify_query(self, query: str) -> ParaFolder:
        return self.category_to_return

    def classify_document(self, content: str) -> ParaFolder:
        return self.category_to_return
