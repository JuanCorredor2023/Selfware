from selfware.context.domain import ParaFolder
from selfware.core.llm import call

_DEFAULT_CATEGORY = ParaFolder.RESOURCES

_SYSTEM_PROMPT = (
    "You are a PARA classifier. Classify the user's query into exactly one "
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


class Classifier:

    def __init__(self, tier: str = "super"):
        self.tier = tier

    def classify_query(self, query: str) -> ParaFolder:
        messages = self._build_messages(query)
        text, _ = call(self.tier, messages, temperature=0, max_tokens=4)
        return self._parse_to_para_folder(text)

    def _build_messages(self, query: str) -> list[dict]:
        return [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ]

    def _parse_to_para_folder(self, text: str) -> ParaFolder:
        cleaned = text.strip().lower()
        for category in ParaFolder:
            if category.value in cleaned:
                return category
        return _DEFAULT_CATEGORY


class FakeClassifier:
    """Configurable fake for tests: returns the category you give it.
    Same shape as Classifier (classify_query -> ParaFolder)."""

    def __init__(self, category_to_return: ParaFolder):
        self.category_to_return = category_to_return

    def classify_query(self, query: str) -> ParaFolder:
        return self.category_to_return