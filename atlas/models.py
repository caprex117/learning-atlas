"""Validated input contracts. Model output is data, never a database command."""
from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Name = Annotated[str, Field(min_length=1, max_length=180)]
Minutes = Annotated[int, Field(ge=1, le=600_000, strict=True)]
Kind = Literal["certification", "course", "topic", "paper", "project", "lab", "pack"]


def safe_url(value: str | None) -> str | None:
    if not value:
        return None
    u = urlparse(value.strip())
    if u.scheme not in {"https", "http"} or not u.netloc or u.username or u.password:
        raise ValueError("Usa un enlace http/https sin credenciales.")
    return value.strip()


def canonical_hash(value: dict) -> str:
    # PostgreSQL JSONB and JS transports may return 1.0 as 1. They mean the same
    # thing in a proposal, and must not invalidate an otherwise unchanged review.
    def canonical(item):
        if isinstance(item, dict):
            return {k: canonical(v) for k, v in item.items()}
        if isinstance(item, list):
            return [canonical(v) for v in item]
        if isinstance(item, float) and item.is_integer():
            return int(item)
        return item
    return hashlib.sha256(json.dumps(canonical(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def normalized(value: str) -> str:
    return " ".join(value.casefold().split())


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)


class SkillDraft(StrictModel):
    name: Name
    definition: Annotated[str, Field(max_length=700)] = ""


class TopicDraft(StrictModel):
    name: Name
    skills: list[Name] = Field(default_factory=list, max_length=20)


class UnitDraft(StrictModel):
    key: Annotated[str, Field(min_length=1, max_length=60, pattern=r"^[a-zA-Z0-9_-]+$")]
    title: Name
    parent_key: str | None = None
    estimated_minutes: Minutes | None = None
    required: bool = True
    weight: Annotated[float, Field(gt=0, le=100)] = 1.0


class TrackDraft(StrictModel):
    title: Name
    kind: Kind = "topic"
    area: Name = "General"
    official_name: Annotated[str, Field(max_length=240)] = ""
    platform: Annotated[str, Field(max_length=180)] = ""
    issuer: Annotated[str, Field(max_length=180)] = ""
    code: Annotated[str, Field(max_length=60)] = ""
    source_url: str | None = None
    target_on: date | None = None
    estimated_minutes: Minutes | None = None
    notes: Annotated[str, Field(max_length=5000)] = ""
    units: list[UnitDraft] = Field(default_factory=list, max_length=150)
    topics: list[TopicDraft] = Field(default_factory=list, max_length=80)
    skills: list[SkillDraft] = Field(default_factory=list, max_length=40)

    _url = field_validator("source_url")(safe_url)

    @model_validator(mode="after")
    def relationships(self):
        by_key = {u.key: u for u in self.units}
        if len(by_key) != len(self.units):
            raise ValueError("Cada unidad necesita una clave distinta.")
        for unit in self.units:
            path = {unit.key}
            parent = unit.parent_key
            while parent:
                if parent not in by_key:
                    raise ValueError(f"La unidad {unit.key} tiene un padre inexistente.")
                if parent in path:
                    raise ValueError("El temario contiene un ciclo.")
                path.add(parent)
                parent = by_key[parent].parent_key
        names = [normalized(s.name) for s in self.skills]
        if len(names) != len(set(names)):
            raise ValueError("Hay habilidades repetidas en la propuesta.")
        topic_names = [normalized(t.name) for t in self.topics]
        if len(topic_names) != len(set(topic_names)):
            raise ValueError("Hay temas repetidos en la propuesta.")
        for topic in self.topics:
            if not {normalized(s) for s in topic.skills}.issubset(names):
                raise ValueError(f"El tema {topic.name} apunta a una habilidad no definida.")
        return self


class PhaseDraft(StrictModel):
    title: Name
    starts_on: date
    ends_on: date
    budget_minutes: Minutes
    milestone: Name
    criteria: Annotated[str, Field(min_length=1, max_length=3000)]
    topics: Annotated[str, Field(max_length=2000)] = ""
    is_buffer: bool = False

    @model_validator(mode="after")
    def dates(self):
        if self.ends_on < self.starts_on:
            raise ValueError("Una fase termina antes de empezar.")
        return self


class RouteDraft(StrictModel):
    title: Name
    outcome: Annotated[str, Field(max_length=2000)] = ""
    weekly_minutes: Annotated[int, Field(ge=10, le=10080, strict=True)] = 480
    phases: list[PhaseDraft] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def sequence(self):
        ordered = sorted(self.phases, key=lambda p: p.starts_on)
        if any(a.ends_on >= b.starts_on for a, b in zip(ordered, ordered[1:])):
            raise ValueError("Las fases de esta ruta deben ser consecutivas, sin solaparse.")
        return self


class EvidenceDraft(StrictModel):
    title: Name
    description: Annotated[str, Field(max_length=3000)] = ""
    url: str | None = None
    occurred_on: date | None = None
    period_label: Annotated[str, Field(max_length=100)] = ""
    skills: list[Name] = Field(default_factory=list, max_length=20)
    _url = field_validator("url")(safe_url)


class ImportProposal(StrictModel):
    schema_version: Literal[1] = 1
    tracks: list[TrackDraft] = Field(default_factory=list, max_length=8)
    route: RouteDraft | None = None
    evidence: list[EvidenceDraft] = Field(default_factory=list, max_length=20)
    warnings: list[Annotated[str, Field(max_length=700)]] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def has_content(self):
        if not self.tracks and not self.route and not self.evidence:
            raise ValueError("La propuesta no contiene aprendizajes, ruta ni evidencia.")
        if sum(len(t.units) for t in self.tracks) > 300:
            raise ValueError("Divide el documento: máximo 300 unidades por importación.")
        return self


class SessionDraft(StrictModel):
    occurred_on: date
    duration_minutes: Annotated[int, Field(ge=1, le=1440, strict=True)]
    activity_type: Literal["study", "review", "work_practice"] = "study"
    area_id: str
    track_id: str | None = None
    phase_id: str | None = None
    topic_ids: list[str] = Field(default_factory=list, max_length=30)
    skill_ids: list[str] = Field(default_factory=list, max_length=30)
    rating: Literal["again", "hard", "good", "easy"] | None = None
    notes: Annotated[str, Field(max_length=3000)] = ""
    evidence_title: Annotated[str, Field(max_length=180)] = ""
    evidence_url: str | None = None
    plan_block_id: str | None = None
    _url = field_validator("evidence_url")(safe_url)

    @model_validator(mode="after")
    def check_fields(self):
        if len(self.skill_ids) != len(set(self.skill_ids)) or len(self.topic_ids) != len(set(self.topic_ids)):
            raise ValueError("No repitas habilidades o temas en una sesión.")
        if len(self.skill_ids) > self.duration_minutes:
            raise ValueError("Asigna al menos un minuto a cada habilidad seleccionada.")
        if self.rating and (not self.topic_ids or self.activity_type == "study"):
            raise ValueError("La valoración requiere temas y actividad de repaso o práctica laboral.")
        if self.evidence_url and not self.evidence_title:
            raise ValueError("Escribe el nombre de la evidencia enlazada.")
        return self
