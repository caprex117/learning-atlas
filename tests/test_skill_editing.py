from copy import deepcopy
from uuid import uuid4

import pytest

from atlas import domain
from atlas.models import SessionDraft, TrackDraft
from atlas.repository import StaleData
from atlas.service import LearningService


def uid():
    return str(uuid4())


def test_edit_skill_keeps_identity_practice_assessments_and_course_links(service):
    track_id = service.create_track(TrackDraft(title="SQL práctico", kind="course", area="Datos",
        skills=[{"name": "Consultas SQL"}], topics=[{"name": "JOIN", "skills": ["Consultas SQL"]}]), uid())["track_id"]
    skill = service.data["skills"][0]
    skill_id, old_area_id = skill["id"], skill["area_id"]
    service.record_session(SessionDraft(occurred_on=service.current, duration_minutes=35, area_id=old_area_id,
        track_id=track_id, skill_ids=[skill_id], evidence_title="Consulta comprobada", notes="Crucé dos tablas"), uid())
    service.assess(skill_id, service.current, 2, "Resuelvo consultas por mi cuenta", None, uid())
    original = {table: deepcopy(rows) for table, rows in service.data.items() if table not in {"skills", "areas", "profiles"}}
    request_id = uid()
    result = service.update_skill(skill_id, "  Consultar   bases de datos  ", "Combinar tablas para responder preguntas", "Bases de datos", request_id)
    assert service.update_skill(skill_id, "Consultar bases de datos", "Combinar tablas para responder preguntas", "Bases de datos", request_id) == result
    updated = domain.by_id(service.data["skills"])[skill_id]
    assert updated["name"] == "Consultar bases de datos"
    assert updated["definition"] == "Combinar tablas para responder preguntas"
    assert domain.by_id(service.data["areas"])[updated["area_id"]]["name"] == "Bases de datos"
    assert service.data["study_sessions"][0]["area_id"] == old_area_id
    assert domain.skill_stats(service.data, skill_id)["minutes"] == 35
    assert domain.skill_coverage(service.data, skill_id) == {track_id}
    assert all(service.data[table] == rows for table, rows in original.items())
    assert len(service.data["skills"]) == 1


def test_edit_skill_reuses_existing_area_and_rejects_duplicate_name_atomically(service):
    first = service.add_skill("SQL", "Consultas", "Datos", uid())["skill_id"]
    second = service.add_skill("Python", "Programación", "Software", uid())["skill_id"]
    software_id = domain.by_id(service.data["skills"])[second]["area_id"]
    service.update_skill(first, "SQL", "Consultas corregidas", " software ", uid())
    assert len(service.data["areas"]) == 2
    assert domain.by_id(service.data["skills"])[first]["area_id"] == software_id
    before = deepcopy(service.data)
    with pytest.raises(ValueError, match="otra habilidad"):
        service.update_skill(first, "  pYtHoN ", "No debe guardarse", "Área que tampoco debe crearse", uid())
    assert service.repo.snapshot() == before


@pytest.mark.parametrize("fields", [
    ("   ", "Descripción", "Datos"), ("SQL", "Descripción", "  "),
    ("SQL", "Descripción", "x" * 181), ("x" * 181, "Descripción", "Datos"),
    ("SQL", "x" * 701, "Datos"),
])
def test_invalid_skill_edit_does_not_write_anything(service, fields):
    skill_id = service.add_skill("SQL", "Consultas", "Datos", uid())["skill_id"]
    before = deepcopy(service.data)
    with pytest.raises(ValueError):
        service.update_skill(skill_id, *fields, uid())
    assert service.repo.snapshot() == before


def test_edit_skill_rejects_missing_identity_and_stale_snapshot(service):
    skill_id = service.add_skill("SQL", "Consultas", "Datos", uid())["skill_id"]
    before = deepcopy(service.data)
    with pytest.raises(ValueError, match="no está disponible"):
        service.update_skill(uid(), "Otra", "", "Área ausente", uid())
    assert service.repo.snapshot() == before
    stale = LearningService(service.repo)
    service.update_skill(skill_id, "SQL corregido", "Versión guardada", "Datos", uid())
    latest = deepcopy(service.data)
    with pytest.raises(StaleData):
        stale.update_skill(skill_id, "Nombre desactualizado", "", "Datos", uid())
    assert service.repo.snapshot() == latest
