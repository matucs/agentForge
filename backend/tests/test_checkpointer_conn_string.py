"""`_checkpointer_conn_string` translates DATABASE_URL for psycopg (used only
by the LangGraph checkpointer, see graph.py) — regression coverage for a
real bug hit deploying against Neon: asyncpg/SQLAlchemy needs `?ssl=require`,
but psycopg/libpq has no `ssl` parameter, only `sslmode`, and errors on an
unrecognized one outright.
"""

from app.config import Settings
from app.orchestration.graph import _checkpointer_conn_string


def test_translates_asyncpg_scheme_to_plain_postgresql(monkeypatch) -> None:
    settings = Settings(database_url="postgresql+asyncpg://u:p@host/db")
    monkeypatch.setattr("app.orchestration.graph.get_settings", lambda: settings)
    assert _checkpointer_conn_string() == "postgresql://u:p@host/db"


def test_translates_ssl_require_to_sslmode_for_psycopg(monkeypatch) -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://u:p@host/db?ssl=require"
    )
    monkeypatch.setattr("app.orchestration.graph.get_settings", lambda: settings)
    result = _checkpointer_conn_string()
    assert result.startswith("postgresql://u:p@host/db?")
    assert "sslmode=require" in result
    assert "ssl=require" not in result


def test_leaves_other_query_params_untouched(monkeypatch) -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://u:p@host/db?ssl=require&application_name=agentforge"
    )
    monkeypatch.setattr("app.orchestration.graph.get_settings", lambda: settings)
    result = _checkpointer_conn_string()
    assert "sslmode=require" in result
    assert "application_name=agentforge" in result
