"""Storage adapters. Authenticated Supabase clients are never globally cached."""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from uuid import uuid4

TABLES = (
    "profiles", "areas", "learning_tracks", "resources", "track_resources", "units", "track_units", "unit_progress",
    "topics", "skills", "resource_topics", "track_topics", "topic_skills", "track_skills", "learning_goals", "goal_phases",
    "phase_tracks", "study_sessions", "session_skills", "topic_events", "learning_evidence", "evidence_skills", "skill_rubrics",
    "skill_assessments", "milestones", "credentials", "import_jobs", "attachments", "daily_plans", "plan_blocks",
)


class RepositoryError(RuntimeError):
    pass


class StaleData(RepositoryError):
    pass


class MemoryRepository:
    """Session-local demonstration. Never used as persistent storage in connected mode."""
    is_demo = True

    def __init__(self, user_id=None):
        self.user_id = user_id or str(uuid4())
        self.data = {table: [] for table in TABLES}
        self.data["profiles"] = [{"id": self.user_id, "user_id": self.user_id, "revision": 0,
                                  "display_name": "Tu espacio de prueba", "timezone": "America/La_Paz", "weekly_minutes": 480, "streak_minutes": 10}]
        self.receipts = {}
        self.files = {}

    def snapshot(self):
        return copy.deepcopy(self.data)

    def commit(self, changes, request_id, expected_revision, intent, result=None, import_approval=None):
        if request_id in self.receipts:
            previous = self.receipts[request_id]
            if previous["intent"] != intent:
                raise RepositoryError("REQUEST_ID_REUSED")
            return copy.deepcopy(previous["answer"])
        if self.data["profiles"][0]["revision"] != expected_revision:
            raise StaleData("Los datos cambiaron. Actualiza y revisa de nuevo antes de guardar.")
        if import_approval:
            job = next((r for r in self.data["import_jobs"] if r["id"] == import_approval["job_id"]), None)
            if not job or job["status"] != "draft" or job["proposal"] != import_approval["proposal"]:
                raise StaleData("La propuesta de importación cambió. Revísala de nuevo.")
        candidate = copy.deepcopy(self.data)
        for change in changes:
            table = change["table"]
            if table not in TABLES:
                raise RepositoryError("INVALID_TABLE")
            if change["op"] == "delete":
                candidate[table] = [r for r in candidate[table] if r["id"] != change["id"]]
            elif change["op"] == "upsert":
                r = copy.deepcopy(change["row"])
                if r.get("user_id", self.user_id) != self.user_id:
                    raise RepositoryError("WRONG_OWNER")
                previous = next((x for x in candidate[table] if x["id"] == r["id"]), {})
                r = {**previous, **r, "user_id": self.user_id, "created_at": previous.get("created_at", datetime.now(timezone.utc).isoformat())}
                if table == "import_jobs" and r.get("status") == "imported" and not import_approval:
                    raise RepositoryError("REVIEW_REQUIRED")
                candidate[table] = [x for x in candidate[table] if x["id"] != r["id"]]+[r]
            else:
                raise RepositoryError("INVALID_OPERATION")
        # Useful invariant in the demo; the real database enforces this independently.
        for session in candidate["study_sessions"]:
            total = sum(a["allocated_minutes"] for a in candidate["session_skills"] if a["session_id"] == session["id"])
            if total > session["duration_minutes"]:
                raise RepositoryError("ALLOCATION_EXCEEDS_SESSION")
        revision = expected_revision+1
        candidate["profiles"][0]["revision"] = revision
        answer = {"revision": revision, "result": result or {}}
        self.data = candidate
        self.receipts[request_id] = {"intent": copy.deepcopy(intent), "answer": copy.deepcopy(answer)}
        return answer

    def upload(self, path, contents, mime):
        if not path.startswith(self.user_id+"/"):
            raise RepositoryError("WRONG_OWNER")
        self.files[path] = bytes(contents)

    def download(self, path):
        return self.files[path]

    def remove_file(self, path):
        if any(a["storage_path"] == path for a in self.data["attachments"]):
            raise RepositoryError("FILE_IN_USE")
        self.files.pop(path, None)


class SupabaseRepository:
    is_demo = False

    def __init__(self, client, user_id):
        self.client = client
        self.user_id = user_id
        self.client.rpc("atlas_bootstrap").execute()

    def snapshot(self):
        return self.client.rpc("atlas_snapshot").execute().data

    def commit(self, changes, request_id, expected_revision, intent, result=None, import_approval=None):
        try:
            return self.client.rpc("atlas_apply", {
                "p_request_id": request_id, "p_expected_revision": expected_revision, "p_intent": intent,
                "p_changes": changes, "p_result": result or {}, "p_import_approval": import_approval,
            }).execute().data
        except Exception as exc:
            if "STALE_REVISION" in str(exc) or "IMPORT_REVIEW_CHANGED" in str(exc):
                raise StaleData("Los datos cambiaron en otra operación. Actualiza y revisa antes de volver a guardar.") from exc
            raise RepositoryError("No se confirmó el guardado. Puedes reintentar la misma operación; no se duplicará.") from exc

    def upload(self, path, contents, mime):
        self.client.storage.from_("learning-documents").upload(path, contents, {"content-type": mime, "upsert": "false"})

    def download(self, path):
        return self.client.storage.from_("learning-documents").download(path)

    def remove_file(self, path):
        self.client.storage.from_("learning-documents").remove([path])


def export_json(data: dict) -> str:
    """An explicit user download; contains personal data but never auth tokens or file bytes."""
    return json.dumps({"format": "learning-atlas-export-v1", "exported_at": datetime.now(timezone.utc).isoformat(), "data": data},
                      ensure_ascii=False, indent=2, default=str)
