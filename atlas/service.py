"""Business actions create a batch, then commit it atomically with optimistic concurrency."""
from __future__ import annotations

import copy
from datetime import date
from uuid import uuid4, uuid5, NAMESPACE_URL
from zoneinfo import ZoneInfo

from . import domain
from .models import ImportProposal, RouteDraft, SessionDraft, TrackDraft, canonical_hash, normalized, safe_url
from .repository import StaleData


def clean(row):
    return {k: v for k, v in row.items() if k not in {"created_at", "user_id", "revision"}}


class Batch:
    def __init__(self, data):
        self.data = copy.deepcopy(data)
        self.changes = []

    def find(self, table, key):
        row = next((r for r in self.data[table] if r["id"] == key), None)
        if not row:
            raise ValueError("El registro ya no está disponible en tu biblioteca.")
        return row

    def put(self, table, row):
        row = clean(row)
        row.setdefault("id", str(uuid4()))
        self.changes.append({"op": "upsert", "table": table, "row": row})
        self.data[table] = [r for r in self.data[table] if r["id"] != row["id"]]+[row]
        return row["id"]

    def remove(self, table, key):
        self.changes.append({"op": "delete", "table": table, "id": key})
        self.data[table] = [r for r in self.data[table] if r["id"] != key]

    def named(self, table, name, **defaults):
        name = " ".join(name.split())
        if not name:
            raise ValueError("El nombre no puede quedar vacío.")
        existing = next((r for r in self.data[table] if normalized(r["name"]) == normalized(name)
                         and (table != "topics" or r["area_id"] == defaults["area_id"])), None)
        return existing["id"] if existing else self.put(table, {"name": name, **defaults})

    def link(self, table, **columns):
        if not any(all(r.get(k) == v for k, v in columns.items()) for r in self.data[table]):
            self.put(table, columns)


class LearningService:
    def __init__(self, repository, snapshot=None):
        self.repo = repository
        self.data = snapshot if snapshot is not None else repository.snapshot()
        self.profile = self.data["profiles"][0]
        self.current = domain.today(self.profile["timezone"])

    def _commit(self, batch, request_id, intent, result=None, approval=None):
        answer = self.repo.commit(batch.changes, request_id, self.profile["revision"], intent, result, approval)
        self.data = self.repo.snapshot()
        self.profile = self.data["profiles"][0]
        return answer["result"]

    def _draft_track(self, b, draft, *, status="planned", favorite=False, priority=3, source_key=None):
        area = b.named("areas", draft.area)
        track = b.put("learning_tracks", {
            **draft.model_dump(mode="json", exclude={"area", "units", "topics", "skills"}), "area_id": area,
            "status": status, "favorite": favorite, "priority": priority, "source_key": source_key,
            "source_type": "manual", "completion_basis": "units",
        })
        resource = b.put("resources", {"title": draft.title, "kind": "document", "url": draft.source_url, "notes": ""})
        b.link("track_resources", track_id=track, resource_id=resource)
        units = {u.key: str(uuid4()) for u in draft.units}
        parents = {u.parent_key for u in draft.units if u.parent_key}
        for i, u in enumerate(draft.units):
            b.put("units", {"id": units[u.key], "resource_id": resource, "parent_id": units.get(u.parent_key),
                            "title": u.title, "estimated_minutes": u.estimated_minutes, "sort_order": i, "archived": False})
        for u in draft.units:
            if u.key not in parents:
                b.put("track_units", {"track_id": track, "resource_id": resource, "unit_id": units[u.key], "required": u.required, "weight": u.weight})
        self._coverage(b, track, area, draft.topics, draft.skills)
        return track, resource

    def _coverage(self, b, track, area, topics, skills):
        skill_ids = {normalized(s.name): b.named("skills", s.name, definition=s.definition, area_id=area) for s in skills}
        for skill in skill_ids.values():
            b.link("track_skills", track_id=track, skill_id=skill)
        for t in topics:
            tid = b.named("topics", t.name, area_id=area, description="", review_enabled=True)
            b.link("track_topics", track_id=track, topic_id=tid)
            for name in t.skills:
                b.link("topic_skills", topic_id=tid, skill_id=skill_ids[normalized(name)])

    def create_track(self, draft: TrackDraft, request_id, *, status="planned", favorite=False, priority=3, source_key=None, phase_id=None):
        if status not in {"planned", "active", "paused"} or priority not in range(1, 6):
            raise ValueError("Estado o prioridad no válidos.")
        if source_key and any(t.get("source_key") == source_key for t in self.data["learning_tracks"]):
            raise ValueError("Este recurso ya está en tu biblioteca.")
        b = Batch(self.data)
        if phase_id:
            phase = b.find("goal_phases", phase_id)
            if b.find("learning_goals", phase["goal_id"])["status"] != "active":
                raise ValueError("Esta ruta está archivada. Usa una versión activa.")
        track, resource = self._draft_track(b, draft, status=status, favorite=favorite, priority=priority, source_key=source_key)
        if phase_id:
            b.link("phase_tracks", phase_id=phase_id, track_id=track)
        return self._commit(b, request_id, {"action": "create_track", "draft": draft.model_dump(mode="json"), "status": status,
                                             "favorite": favorite, "priority": priority, "source_key": source_key, "phase_id": phase_id}, {"track_id": track, "resource_id": resource})

    def update_track(self, track_id, fields, request_id):
        allowed = {"title", "status", "favorite", "priority", "target_on", "notes", "official_name", "platform", "issuer", "code", "source_url", "estimated_minutes"}
        if not set(fields).issubset(allowed):
            raise ValueError("Campo de aprendizaje no editable.")
        b = Batch(self.data)
        t = {**b.find("learning_tracks", track_id), **fields}
        if not t["title"].strip() or t["priority"] not in range(1, 6) or t["status"] not in {"planned", "active", "paused", "completed", "archived"}:
            raise ValueError("Comprueba nombre, estado y prioridad.")
        safe_url(t.get("source_url"))
        if t["status"] == "completed" and domain.progress(self.data, track_id)["percent"] != 100:
            raise ValueError("Completa las unidades antes de marcar el itinerario como completado. Las credenciales se registran aparte.")
        b.put("learning_tracks", t)
        return self._commit(b, request_id, {"action": "update_track", "id": track_id, "fields": fields})

    def toggle_unit(self, unit_id, completed, request_id):
        b = Batch(self.data)
        b.find("units", unit_id)
        if any(u.get("parent_id") == unit_id and not u.get("archived") for u in b.data["units"]):
            raise ValueError("Marca las lecciones, no el módulo padre.")
        records = [r for r in b.data["unit_progress"] if r["unit_id"] == unit_id]
        if completed and not records:
            b.put("unit_progress", {"unit_id": unit_id, "completed_on": self.current.isoformat()})
        elif not completed:
            for r in records:
                b.remove("unit_progress", r["id"])
            tracks = {x["track_id"] for x in b.data["track_units"] if x["unit_id"] == unit_id}
            for t in b.data["learning_tracks"][:]:
                if t["id"] in tracks and t["status"] == "completed":
                    b.put("learning_tracks", {**t, "status": "active"})
        return self._commit(b, request_id, {"action": "toggle_unit", "id": unit_id, "completed": completed})

    def add_unit(self, track_id, title, minutes, request_id, required=True):
        if not title.strip() or minutes is not None and (not isinstance(minutes, int) or minutes < 1):
            raise ValueError("Escribe un título y una estimación positiva o desconocida.")
        b = Batch(self.data)
        t = b.find("learning_tracks", track_id)
        links = [l for l in b.data["track_resources"] if l["track_id"] == track_id]
        resource = links[0]["resource_id"] if links else b.put("resources", {"title": t["title"], "kind": "personal", "notes": "", "url": None})
        b.link("track_resources", track_id=track_id, resource_id=resource)
        unit = b.put("units", {"resource_id": resource, "parent_id": None, "title": title, "estimated_minutes": minutes,
                               "sort_order": len(b.data["units"]), "archived": False})
        b.put("track_units", {"track_id": track_id, "resource_id": resource, "unit_id": unit, "required": required, "weight": 1})
        if t["status"] == "completed":
            b.put("learning_tracks", {**t, "status": "active"})
        return self._commit(b, request_id, {"action": "add_unit", "track": track_id, "title": title, "minutes": minutes, "required": required})

    def set_coverage(self, track_id, topic_names, skill_ids, request_id):
        b = Batch(self.data)
        t = b.find("learning_tracks", track_id)
        for sid in skill_ids:
            b.find("skills", sid)
        for table in ("track_topics", "track_skills"):
            for row in b.data[table][:]:
                if row["track_id"] == track_id:
                    b.remove(table, row["id"])
        for name in dict.fromkeys(n.strip() for n in topic_names if n.strip()):
            tid = b.named("topics", name, area_id=t["area_id"], description="", review_enabled=True)
            b.link("track_topics", track_id=track_id, topic_id=tid)
        for sid in set(skill_ids):
            b.link("track_skills", track_id=track_id, skill_id=sid)
        return self._commit(b, request_id, {"action": "coverage", "track": track_id, "topics": topic_names, "skills": skill_ids})

    def update_unit(self, track_id, unit_id, title, estimated_minutes, required, weight, remove, request_id):
        from .models import UnitDraft
        validated = UnitDraft(key="validated", title=title, estimated_minutes=estimated_minutes, required=required, weight=weight)
        b = Batch(self.data)
        unit = b.find("units", unit_id)
        link = next((r for r in b.data["track_units"] if r["track_id"] == track_id and r["unit_id"] == unit_id), None)
        if not link:
            raise ValueError("Esta unidad ya no pertenece al aprendizaje seleccionado.")
        if remove:
            b.remove("track_units", link["id"])
        else:
            b.put("units", {**unit, "title": validated.title, "estimated_minutes": validated.estimated_minutes})
            b.put("track_units", {**link, "required": validated.required, "weight": validated.weight})
        affected = {r["track_id"] for r in self.data["track_units"] if r["unit_id"] == unit_id}
        for track in b.data["learning_tracks"][:]:
            if track["id"] in affected and track["status"] == "completed" and domain.progress(b.data, track["id"])["percent"] != 100:
                b.put("learning_tracks", {**track, "status": "active"})
        return self._commit(b, request_id, {"action": "update_unit", "track": track_id, "unit": unit_id,
            "title": validated.title, "minutes": validated.estimated_minutes, "required": validated.required, "weight": validated.weight, "remove": remove})

    def add_skill(self, name, definition, area_name, request_id):
        b = Batch(self.data)
        area = b.named("areas", area_name)
        sid = b.named("skills", name, area_id=area, definition=definition)
        return self._commit(b, request_id, {"action": "add_skill", "name": name, "definition": definition, "area": area_name}, {"skill_id": sid})

    def update_skill(self, skill_id, name, definition, area_name, request_id):
        from .models import SkillDraft
        name, area_name = " ".join(name.split()), " ".join(area_name.split())
        if not name or not area_name:
            raise ValueError("Escribe el nombre de la habilidad y su área.")
        if len(area_name) > 180:
            raise ValueError("El nombre del área no puede superar 180 caracteres.")
        draft = SkillDraft(name=name, definition=definition)
        b = Batch(self.data)
        skill = b.find("skills", skill_id)
        if any(s["id"] != skill_id and normalized(s["name"]) == normalized(draft.name) for s in b.data["skills"]):
            raise ValueError("Ya existe otra habilidad con ese nombre. Elige un nombre distinto.")
        area_id = b.named("areas", area_name)
        # Keep the identity and all references; only descriptive fields change.
        b.put("skills", {**skill, "name": draft.name, "definition": draft.definition, "area_id": area_id})
        return self._commit(b, request_id, {"action": "update_skill", "id": skill_id, "name": draft.name,
            "definition": draft.definition, "area": area_name}, {"skill_id": skill_id})

    def add_learned_topic(self, name, area_name, learned_on, notes, request_id, skill_ids=()):
        learned_on = domain.as_date(learned_on)
        if learned_on > self.current:
            raise ValueError("No puedes registrar aprendizaje futuro.")
        b = Batch(self.data)
        area = b.named("areas", area_name)
        tid = b.named("topics", name, area_id=area, description=notes, review_enabled=True)
        for sid in skill_ids:
            b.find("skills", sid)
            b.link("topic_skills", topic_id=tid, skill_id=sid)
        if domain.review_state(b.data, tid, self.current) is None:
            b.put("topic_events", {"topic_id": tid, "session_id": None, "occurred_on": learned_on.isoformat(), "event_type": "learned", "rating": None, "notes": notes, "voided": False})
        return self._commit(b, request_id, {"action": "learned", "name": name, "area": area_name, "date": learned_on.isoformat(), "notes": notes, "skills": list(skill_ids)}, {"topic_id": tid})

    def _session(self, b, draft: SessionDraft, *, session_id=None, area_name=None, timezone=None):
        if draft.occurred_on > self.current:
            raise ValueError("No puedes registrar sesiones futuras.")
        area_id = draft.area_id
        if area_name is not None:
            area_name = " ".join(area_name.split())
            if not area_name or len(area_name) > 180:
                raise ValueError("Escribe un área de entre 1 y 180 caracteres.")
            area_id = b.named("areas", area_name)
        b.find("areas", area_id)
        if draft.track_id:
            b.find("learning_tracks", draft.track_id)
        if draft.phase_id:
            b.find("goal_phases", draft.phase_id)
        for tid in draft.topic_ids:
            b.find("topics", tid)
            review = domain.review_state(b.data, tid, self.current)
            if draft.rating and (not review or draft.occurred_on < review["first"]):
                raise ValueError("Para valorar un repaso, registra primero cuándo aprendiste el tema.")
        for sid in draft.skill_ids:
            b.find("skills", sid)
        block = b.find("plan_blocks", draft.plan_block_id) if draft.plan_block_id else None
        if block and block.get("completed_session_id"):
            raise ValueError("Este bloque ya tiene una sesión registrada.")
        session = b.put("study_sessions", {"id": session_id or str(uuid4()), "area_id": area_id, "track_id": draft.track_id, "phase_id": draft.phase_id,
                       "occurred_on": draft.occurred_on.isoformat(), "timezone_at_entry": timezone or self.profile["timezone"],
                       "duration_minutes": draft.duration_minutes, "activity_type": draft.activity_type, "notes": draft.notes,
                       "voided": False, "void_reason": ""})
        for a in domain.allocate(draft.skill_ids, draft.duration_minutes):
            b.put("session_skills", {"session_id": session, **a})
        for tid in draft.topic_ids:
            b.put("topic_events", {"topic_id": tid, "session_id": session, "occurred_on": draft.occurred_on.isoformat(),
                                   "event_type": draft.activity_type, "rating": draft.rating, "notes": draft.notes, "voided": False})
        if draft.evidence_title:
            evidence = b.put("learning_evidence", {"session_id": session, "track_id": draft.track_id, "title": draft.evidence_title,
                "description": draft.notes, "url": draft.evidence_url, "occurred_on": draft.occurred_on.isoformat(),
                "period_label": "", "source_type": "self_report", "validation_status": "self_checked"})
            for sid in draft.skill_ids:
                b.link("evidence_skills", evidence_id=evidence, skill_id=sid)
        if block:
            b.put("plan_blocks", {**block, "completed_session_id": session})
        return session

    def record_session(self, draft: SessionDraft, request_id, *, area_name=None):
        b = Batch(self.data)
        session = self._session(b, draft, area_name=area_name)
        return self._commit(b, request_id, {"action": "session", "draft": draft.model_dump(mode="json"), "area_name": area_name}, {"session_id": session})

    def update_session(self, session_id, draft: SessionDraft, reason, request_id, *, area_name=None):
        """Replace a session atomically, keeping the original and all external references."""
        if not reason.strip():
            raise ValueError("Indica brevemente qué estás corrigiendo.")
        if draft.plan_block_id or draft.evidence_title or draft.evidence_url:
            raise ValueError("La edición conserva el bloque y los trabajos originales; no crea otros.")
        b = Batch(self.data)
        old = b.find("study_sessions", session_id)
        replacement = str(uuid5(NAMESPACE_URL, "learning-atlas/session-correction/"+str(request_id)))
        marker = f"Corregida por sesión {replacement}: {reason.strip()}"
        intent = {"action": "update_session", "id": session_id, "draft": draft.model_dump(mode="json"),
                  "reason": reason, "area_name": area_name}
        if old.get("voided"):
            if old.get("void_reason") == marker and any(s["id"] == replacement for s in b.data["study_sessions"]):
                # The repository checks the original intent before replaying its receipt.
                return self._commit(b, request_id, intent)
            raise ValueError("Esta sesión ya fue anulada o corregida. Abre su registro vigente.")
        b.put("study_sessions", {**old, "voided": True, "void_reason": marker})
        for event in b.data["topic_events"][:]:
            if event.get("session_id") == session_id:
                b.put("topic_events", {**event, "voided": True})
        self._session(b, draft, session_id=replacement, area_name=area_name, timezone=old["timezone_at_entry"])
        for evidence in b.data["learning_evidence"][:]:
            if evidence.get("session_id") == session_id:
                b.put("learning_evidence", {**evidence, "session_id": replacement, "track_id": draft.track_id,
                                           "occurred_on": draft.occurred_on.isoformat()})
        for block in b.data["plan_blocks"][:]:
            if block.get("completed_session_id") == session_id:
                b.put("plan_blocks", {**block, "completed_session_id": replacement})
        return self._commit(b, request_id, intent, {"session_id": replacement, "replaced_session_id": session_id})

    def void_session(self, session_id, reason, request_id):
        if not reason.strip():
            raise ValueError("Indica el motivo de la corrección.")
        b = Batch(self.data)
        s = b.find("study_sessions", session_id)
        b.put("study_sessions", {**s, "voided": True, "void_reason": reason})
        for e in b.data["topic_events"][:]:
            if e.get("session_id") == session_id:
                b.put("topic_events", {**e, "voided": True})
        for block in b.data["plan_blocks"][:]:
            if block.get("completed_session_id") == session_id:
                b.put("plan_blocks", {**block, "completed_session_id": None})
        return self._commit(b, request_id, {"action": "void", "id": session_id, "reason": reason})

    def assess(self, skill_id, occurred_on, level, context, url, request_id):
        d = domain.as_date(occurred_on)
        if d > self.current or level not in range(4) or not context.strip():
            raise ValueError("Comprueba fecha, nivel y descripción de la tarea.")
        safe_url(url)
        b = Batch(self.data)
        b.find("skills", skill_id)
        rubric = next((r for r in b.data["skill_rubrics"] if r["code"] == "autonomia" and r["version"] == 1), None)
        rid = rubric["id"] if rubric else b.put("skill_rubrics", {"code": "autonomia", "version": 1, "description": "0 Todavía no puedo; 1 Con guía; 2 Por mi cuenta; 3 Explico y compruebo"})
        if any(a["skill_id"] == skill_id and a["rubric_id"] == rid and a["occurred_on"] == d.isoformat() for a in b.data["skill_assessments"]):
            raise ValueError("Ya existe una autoevaluación de esta habilidad en esa fecha.")
        b.put("skill_assessments", {"skill_id": skill_id, "rubric_id": rid, "occurred_on": d.isoformat(), "level": level,
                                  "method": "self", "context": context, "evidence_url": url or None, "voided": False})
        return self._commit(b, request_id, {"action": "assess", "skill": skill_id, "date": d.isoformat(), "level": level, "context": context, "url": url})

    def _route(self, b, draft: RouteDraft, supersedes=None):
        phases = sorted(draft.phases, key=lambda p: p.starts_on)
        version = 1
        if supersedes:
            old = b.find("learning_goals", supersedes)
            version = old["version"]+1
            b.put("learning_goals", {**old, "status": "archived"})
        gid = b.put("learning_goals", {"title": draft.title, "outcome": draft.outcome, "weekly_minutes": draft.weekly_minutes,
                    "starts_on": phases[0].starts_on.isoformat(), "target_on": phases[-1].ends_on.isoformat(), "version": version,
                    "supersedes_id": supersedes, "status": "active"})
        for i, p in enumerate(phases):
            pid = b.put("goal_phases", {"goal_id": gid, "title": p.title, "starts_on": p.starts_on.isoformat(),
                "ends_on": p.ends_on.isoformat(), "budget_minutes": p.budget_minutes, "sort_order": i, "topics": p.topics, "is_buffer": p.is_buffer})
            b.put("milestones", {"phase_id": pid, "title": p.milestone, "criteria": p.criteria, "accepted_on": None, "evidence_id": None, "notes": ""})
        return gid

    def create_route(self, draft: RouteDraft, request_id, supersedes=None):
        b = Batch(self.data)
        gid = self._route(b, draft, supersedes)
        return self._commit(b, request_id, {"action": "route", "draft": draft.model_dump(mode="json"), "supersedes": supersedes}, {"goal_id": gid})

    def accept_milestone(self, milestone_id, accepted, notes, evidence_id, request_id):
        b = Batch(self.data)
        m = b.find("milestones", milestone_id)
        if evidence_id:
            b.find("learning_evidence", evidence_id)
        b.put("milestones", {**m, "accepted_on": (m.get("accepted_on") or self.current.isoformat()) if accepted else None, "notes": notes, "evidence_id": evidence_id})
        return self._commit(b, request_id, {"action": "milestone", "id": milestone_id, "accepted": accepted, "notes": notes, "evidence": evidence_id})

    def save_plan(self, budget, energy, request_id):
        blocks = domain.make_plan(self.data, self.current, budget, energy)
        if not blocks:
            raise ValueError("Todavía no hay tareas disponibles. En Dashboard → My Learning, abre un aprendizaje, cambia su estado a En curso y añade al menos una lección pendiente. Los temas de Garden of Knowledge también se incluyen cuando llega su fecha de repaso.")
        b = Batch(self.data)
        pid = b.put("daily_plans", {"plan_date": self.current.isoformat(), "budget_minutes": budget, "energy": energy, "generator": "rules"})
        for block in blocks:
            b.put("plan_blocks", {"plan_id": pid, **block, "completed_session_id": None})
        return self._commit(b, request_id, {"action": "plan", "budget": budget, "energy": energy, "date": self.current.isoformat()}, {"plan_id": pid})

    def add_credential(self, fields, request_id, credential_id=None):
        b = Batch(self.data)
        if credential_id:
            b.find("credentials", credential_id)
        if not fields.get("official_name", "").strip() or not fields.get("issuer", "").strip():
            raise ValueError("Indica el nombre de la credencial y su emisor.")
        if fields.get("track_id"):
            b.find("learning_tracks", fields["track_id"])
        earned, expires = fields.get("earned_on"), fields.get("expires_on")
        if earned and domain.as_date(earned) > self.current:
            raise ValueError("No puedes registrar como obtenida una credencial futura.")
        if earned and expires and domain.as_date(expires) < domain.as_date(earned):
            raise ValueError("La caducidad no puede ser anterior a la obtención.")
        if fields.get("never_expires") and expires:
            raise ValueError("Elige fecha de vencimiento o sin caducidad, no ambas.")
        safe_url(fields.get("verification_url"))
        safe_url(fields.get('document_url'))
        for name,limit in [('program_code',100),('credential_code',200)]:
            if len(fields.get(name,''))>limit:
                raise ValueError('El código indicado es demasiado largo.')
        if not credential_id:
            fields={k:v for k,v in fields.items() if k not in {'program_code','credential_code','document_url'} or v}
        if fields.get("credential_type") not in {"professional", "course", "program", "badge"}:
            raise ValueError("Elige un tipo de credencial válido.")
        b.put("credentials", {**fields, **({"id": credential_id} if credential_id else {}), "verification_status": "self_reported"})
        return self._commit(b, request_id, {"action": "credential", "id": credential_id, "fields": fields})

    def link_phase(self, phase_id, track_ids, request_id):
        b=Batch(self.data)
        phase=b.find('goal_phases',phase_id)
        if b.find('learning_goals',phase['goal_id'])['status']!='active':
            raise ValueError('Esta ruta está archivada. Usa una versión activa.')
        for tid in track_ids:
            b.find('learning_tracks',tid)
        for row in list(b.data['phase_tracks']):
            if row['phase_id']==phase_id and row['track_id'] not in track_ids:
                b.remove('phase_tracks',row['id'])
        for tid in set(track_ids):
            b.link('phase_tracks',phase_id=phase_id,track_id=tid)
        return self._commit(b,request_id,{'action':'link_phase','phase':phase_id,'tracks':sorted(set(track_ids))})

    def settings(self, display_name, timezone, weekly_minutes, streak_minutes, request_id):
        ZoneInfo(timezone)
        if not 10 <= weekly_minutes <= 10080 or not 1 <= streak_minutes <= 1440:
            raise ValueError("Comprueba disponibilidad y umbral de racha.")
        b = Batch(self.data)
        b.put("profiles", {**self.profile, "display_name": display_name, "timezone": timezone, "weekly_minutes": weekly_minutes, "streak_minutes": streak_minutes})
        return self._commit(b, request_id, {"action": "settings", "name": display_name, "timezone": timezone, "weekly": weekly_minutes, "streak": streak_minutes})

    def stage_import(self, proposal: ImportProposal, file_info: dict, request_id, job_id=None):
        b = Batch(self.data)
        if job_id and b.find("import_jobs", job_id)["status"] != "draft":
            raise ValueError("Esta importación ya no puede editarse.")
        payload = proposal.model_dump(mode="json")
        jid = b.put("import_jobs", {"id": job_id or str(uuid4()), **file_info, "proposal": payload,
                   "proposal_hash": canonical_hash(payload), "status": "draft", "result": None})
        return self._commit(b, request_id, {"action": "stage_import", "job": job_id, "file": file_info, "proposal": payload}, {"job_id": jid})

    def apply_import(self, job_id, expected_hash, request_id, *, target_track_id=None, accepted=False):
        if not accepted:
            raise ValueError("Revisa y aprueba la propuesta antes de importarla.")
        b = Batch(self.data)
        job = b.find("import_jobs", job_id)
        intent = {"action": "apply_import", "job_id": job_id, "hash": expected_hash, "target": target_track_id}
        if job["status"] == "imported":
            return job["result"]  # Already committed; no writes on retry, even after a browser reconnect.
        if job["status"] != "draft" or job["proposal_hash"] != expected_hash or canonical_hash(job["proposal"]) != expected_hash:
            raise StaleData("La propuesta cambió. Vuelve a validarla y revisarla.")
        proposal = ImportProposal.model_validate(job["proposal"])
        if target_track_id and (len(proposal.tracks) != 1 or proposal.route or proposal.evidence):
            raise ValueError("Para añadir material a un aprendizaje existente, usa una propuesta de un solo aprendizaje.")
        if target_track_id:
            b.find("learning_tracks", target_track_id)
        created_tracks = []
        resources = []
        for draft in proposal.tracks:
            track, resource = self._draft_track(b, draft)
            for change in b.changes:
                if change["table"] == "learning_tracks" and change.get("row", {}).get("id") == track:
                    change["row"]["source_type"] = "reviewed_import"
            if target_track_id:
                # Retarget the newly created material; preserve the existing track's name, state and completed units.
                for c in b.changes:
                    if c["table"] in {"track_resources", "track_units", "track_topics", "track_skills"} and c.get("row", {}).get("track_id") == track:
                        c["row"]["track_id"] = target_track_id
                b.changes = [c for c in b.changes if not (c["table"] == "learning_tracks" and c.get("row", {}).get("id") == track)]
                # A reused coverage relation must not be inserted a second time.
                for table, field in (("track_topics", "topic_id"), ("track_skills", "skill_id")):
                    existing = {r[field] for r in self.data[table] if r["track_id"] == target_track_id}
                    b.changes = [c for c in b.changes if not(c["table"] == table and c.get("row", {}).get("track_id") == target_track_id and c["row"][field] in existing)]
                track = target_track_id
                old = b.find("learning_tracks", target_track_id)
                if old["status"] == "completed" and draft.units:
                    b.put("learning_tracks", {**old, "status": "active"})
            created_tracks.append(track)
            resources.append(resource)
            # Explicit content coverage, not an event claiming the topic was learned.
            for topic in draft.topics:
                area = b.named("areas", draft.area)
                tid = b.named("topics", topic.name, area_id=area, description="", review_enabled=True)
                b.link("resource_topics", resource_id=resource, topic_id=tid, origin="reviewed_import")
        goal_id = self._route(b, proposal.route) if proposal.route else None
        evidence_ids = []
        for ev in proposal.evidence:
            if ev.occurred_on and ev.occurred_on > self.current:
                raise ValueError("Una evidencia realizada no puede tener fecha futura.")
            eid = b.put("learning_evidence", {**ev.model_dump(mode="json", exclude={"skills"}), "session_id": None,
                        "track_id": None, "source_type": "imported", "validation_status": "unreviewed"})
            evidence_ids.append(eid)
            area = b.named("areas", "General")
            for name in ev.skills:
                sid = b.named("skills", name, area_id=area, definition="")
                b.link("evidence_skills", evidence_id=eid, skill_id=sid)
        if job.get("storage_path"):
            destinations = [("resource_id", rid) for rid in resources]+[("evidence_id", eid) for eid in evidence_ids]
            if not destinations:  # A route document remains an accessible reference resource.
                rid = b.put("resources", {"title": proposal.route.title, "kind": "document", "url": None, "notes": "Documento de referencia de ruta"})
                destinations = [("resource_id", rid)]
            file_size = self._file_size(job)
            for field, rid in destinations:
                b.put("attachments", {"resource_id": None, "credential_id": None, "evidence_id": None, field: rid,
                      "import_job_id": job_id, "storage_path": job["storage_path"], "original_name": job["filename"],
                      "mime_type": job["mime_type"], "size_bytes": file_size, "sha256": job["sha256"]})
        result = {"track_ids": created_tracks, "goal_id": goal_id, "evidence_ids": evidence_ids}
        b.put("import_jobs", {**job, "status": "imported", "result": result})
        return self._commit(b, request_id, intent, result, {"job_id": job_id, "proposal": job["proposal"]})

    def _file_size(self, job):
        # Verify the uploaded file remains readable before committing references.
        return len(self.repo.download(job["storage_path"]))

    def cancel_import(self, job_id, request_id):
        b = Batch(self.data)
        job = b.find("import_jobs", job_id)
        if job["status"] == "imported":
            raise ValueError("No puedes cancelar una importación que ya se guardó.")
        b.put("import_jobs", {**job, "status": "cancelled"})
        self._commit(b, request_id, {"action": "cancel_import", "id": job_id})
        if job.get("storage_path"):
            try:
                self.repo.remove_file(job["storage_path"])
            except Exception:
                return {"cleanup_pending": True}
        return {"cleanup_pending": False}
