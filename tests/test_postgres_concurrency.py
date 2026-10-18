"""True two-connection lock test; intentionally skipped by single-connection PGlite."""
from concurrent.futures import ThreadPoolExecutor
import json
from threading import Barrier
from uuid import uuid4

import pytest

from .sql_backend import SQLRepository


@pytest.mark.postgres
def test_two_connections_cannot_overwrite_same_revision(sql_engine):
    if not sql_engine.dsn:
        pytest.skip("Requires a PostgreSQL server with two independent connections; PGlite is single-connection.")
    import psycopg
    repo=SQLRepository(sql_engine)
    barrier=Barrier(2)
    def write(name):
        with psycopg.connect(sql_engine.dsn,autocommit=True) as conn:
            conn.execute("select set_config('request.jwt.claim.sub',%s,false)",[repo.user_id])
            conn.execute("set role authenticated")
            barrier.wait(timeout=10)
            try:
                conn.execute("select public.atlas_apply(%s::uuid,0,%s::jsonb,%s::jsonb)",
                    [str(uuid4()),json.dumps({"action":name}),json.dumps([{"op":"upsert","table":"areas","row":{"id":str(uuid4()),"name":name}}])])
                return "saved"
            except psycopg.Error as exc:
                assert "STALE_REVISION" in str(exc)
                return "stale"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(write,["first","second"]))
    assert sorted(results)==["saved","stale"]
    assert len(repo.snapshot()["areas"])==1
