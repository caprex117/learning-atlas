import pytest

from atlas.repository import MemoryRepository
from atlas.service import LearningService
from .sql_backend import SQLHarness, SQLRepository


@pytest.fixture(scope="session")
def sql_engine():
    try:
        engine=SQLHarness()
    except FileNotFoundError as exc:
        pytest.skip(str(exc))
    yield engine
    engine.close()


@pytest.fixture(params=["memory","sql"])
def repository(request):
    if request.param=="memory":
        return MemoryRepository()
    return SQLRepository(request.getfixturevalue("sql_engine"))


@pytest.fixture
def service(repository):
    return LearningService(repository)
