"""Public learning templates; only the explicit demo creates fictional activity."""
import json
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from .models import RouteDraft, TrackDraft, SessionDraft
from .repository import MemoryRepository
from .service import Batch, LearningService
from . import domain

DATA = Path(__file__).resolve().parent.parent / "data"


def read_data(name):
    return json.loads((DATA / (name + ".json")).read_text(encoding="utf-8"))


def factory_route():
    return RouteDraft.model_validate({"title": "Factory Enablement", "outcome": "Construir y explicar un piloto reproducible de datos y sistemas industriales.",
        "weekly_minutes": 480, "phases": [{"title": p["title"], "starts_on": p["start"], "ends_on": p["end"],
        "budget_minutes": p["hours"]*60, "milestone": p["result"], "criteria": "\n".join(p["criteria"]),
        "topics": p["topics"], "is_buffer": p["id"] == "p7"} for p in read_data("phases")]})


def initialize_dictionary(service, request_id):
    b = Batch(service.data)
    for s in read_data("skillCatalog"):
        area = b.named("areas", s["area"])
        b.named("skills", s["name"], area_id=area, definition=s["definition"])
    return service._commit(b, request_id, {"action": "initialize_dictionary", "version": 1})


def demo_repository():
    repo = MemoryRepository()
    service = LearningService(repo)
    initialize_dictionary(service, str(uuid4()))
    service.create_route(factory_route(), str(uuid4()))
    examples = [
        ("Python · de la idea a la práctica", "Python", ["Funciones", "Colecciones", "CSV", "Pruebas"], "Programar en Python", 2),
        ("Power BI · análisis con intención", "Power BI", ["Power Query", "Modelo estrella", "Medidas DAX", "Narrativa visual"], "Modelar y comunicar con BI", 1),
        ("Redes · conectar las piezas", "Redes y ciberseguridad", ["Protocolos", "Direccionamiento", "Diagnóstico", "Laboratorio"], "Diagnosticar redes", 0),
    ]
    for idx, (title, area, units, skill, completed) in enumerate(examples):
        result = service.create_track(TrackDraft.model_validate({"title": title, "kind": "course", "area": area,
            "notes": "Ejemplo ficticio del modo demo.", "units": [{"key": f"u{i}", "title": u, "estimated_minutes": 90} for i, u in enumerate(units)],
            "skills": [{"name": skill}], "topics": [{"name": u, "skills": [skill]} for u in units]}), str(uuid4()), status="active", favorite=idx == 0, priority=idx+1)
        tid = result["track_id"]
        for u in domain.track_units(service.data, tid)[:completed]:
            service.toggle_unit(u["id"], True, str(uuid4()))
        track = next(t for t in service.data["learning_tracks"] if t["id"] == tid)
        sid = next(s["id"] for s in service.data["skills"] if s["name"] == skill)
        for days in (1, 2, 4):
            service.record_session(SessionDraft(occurred_on=service.current-timedelta(days=days), duration_minutes=25+idx*10,
                area_id=track["area_id"], track_id=tid, skill_ids=[sid], notes="Sesión ficticia de demostración."), str(uuid4()))
        if completed:
            service.add_learned_topic(units[0], area, service.current-timedelta(days=8 if idx == 0 else 1), "Ejemplo ficticio.", str(uuid4()), [sid])
    return repo
