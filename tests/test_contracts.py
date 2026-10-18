from datetime import date,timedelta
from uuid import uuid4
import copy

import pytest
from pydantic import ValidationError

from atlas import domain
from atlas.models import ImportProposal,SessionDraft,TrackDraft,canonical_hash
from atlas.repository import RepositoryError,StaleData
from atlas.seed import factory_route
from atlas.service import Batch,LearningService


def uid(): return str(uuid4())


def draft():
    return TrackDraft.model_validate({"title":"Python práctico","kind":"course","area":"Python",
        "units":[{"key":"m","title":"Fundamentos"},{"key":"a","parent_key":"m","title":"Funciones","estimated_minutes":20},
                 {"key":"b","parent_key":"m","title":"Colecciones","weight":3},
                 {"key":"x","title":"Extra","required":False,"estimated_minutes":50}],
        "skills":[{"name":"Python"},{"name":"Pruebas"}],"topics":[{"name":"Funciones","skills":["Python"]}]})


def create(service,status="active"):
    result=service.create_track(draft(),uid(),status=status)
    return result["track_id"]


def test_progress_required_leaves_weights_and_estimate(service):
    tid=create(service)
    assert domain.progress(service.data,tid)=={"total":2,"done":0,"percent":0,"weight_done":0,"weight_total":4}
    rows=domain.track_units(service.data,tid)
    service.toggle_unit(next(u["id"] for u in rows if u["title"]=="Funciones"),True,uid())
    assert domain.progress(service.data,tid)["percent"]==25
    track=domain.by_id(service.data["learning_tracks"])[tid]
    assert domain.estimate(service.data,track)["remaining"]==0
    assert domain.estimate(service.data,track)["missing"]==1
    assert domain.effort(service.data)==0


def test_zero_units_unknown_not_zero_progress(service):
    tid=service.create_track(TrackDraft(title="Sin temario",kind="topic"),uid())["track_id"]
    assert domain.progress(service.data,tid)["percent"] is None
    with pytest.raises(ValueError):
        service.update_track(tid,{"status":"completed"},uid())


def test_time_allocation_coverage_evidence_and_void(service):
    tid=create(service)
    track=domain.by_id(service.data["learning_tracks"])[tid]
    skills=[s["id"] for s in service.data["skills"]]
    topic=service.data["topics"][0]["id"]
    rid=uid()
    session=SessionDraft(occurred_on=service.current,duration_minutes=31,area_id=track["area_id"],track_id=tid,
                         skill_ids=skills,topic_ids=[topic],evidence_title="CSV comprobado",evidence_url="https://example.org/evidence")
    result=service.record_session(session,rid)
    assert service.record_session(session,rid)==result
    assert len(service.data["study_sessions"])==1
    assert domain.effort(service.data)==31
    assert sorted(a["allocated_minutes"] for a in service.data["session_skills"])==[15,16]
    assert all(domain.skill_stats(service.data,s)["sessions"]==1 for s in skills)
    assert domain.skill_coverage(service.data,skills[0])=={tid}
    assert domain.review_state(service.data,topic,service.current) is None
    service.void_session(result["session_id"],"Duración incorrecta",uid())
    assert domain.effort(service.data)==0
    assert domain.skill_stats(service.data,skills[0])["evidence"]==[]


def test_stale_revision_requires_refresh(service):
    stale=LearningService(service.repo)
    create(service)
    with pytest.raises(StaleData):
        stale.create_track(TrackDraft(title="Otro",kind="topic"),uid())
    assert len(service.repo.snapshot()["learning_tracks"])==1


def test_atomic_import_approved_once_and_no_progress(service):
    proposal=ImportProposal(tracks=[draft()],route=factory_route())
    file=b"Documento de ejemplo, sin horas realizadas"
    path=service.repo.user_id+"/imports/test.txt"
    service.repo.upload(path,file,"text/plain")
    jid=service.stage_import(proposal,{"filename":"test.txt","sha256":"a"*64,"mime_type":"text/plain","storage_path":path},uid())["job_id"]
    job=domain.by_id(service.data["import_jobs"])[jid]
    with pytest.raises(ValueError):
        service.apply_import(jid,job["proposal_hash"],uid())
    assert not service.data["learning_tracks"]
    result=service.apply_import(jid,job["proposal_hash"],uid(),accepted=True)
    before=copy.deepcopy(service.data)
    assert service.apply_import(jid,job["proposal_hash"],uid(),accepted=True)==result
    assert service.data==before
    assert len(service.data["learning_tracks"])==1
    assert len(service.data["units"])==4 and len(service.data["track_units"])==3
    assert len(service.data["goal_phases"])==7
    assert len(service.data["attachments"])==1
    assert service.data["attachments"][0]["size_bytes"]==len(file)
    assert domain.effort(service.data)==0 and not service.data["unit_progress"] and not service.data["topic_events"]
    assert service.data["learning_tracks"][0]["source_type"]=="reviewed_import"


def test_import_changed_after_review_rejected(service):
    info={"filename":"x.json","sha256":"b"*64,"mime_type":"application/json","storage_path":None}
    jid=service.stage_import(ImportProposal(tracks=[draft()]),info,uid())["job_id"]
    old=domain.by_id(service.data["import_jobs"])[jid]["proposal_hash"]
    new=draft().model_copy(update={"title":"Revisado"})
    service.stage_import(ImportProposal(tracks=[new]),info,uid(),job_id=jid)
    with pytest.raises(StaleData):
        service.apply_import(jid,old,uid(),accepted=True)
    assert not service.data["learning_tracks"]


def test_import_attach_existing_reuses_coverage_preserves_completed_units(service):
    tid=create(service)
    units=domain.track_units(service.data,tid)
    service.toggle_unit(units[0]["id"],True,uid())
    proposal=ImportProposal(tracks=[draft()])
    jid=service.stage_import(proposal,{"filename":"x.json","sha256":"b"*64,"mime_type":"application/json","storage_path":None},uid())["job_id"]
    h=domain.by_id(service.data["import_jobs"])[jid]["proposal_hash"]
    service.apply_import(jid,h,uid(),target_track_id=tid,accepted=True)
    assert len(service.data["learning_tracks"])==1
    assert len(service.data["unit_progress"])==1
    assert len(service.data["track_skills"])==2
    assert len(service.data["track_topics"])==1
    assert len(domain.track_units(service.data,tid))==6


def test_cancel_draft_keeps_learning_untouched(service):
    path=service.repo.user_id+"/imports/cancel.txt"
    service.repo.upload(path,b"cancel","text/plain")
    jid=service.stage_import(ImportProposal(tracks=[draft()]),{"filename":"cancel.txt","sha256":"c"*64,"mime_type":"text/plain","storage_path":path},uid())["job_id"]
    assert not service.cancel_import(jid,uid())["cleanup_pending"]
    assert not service.data["learning_tracks"]
    assert service.data["import_jobs"][0]["status"]=="cancelled"


def test_plan_does_not_log_time_and_record_is_once(service):
    tid=create(service)
    result=service.save_plan(20,"low",uid())
    blocks=service.data["plan_blocks"]
    assert len(blocks)==1 and blocks[0]["planned_minutes"]==20
    assert domain.effort(service.data)==0
    track=domain.by_id(service.data["learning_tracks"])[tid]
    draft_session=SessionDraft(occurred_on=service.current,duration_minutes=18,area_id=track["area_id"],track_id=tid,plan_block_id=blocks[0]["id"])
    rid=uid()
    sid=service.record_session(draft_session,rid)["session_id"]
    with pytest.raises(ValueError):
        service.record_session(draft_session,uid())
    assert domain.effort(service.data)==18
    service.void_session(sid,"Registrar de nuevo",uid())
    assert service.data["plan_blocks"][0]["completed_session_id"] is None


def test_route_versions_preserve_original(service):
    route=factory_route()
    assert sum(p.budget_minutes for p in route.phases)==5760
    result=service.create_route(route,uid())
    service.create_route(route.model_copy(update={"weekly_minutes":360}),uid(),supersedes=result["goal_id"])
    goals=sorted(service.data["learning_goals"],key=lambda g:g["version"])
    assert [(g["version"],g["status"],g["weekly_minutes"]) for g in goals]==[(1,"archived",480),(2,"active",360)]
    assert not service.data["study_sessions"]


def test_skill_evolution_requires_same_rubric_distinct_days(service):
    create(service)
    sid=service.data["skills"][0]["id"]
    service.assess(sid,service.current-timedelta(days=2),1,"Pude con guía",None,uid())
    rubric=service.data["skill_rubrics"][0]["id"]
    assert not domain.evolution(service.data,sid,rubric)["comparable"]
    service.assess(sid,service.current,2,"Lo hice por mi cuenta",None,uid())
    evo=domain.evolution(service.data,sid,rubric)
    assert evo["comparable"] and evo["last"]["level"]==2
    with pytest.raises(ValueError):
        service.assess(sid,service.current,3,"Otro intento el mismo día",None,uid())


def test_streak_yesterday_grace_and_threshold():
    current=date(2026,10,17)
    data={"study_sessions":[{"occurred_on":"2026-10-16","duration_minutes":10},
        {"occurred_on":"2026-10-15","duration_minutes":6},{"occurred_on":"2026-10-15","duration_minutes":4},
        {"occurred_on":"2026-10-14","duration_minutes":9},{"occurred_on":"2026-10-17","duration_minutes":50,"voided":True}]}
    assert domain.streak(data,current)=={"current":2,"longest":2}
    assert domain.streak(data,current+timedelta(days=1))["current"]==0


def test_review_daily_limit_backdated_and_ungraded_practice():
    data={"topic_events":[{"id":"a","topic_id":"t","occurred_on":"2026-10-01","event_type":"learned"},
          {"id":"b","topic_id":"t","occurred_on":"2026-10-03","event_type":"review","rating":"good"},
          {"id":"c","topic_id":"t","occurred_on":"2026-10-03","event_type":"review","rating":"easy"},
          {"id":"d","topic_id":"t","occurred_on":"2026-10-16","event_type":"work_practice"}]}
    result=domain.review_state(data,"t",date(2026,10,17))
    assert result["interval"]==6 and result["reviews"]==1
    assert result["last_practice"]==date(2026,10,16) and result["next"]==date(2026,10,9)
    data["topic_events"].append({"id":"e","topic_id":"t","occurred_on":"2026-10-10","event_type":"review","rating":"again"})
    assert domain.review_state(data,"t",date(2026,10,17))["next"]==date(2026,10,11)


@pytest.mark.parametrize("budget",[20,30,45,60,90,120])
@pytest.mark.parametrize("energy",["low","medium","high"])
def test_plan_boundaries(budget,energy):
    data={"learning_tracks":[{"id":str(i),"status":"active","priority":i+1} for i in range(3)],
          "units":[{"id":str(i),"title":"Unidad","sort_order":0} for i in range(3)],
          "track_units":[{"track_id":str(i),"unit_id":str(i)} for i in range(3)]}
    blocks=domain.make_plan(data,date(2026,10,17),budget,energy)
    assert 1<=len(blocks)<=3
    assert all(10<=b["planned_minutes"]<=40 for b in blocks)
    assert sum(b["planned_minutes"] for b in blocks)+5*(len(blocks)-1)<=budget


@pytest.mark.parametrize("change",[
    {"units":[{"key":"a","title":"A","parent_key":"b"},{"key":"b","title":"B","parent_key":"a"}]},
    {"units":[{"key":"a","title":"A","estimated_minutes":True}]},
    {"units":[{"key":"a","title":"A","parent_key":"missing"}]},
    {"topics":[{"name":"Tema","skills":["No definida"]}]},
    {"progress":100}, {"source_url":"javascript:alert(1)"}, {"source_url":"https://user:password@example.com"},
])
def test_invalid_proposals_rejected(change):
    with pytest.raises(ValidationError):
        TrackDraft.model_validate({"title":"Python","kind":"course",**change})
