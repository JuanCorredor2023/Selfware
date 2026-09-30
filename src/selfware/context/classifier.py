from .domain import ParaFolder


class Classifier:
    def __init__(self, category_to_return: ParaFolder):
        self.category_to_return = category_to_return

    def classify_query(self, query: str) -> ParaFolder:
        return self.category_to_return
