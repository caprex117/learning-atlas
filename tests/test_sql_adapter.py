"""Driver contract regressions runnable even when PostgreSQL is unavailable."""
from unittest.mock import MagicMock

import psycopg
import pytest

from atlas.repository import RepositoryError
from .sql_backend import SQLHarness


@pytest.fixture
def postgres_adapter():
    harness = SQLHarness.__new__(SQLHarness)
    harness.process = None
    harness.connection = MagicMock()
    cursor = harness.connection.cursor.return_value.__enter__.return_value
    return harness, cursor


def test_query_without_returning_returns_empty_rows(postgres_adapter):
    harness, cursor = postgres_adapter
    cursor.description = None

    assert harness.query("insert into example(name) values($1)", ["Example"]) == []
    cursor.execute.assert_called_once_with(
        "insert into example(name) values(%s)", ["Example"]
    )
    cursor.fetchall.assert_not_called()


@pytest.mark.parametrize("error", [
    psycopg.errors.InsufficientPrivilege("permission denied for table example"),
    psycopg.errors.CheckViolation("check constraint rejected the row"),
])
def test_postgres_errors_keep_the_shared_repository_contract(postgres_adapter, error):
    harness, cursor = postgres_adapter
    cursor.execute.side_effect = error

    with pytest.raises(RepositoryError) as caught:
        harness.query("select * from example")

    assert str(caught.value) == str(error)
    assert caught.value.__cause__ is error


def test_adapter_does_not_hide_python_programming_errors(postgres_adapter):
    harness, cursor = postgres_adapter
    cursor.execute.side_effect = TypeError("invalid driver argument")

    with pytest.raises(TypeError, match="invalid driver argument"):
        harness.query("select 1")
