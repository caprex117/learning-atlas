from copy import deepcopy
from datetime import timedelta
from uuid import uuid4

import pytest

from atlas import domain
from atlas.models import SessionDraft, TrackDraft
from atlas.repository import RepositoryError, StaleData
from atlas.seed import factory_route
from atlas.service import Batch, LearningService


def uid():
    return str(uuid4())


def setup_learning(service):
    service.create_route(factory_route(), uid())
    phase = service.data["goal_phases"][0]["id"]
    draft = TrackDraft(title="Validador CSV", kind="project", area="Python",
        units=[{"key": "read", "title": "Leer un CSV"}, {"key": "test", "title": "Comprobar casos"}],
        skills=[{"name": "Programar en Python"}], topics=[{"name": "CSV", "skills": ["Programar en Python"]}])
    track = service.create_track(draft, uid(), status="active", phase_id=phase)["track_id"]
    return track, phase


def test_create_from_phase_is_one_learning_and_no_invented_activity(service):
    track, phase = setup_learning(service)
    assert service.data["phase_tracks"][0]["track_id"] == track
    assert service.data["phase_tracks"][0]["phase_id"] == phase
    assert len(service.data["learning_tracks"]) == 1
    assert domain.progress(service.data, track)["percent"] == 0
    assert domain.effort(service.data) == 0
    assert not service.data["topic_events"]
    service.toggle_unit(domain.track_units(service.data, track)[0]["id"], True, uid())
    assert domain.progress(service.data, track)["percent"] == 50
    assert not any(m["accepted_on"] for m in service.data["milestones"])
    assert domain.effort(service.data) == 0
    goal = service.data["learning_goals"][0]["id"]
    service.create_route(factory_route(), uid(), supersedes=goal)
    before = deepcopy(service.data)
    with pytest.raises(ValueError, match="archivada"):
        service.create_track(TrackDraft(title="No crear", kind="course"), uid(), phase_id=phase)
    assert service.repo.snapshot() == before


def test_correction_keeps_evidence_attachment_milestone_and_plan_counts_once(service):
    track, phase = setup_learning(service)
    skill = service.data["skills"][0]["id"]
    topic = service.data["topics"][0]["id"]
    area = service.data["areas"][0]["id"]
    service.add_learned_topic("CSV", "Python", service.current-timedelta(days=5), "Comprendido", uid())
    service.save_plan(30, "medium", uid())
    block = service.data["plan_blocks"][0]["id"]
    old_draft = SessionDraft(occurred_on=service.current, duration_minutes=30, area_id=area, track_id=track,
        phase_id=phase, skill_ids=[skill], topic_ids=[topic], activity_type="work_practice", rating="good",
        notes="Probé mi validador", evidence_title="Código probado", evidence_url="https://example.org/code", plan_block_id=block)
    old_id = service.record_session(old_draft, uid())["session_id"]
    evidence = deepcopy(service.data["learning_evidence"][0])
    service.repo.upload(service.repo.user_id+"/imports/test.txt", b"notes", "text/plain")
    b = Batch(service.data)
    b.put("attachments", {"resource_id": None, "evidence_id": evidence["id"], "original_name": "notas.txt",
        "storage_path": service.repo.user_id+"/imports/test.txt", "mime_type": "text/plain", "size_bytes": 5, "sha256": "a"*64})
    service._commit(b, uid(), {"action": "test_attachment"})
    milestone = next(m for m in service.data["milestones"] if m["phase_id"] == phase)
    service.accept_milestone(milestone["id"], True, "Cumple", evidence["id"], uid())
    links = {table: deepcopy(service.data[table]) for table in ["milestones", "attachments", "evidence_skills", "unit_progress"]}
    new_draft = old_draft.model_copy(update={"occurred_on": service.current-timedelta(days=1), "duration_minutes": 18,
        "notes": "Fueron 18 minutos ayer", "plan_block_id": None, "evidence_title": "", "evidence_url": None})
    request = uid()
    result = service.update_session(old_id, new_draft, "Fecha y tiempo", request)
    new_id = result["session_id"]
    assert new_id != old_id
    assert service.update_session(old_id, new_draft, "Fecha y tiempo", request) == result
    assert len(service.data["study_sessions"]) == 2
    assert domain.effort(service.data) == 18
    assert domain.skill_stats(service.data, skill)["minutes"] == 18
    assert domain.streak(service.data, service.current, 10)["current"] == 1
    assert len(domain.active_sessions(service.data)) == 1
    assert domain.by_id(service.data["study_sessions"])[old_id]["voided"]
    assert next(b for b in service.data["plan_blocks"] if b["id"] == block)["completed_session_id"] == new_id
    assert all(service.data[table] == rows for table, rows in links.items())
    moved = domain.by_id(service.data["learning_evidence"])[evidence["id"]]
    assert moved["session_id"] == new_id and moved["url"] == evidence["url"] and moved["description"] == evidence["description"]
    assert all(e["voided"] for e in service.data["topic_events"] if e.get("session_id") == old_id)
    assert len([e for e in service.data["topic_events"] if e.get("session_id") == new_id and not e["voided"]]) == 1
    with pytest.raises(RepositoryError):
        service.update_session(old_id, new_draft.model_copy(update={"duration_minutes": 19}), "Fecha y tiempo", request)
    service.void_session(new_id, "Esta práctica no ocurrió", uid())
    assert domain.effort(service.data) == 0
    assert next(b for b in service.data["plan_blocks"] if b["id"] == block)["completed_session_id"] is None


def test_correction_invalid_or_stale_is_atomic(service):
    track, phase = setup_learning(service)
    draft = SessionDraft(occurred_on=service.current, duration_minutes=20, area_id=service.data["areas"][0]["id"], track_id=track)
    sid = service.record_session(draft, uid())["session_id"]
    before = deepcopy(service.data)
    for changed, reason in [(draft, " "), (draft.model_copy(update={"phase_id": uid()}), "Fase"),
        (draft.model_copy(update={"occurred_on": service.current+timedelta(days=1)}), "Fecha")]:
        with pytest.raises(ValueError):
            service.update_session(sid, changed, reason, uid(), area_name="No crear si falla")
        assert service.repo.snapshot() == before
    stale = LearningService(service.repo)
    service.add_skill("Otra habilidad", "", "Otra área", uid())
    before = deepcopy(service.data)
    with pytest.raises(StaleData):
        stale.update_session(sid, draft.model_copy(update={"duration_minutes": 10}), "Duración", uid())
    assert service.repo.snapshot() == before


def test_independent_work_can_create_area_and_correct_skills(service):
    first = service.record_session(SessionDraft(occurred_on=service.current, duration_minutes=60, area_id="",
        activity_type="work_practice", notes="Apoyo técnico"), uid(), area_name=" Soporte   técnico ")["session_id"]
    assert service.data["areas"][0]["name"] == "Soporte técnico"
    assert domain.effort(service.data) == 60 and not service.data["learning_tracks"]
    skill = service.add_skill("Resolver incidentes", "", "Soporte técnico", uid())["skill_id"]
    service.update_session(first, SessionDraft(occurred_on=service.current, duration_minutes=40, area_id="",
        activity_type="work_practice", skill_ids=[skill]), "Tiempo y habilidad", uid(), area_name="soporte técnico")
    assert len(service.data["areas"]) == 1
    assert domain.skill_stats(service.data, skill)["minutes"] == 40


def test_phase_visibility_grace_archive_keep_and_original_acceptance(service):
    service.create_route(factory_route(), uid())
    phases = service.data["goal_phases"]
    old, yesterday, today, pending = [p["id"] for p in phases[:4]]
    b = Batch(service.data)
    for pid, days in [(old, 2), (yesterday, 1), (today, 0)]:
        milestone = next(m for m in b.data["milestones"] if m["phase_id"] == pid)
        b.put("milestones", {**milestone, "accepted_on": (service.current-timedelta(days=days)).isoformat()})
    service._commit(b, uid(), {"action": "test_past_acceptance"})
    visible = domain.by_id(domain.session_phases(service.data, service.current))
    assert old not in visible and {yesterday, today, pending} <= visible.keys()
    assert old in domain.by_id(domain.session_phases(service.data, service.current, show_finished=True))
    assert old in domain.by_id(domain.session_phases(service.data, service.current, keep_id=old))
    milestone = next(m for m in service.data["milestones"] if m["phase_id"] == old)
    service.accept_milestone(milestone["id"], True, "Sólo cambio notas", None, uid())
    assert domain.by_id(service.data["milestones"])[milestone["id"]]["accepted_on"] == milestone["accepted_on"]
    service.create_route(factory_route(), uid(), supersedes=service.data["learning_goals"][0]["id"])
    visible = domain.by_id(domain.session_phases(service.data, service.current))
    assert not set(p["id"] for p in phases) & visible.keys()
    assert len(domain.session_phases(service.data, service.current, show_finished=True)) == 14
    assert "v1 · archivada" in domain.session_phases(service.data, service.current, keep_id=pending)[-1]["label"]
