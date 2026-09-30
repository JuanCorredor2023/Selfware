import pytest

from selfware.observability.ledger import ledger


@pytest.fixture(autouse=True)
def empty_ledger():
    """Every test starts (and ends) with an empty cost ledger, so /cost
    numbers don't leak between tests."""
    ledger.reset()
    yield
    ledger.reset()
