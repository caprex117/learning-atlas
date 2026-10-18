import copy
import pytest
from uuid import uuid4

from atlas.models import TrackDraft,ImportProposal
from atlas.repository import RepositoryError
from atlas.service import LearningService
from .sql_backend import SQLRepository


def uid(): return str(uuid4())


def test_rls_and_cross_user_references(sql_engine):
    a,b=SQLRepository(sql_engine),SQLRepository(sql_engine)
    sa,sb=LearningService(a),LearningService(b)
    ta=sa.create_track(TrackDraft(title="Privado A",kind="course",area="A"),uid())["track_id"]
    tb=sb.create_track(TrackDraft(title="Privado B",kind="course",area="B"),uid())["track_id"]
    sql_engine.actor(b.user_id)
    assert [r["title"] for r in sql_engine.query("select title from public.learning_tracks")]==["Privado B"]
    with pytest.raises(RepositoryError):
        sql_engine.query("update public.learning_tracks set title='mal' where id=$1",[ta])
    with pytest.raises(RepositoryError):
        b.commit([{"op":"upsert","table":"learning_tracks","row":{"id":ta,"title":"mal","kind":"course","area_id":sb.data["areas"][0]["id"]}}],uid(),sb.profile["revision"],{"action":"bad"})
    # An owned row still cannot link to another user's area.
    with pytest.raises(RepositoryError):
        b.commit([{"op":"upsert","table":"learning_tracks","row":{"id":uid(),"title":"mal","kind":"course","area_id":sa.data["areas"][0]["id"]}}],uid(),sb.profile["revision"],{"action":"crossfk"})
    assert [t["title"] for t in a.snapshot()["learning_tracks"]]==["Privado A"]
    assert [t["title"] for t in b.snapshot()["learning_tracks"]]==["Privado B"]
    sql_engine.actor(None)
    with pytest.raises(RepositoryError):
        sql_engine.query("select * from public.learning_tracks")
    with pytest.raises(RepositoryError):
        sql_engine.query("select public.atlas_snapshot()")


def test_transaction_failure_rolls_back_every_row_and_receipt(sql_engine):
    repo=SQLRepository(sql_engine)
    snapshot=repo.snapshot()
    request=uid()
    changes=[{"op":"upsert","table":"areas","row":{"id":uid(),"name":"No debe persistir"}},
             {"op":"upsert","table":"skills","row":{"id":uid(),"name":"FK inválida","area_id":uid()}}]
    with pytest.raises(RepositoryError):
        repo.commit(changes,request,0,{"action":"broken"})
    assert repo.snapshot()==snapshot
    sql_engine.actor(repo.user_id)
    assert not sql_engine.query("select * from public.mutation_receipts where request_id=$1",[request])


def test_database_independently_rejects_overallocation(sql_engine):
    repo=SQLRepository(sql_engine)
    area,session,s1,s2=uid(),uid(),uid(),uid()
    changes=[{"op":"upsert","table":"areas","row":{"id":area,"name":"SQL"}},
        *[{"op":"upsert","table":"skills","row":{"id":sid,"name":sid,"area_id":area}} for sid in [s1,s2]],
        {"op":"upsert","table":"study_sessions","row":{"id":session,"area_id":area,"occurred_on":"2026-01-01","timezone_at_entry":"America/La_Paz","duration_minutes":30,"activity_type":"study"}},
        *[{"op":"upsert","table":"session_skills","row":{"id":uid(),"session_id":session,"skill_id":sid,"allocated_minutes":20}} for sid in [s1,s2]]]
    with pytest.raises(RepositoryError,match="ALLOCATION_EXCEEDS_SESSION"):
        repo.commit(changes,uid(),0,{"action":"overallocate"})
    assert not repo.snapshot()["study_sessions"] and not repo.snapshot()["areas"]


def test_sql_rejects_unknown_tables_columns_and_intent_reuse(sql_engine):
    repo=SQLRepository(sql_engine)
    request=uid()
    repo.commit([],request,0,{"action":"first"})
    with pytest.raises(RepositoryError,match="REQUEST_ID_REUSED"):
        repo.commit([],request,1,{"action":"different"})
    for table,row in [("auth.users",{"id":uid()}),("areas",{"id":uid(),"name":"a","unexpected":1}),("profiles",{"id":repo.user_id,"revision":5})]:
        with pytest.raises(RepositoryError):
            repo.commit([{"op":"upsert","table":table,"row":row}],uid(),1,{"action":"bad"})
    assert repo.snapshot()["profiles"][0]["revision"]==1


def test_private_files_owner_and_retention(sql_engine):
    a,b=SQLRepository(sql_engine),SQLRepository(sql_engine)
    path=a.user_id+"/imports/private.txt"
    a.upload(path,b"private","text/plain")
    sql_engine.actor(b.user_id)
    assert not sql_engine.query("select name from storage.objects where name=$1",[path])
    with pytest.raises(RepositoryError):
        b.upload(a.user_id+"/imports/forged.txt",b"bad","text/plain")
    sa=LearningService(a)
    proposal=ImportProposal(tracks=[TrackDraft(title="SQL",kind="topic")])
    jid=sa.stage_import(proposal,{"filename":"private.txt","sha256":"a"*64,"mime_type":"text/plain","storage_path":path},uid())["job_id"]
    sql_engine.actor(a.user_id)
    assert not sql_engine.query("delete from storage.objects where name=$1 returning name",[path])
    sa.apply_import(jid,sa.data["import_jobs"][0]["proposal_hash"],uid(),accepted=True)
    sql_engine.actor(a.user_id)
    assert not sql_engine.query("delete from storage.objects where name=$1 returning name",[path])


def test_import_rpc_rejects_changed_proposal_even_with_fresh_revision(sql_engine):
    repo=SQLRepository(sql_engine)
    service=LearningService(repo)
    p=ImportProposal(tracks=[TrackDraft(title="A",kind="topic")])
    jid=service.stage_import(p,{"filename":"a.json","sha256":"a"*64,"mime_type":"application/json","storage_path":None},uid())["job_id"]
    wrong=p.model_dump(mode="json")
    wrong["tracks"][0]["title"]="Otra propuesta"
    with pytest.raises(RepositoryError,match="IMPORT_REVIEW_CHANGED"):
        repo.commit([],uid(),service.profile["revision"],{"action":"wrong"},import_approval={"job_id":jid,"proposal":wrong})


def test_future_dates_and_parent_progress_rejected_in_database(sql_engine):
    repo=SQLRepository(sql_engine)
    service=LearningService(repo)
    result=service.create_track(TrackDraft(title="A",kind="course",units=[{"key":"m","title":"M"},{"key":"u","parent_key":"m","title":"U"}]),uid())
    units=service.data["units"]
    parent=next(u for u in units if not u["parent_id"])
    leaf=next(u for u in units if u["parent_id"])
    with pytest.raises(RepositoryError,match="FUTURE_ACTIVITY"):
        repo.commit([{"op":"upsert","table":"unit_progress","row":{"id":uid(),"unit_id":leaf["id"],"completed_on":"2999-01-01"}}],uid(),service.profile["revision"],{"action":"future"})
    with pytest.raises(RepositoryError,match="ONLY_LEAF_UNITS_COUNT"):
        repo.commit([{"op":"upsert","table":"track_units","row":{"id":uid(),"track_id":result["track_id"],"unit_id":parent["id"],"resource_id":parent["resource_id"]}}],uid(),service.profile["revision"],{"action":"parent"})
