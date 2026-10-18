from datetime import timedelta
from uuid import uuid4
import json
import httpx
import pytest

from atlas import domain
from atlas.auth import validate_config
from atlas.discovery import fetch_feed
from atlas.models import TrackDraft,SessionDraft,canonical_hash
from atlas.repository import export_json


def uid(): return str(uuid4())


def test_json_hash_survives_jsonb_numeric_normalization():
    assert canonical_hash({"weight":1.0,"a":[3.0,1.5]})==canonical_hash({"a":[3,1.5],"weight":1})
    assert canonical_hash({"weight":1})!=canonical_hash({"weight":2})


def test_learned_work_practice_review_and_settings(service):
    service.settings("Mi espacio","America/Puerto_Rico",480,10,uid())
    assert service.profile["timezone"]=="America/Puerto_Rico"
    tid=service.add_learned_topic("Consultas SQL","SQL",service.current-timedelta(days=4),"Ya entiendo JOIN",uid())["topic_id"]
    area=service.data["topics"][0]["area_id"]
    service.record_session(SessionDraft(occurred_on=service.current,duration_minutes=20,area_id=area,topic_ids=[tid],activity_type="work_practice",rating="good"),uid())
    state=domain.review_state(service.data,tid,service.current)
    assert state["interval"]==6 and state["last_practice"]==service.current
    assert service.data["study_sessions"][0]["timezone_at_entry"]=="America/Puerto_Rico"
    assert domain.effort(service.data)==20


def test_credential_does_not_complete_course_or_invent_time(service):
    tid=service.create_track(TrackDraft(title="Curso",kind="course"),uid())["track_id"]
    service.add_credential(dict(official_name="Curso completado",issuer="Proveedor",credential_type="course",track_id=tid,
        earned_on=None,period_label="Fall 2024",expires_on=None,never_expires=False,verification_url=None,notes="Declarado por mí"),uid())
    assert len(service.data["credentials"])==1
    assert service.data["learning_tracks"][0]["status"]=="planned"
    assert domain.effort(service.data)==0
    assert domain.credential_status(service.data["credentials"][0],service.current)=="Vigencia por confirmar"
    assert "password" not in export_json(service.data)


def test_reopen_unit_reopens_completed_course(service):
    tid=service.create_track(TrackDraft(title="Corto",kind="course",units=[{"key":"u","title":"Tema"}]),uid())["track_id"]
    unit=service.data["units"][0]["id"]
    service.toggle_unit(unit,True,uid())
    service.update_track(tid,{"status":"completed"},uid())
    service.toggle_unit(unit,False,uid())
    assert service.data["learning_tracks"][0]["status"]=="active"
    assert domain.progress(service.data,tid)["percent"]==0


def test_correct_unit_estimate_and_credential(service):
    tid=service.create_track(TrackDraft(title="Corto",kind="course",units=[{"key":"u","title":"Tema"}]),uid())["track_id"]
    unit=service.data["units"][0]["id"]
    service.update_unit(tid,unit,"Tema corregido",45,True,2,False,uid())
    assert domain.estimate(service.data,service.data["learning_tracks"][0])["remaining"]==45
    assert domain.effort(service.data)==0
    service.toggle_unit(unit,True,uid())
    service.update_track(tid,{"status":"completed"},uid())
    service.update_unit(tid,unit,"Tema corregido",45,True,2,True,uid())
    assert not domain.track_units(service.data,tid)
    assert len(service.data["unit_progress"])==1
    assert service.data["learning_tracks"][0]["status"]=="active"
    fields=dict(official_name="Curso completado",issuer="Proveedor",credential_type="course",track_id=tid,
        earned_on=None,period_label="Fall 2024",expires_on=None,never_expires=False,verification_url=None,notes="")
    service.add_credential(fields,uid())
    cid=service.data["credentials"][0]["id"]
    service.add_credential({**fields,"period_label":"Spring 2024"},uid(),credential_id=cid)
    assert len(service.data["credentials"])==1 and service.data["credentials"][0]["period_label"]=="Spring 2024"


def test_empty_rss_is_valid_and_has_consultation_timestamp():
    xml=b'<?xml version="1.0"?><rss version="2.0"><channel><title>arXiv</title><link>https://arxiv.org</link><description>No announcements</description></channel></rss>'
    result=fetch_feed("arXiv · aprendizaje automático",transport=httpx.MockTransport(lambda request:httpx.Response(200,content=xml)))
    assert result["items"]==[] and result["checked_at"]


def test_discovery_never_follows_a_redirect():
    def handler(request):
        return httpx.Response(302,headers={"Location":"http://127.0.0.1/private"})
    with pytest.raises(httpx.HTTPStatusError):
        fetch_feed("pandas · versiones",transport=httpx.MockTransport(handler))


@pytest.mark.parametrize("key",["sb_secret_not-allowed","invalid", "eyJ.e30.signature"])
def test_privileged_or_invalid_keys_are_rejected(key):
    with pytest.raises(ValueError):
        validate_config({"url":"https://test.supabase.co","key":key})
