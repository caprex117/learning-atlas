"""Run the same service against real SQL: PostgreSQL server or PostgreSQL WASM.

Auth and Storage control tables are simulated; no Supabase HTTP/Auth/Storage API is tested here.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4

from atlas.repository import RepositoryError, StaleData

ROOT=Path(__file__).resolve().parents[1]


class SQLHarness:
    def __init__(self):
        self.dsn=os.getenv("ATLAS_TEST_DATABASE_URL")
        self.process=None
        if self.dsn:
            import psycopg
            self.connection=psycopg.connect(self.dsn,autocommit=True)
            if not self.connection.info.dbname.endswith("_test"):
                self.connection.close()
                raise ValueError("The disposable database name must end in _test. Never use production.")
        else:
            node=os.getenv("ATLAS_NODE") or shutil.which("node")
            if not node or not (ROOT/"scripts/sql-harness/node_modules/@electric-sql/pglite").exists():
                raise FileNotFoundError("Install scripts/sql-harness dependencies or set ATLAS_TEST_DATABASE_URL for a disposable PostgreSQL database.")
            self.process=subprocess.Popen([node,str(ROOT/"scripts/sql-harness/bridge.mjs")],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE,text=True,encoding="utf-8",cwd=ROOT)
            ready=self.process.stdout.readline()
            if not ready or not json.loads(ready).get("ready"):
                raise RuntimeError("PostgreSQL test engine did not start.")
        self.exec((ROOT/"tests/bootstrap.sql").read_text(encoding="utf-8"))
        for migration in sorted((ROOT/"supabase/migrations").glob('*.sql')):
            self.exec(migration.read_text(encoding="utf-8"))

    def request(self,sql,params=None,exec=False):
        if self.process:
            self.process.stdin.write(json.dumps({"sql":sql,"params":params or [],"exec":exec})+"\n")
            self.process.stdin.flush()
            raw=self.process.stdout.readline()
            if not raw:
                raise RuntimeError("SQL test process stopped.")
            result=json.loads(raw)
            if "error" in result:
                raise RepositoryError(result["error"])
            return result["result"]
        # Adapt numbered PostgreSQL parameters to psycopg placeholders without interpolation.
        if params:
            import re
            order=[]
            def replace(match):
                order.append(params[int(match.group(1))-1])
                return "%s"
            sql=re.sub(r"\$(\d+)",replace,sql)
            params=order
        import psycopg
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql,params or None)
                if exec:
                    return []
                # INSERT/UPDATE/DELETE without RETURNING still use the query contract.
                if cursor.description is None:
                    return {"rows":[]}
                names=[c.name for c in cursor.description]
                return {"rows":[dict(zip(names,row)) for row in cursor.fetchall()]}
        except psycopg.Error as exc:
            # Expose the same error contract as the PGlite bridge.
            raise RepositoryError(str(exc)) from exc

    def query(self,sql,params=None):
        return self.request(sql,params)["rows"]

    def exec(self,sql):
        return self.request(sql,exec=True)

    def actor(self,user):
        self.exec("reset role")
        self.query("select set_config('request.jwt.claim.sub',$1,false)",[user or ""])
        self.exec("set role authenticated" if user else "set role anon")

    def close(self):
        if self.process:
            self.process.stdin.write('{"close":true}\n')
            self.process.stdin.flush()
            self.process.wait(timeout=15)
        else:
            self.connection.close()


class SQLRepository:
    is_demo=False
    def __init__(self,harness):
        self.h=harness
        self.user_id=str(uuid4())
        self.files={}
        self.h.exec("reset role")
        self.h.query("insert into auth.users(id) values($1)",[self.user_id])
        self.h.actor(self.user_id)
        self.h.query("select public.atlas_bootstrap()")

    def snapshot(self):
        self.h.actor(self.user_id)
        return self.h.query("select public.atlas_snapshot() as data")[0]["data"]

    def commit(self,changes,request_id,expected_revision,intent,result=None,import_approval=None):
        self.h.actor(self.user_id)
        try:
            return self.h.query("select public.atlas_apply($1::uuid,$2::bigint,$3::jsonb,$4::jsonb,$5::jsonb,$6::jsonb) as data",
                [request_id,expected_revision,json.dumps(intent),json.dumps(changes),json.dumps(result or {}),json.dumps(import_approval) if import_approval else None])[0]["data"]
        except Exception as exc:
            if "STALE_REVISION" in str(exc) or "IMPORT_REVIEW_CHANGED" in str(exc):
                raise StaleData(str(exc)) from exc
            raise RepositoryError(str(exc)) from exc

    def upload(self,path,contents,mime):
        self.h.actor(self.user_id)
        self.h.query("insert into storage.objects(bucket_id,name) values('learning-documents',$1)",[path])
        self.files[path]=bytes(contents)

    def download(self,path):
        self.h.actor(self.user_id)
        if not self.h.query("select name from storage.objects where name=$1",[path]):
            raise RepositoryError("PRIVATE_FILE_NOT_FOUND")
        return self.files[path]

    def remove_file(self,path):
        self.h.actor(self.user_id)
        self.h.query("delete from storage.objects where name=$1 returning name",[path])
        self.files.pop(path,None)
