"""Pure calculations shared by the UI and acceptance tests (C01–C14)."""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


def today(timezone: str = "America/La_Paz") -> date:
    return datetime.now(ZoneInfo(timezone)).date()


def as_date(value) -> date:
    return value if isinstance(value, date) else date.fromisoformat(value)


def by_id(rows: list[dict]) -> dict[str, dict]:
    return {r["id"]: r for r in rows}


def active_sessions(data: dict) -> list[dict]:
    return [s for s in data.get("study_sessions", []) if not s.get("voided")]


def session_phases(data: dict, current: date, *, show_finished=False, keep_id=None) -> list[dict]:
    """Hide old finished phases and archived routes, without deleting their history."""
    goals = by_id(data["learning_goals"])
    rows = []
    for phase in data["goal_phases"]:
        goal = goals[phase["goal_id"]]
        milestones = [m for m in data["milestones"] if m["phase_id"] == phase["id"]]
        finished = bool(milestones) and all(m.get("accepted_on") for m in milestones)
        recent = finished and max(as_date(m["accepted_on"]) for m in milestones) >= current-timedelta(days=1)
        if not (show_finished or phase["id"] == keep_id or goal["status"] == "active" and (not finished or recent)):
            continue
        status = "archivada" if goal["status"] != "active" else "finalizada" if finished else "pendiente"
        rows.append({**phase, "label": f"{phase['title']} · {goal['title']} · v{goal['version']} · {status}"})
    return sorted(rows, key=lambda p: (goals[p["goal_id"]]["status"] != "active", goals[p["goal_id"]]["title"],
                                     -goals[p["goal_id"]]["version"], p["sort_order"]))


def track_units(data: dict, track_id: str) -> list[dict]:
    units = by_id(data.get("units", []))
    parents = {u.get("parent_id") for u in units.values() if not u.get("archived")}
    result = []
    for link in data.get("track_units", []):
        u = units.get(link["unit_id"])
        if link["track_id"] == track_id and u and not u.get("archived") and u["id"] not in parents:
            result.append({**u, "required": link.get("required", True), "weight": float(link.get("weight", 1))})
    return sorted(result, key=lambda u: (u.get("sort_order", 0), u["title"]))


def progress(data: dict, track_id: str) -> dict:
    units = [u for u in track_units(data, track_id) if u["required"]]
    completed = {p["unit_id"] for p in data.get("unit_progress", [])}
    denominator = sum(u["weight"] for u in units)
    numerator = sum(u["weight"] for u in units if u["id"] in completed)
    return {"total": len(units), "done": sum(u["id"] in completed for u in units),
            "percent": math.floor(numerator/denominator*100+0.5) if denominator else None,
            "weight_done": numerator, "weight_total": denominator}


def estimate(data: dict, track: dict) -> dict:
    units = [u for u in track_units(data, track["id"]) if u["required"]]
    done = {p["unit_id"] for p in data.get("unit_progress", [])}
    pending = [u for u in units if u["id"] not in done]
    return {"total": sum(u.get("estimated_minutes") or 0 for u in units) if units else track.get("estimated_minutes"),
            "total_missing": sum(u.get("estimated_minutes") is None for u in units),
            "remaining": sum(u.get("estimated_minutes") or 0 for u in pending) if units else None,
            "missing": sum(u.get("estimated_minutes") is None for u in pending)}


def effort(data: dict, track_id: str | None = None) -> int:
    return sum(s["duration_minutes"] for s in active_sessions(data) if track_id is None or s.get("track_id") == track_id)


def daily_minutes(data: dict) -> dict[date, int]:
    result = defaultdict(int)
    for s in active_sessions(data):
        result[as_date(s["occurred_on"])] += s["duration_minutes"]
    return dict(result)


def streak(data: dict, current: date, threshold: int = 10) -> dict:
    daily = daily_minutes(data)
    cursor = current if daily.get(current, 0) >= threshold else current-timedelta(days=1)
    count = 0
    while daily.get(cursor, 0) >= threshold:
        count += 1
        cursor -= timedelta(days=1)
    longest = run = 0
    previous = None
    for d in sorted(d for d, minutes in daily.items() if minutes >= threshold and d <= current):
        run = run+1 if previous and d == previous+timedelta(days=1) else 1
        longest = max(longest, run)
        previous = d
    return {"current": count, "longest": longest}


def review_state(data: dict, topic_id: str, current: date) -> dict | None:
    voided_sessions = {s["id"] for s in data.get("study_sessions", []) if s.get("voided")}
    events = sorted((e for e in data.get("topic_events", []) if e["topic_id"] == topic_id
                     and not e.get("voided") and e.get("session_id") not in voided_sessions),
                    key=lambda e: (e["occurred_on"], e.get("created_at", ""), e["id"]))
    learned = [e for e in events if e["event_type"] == "learned"]
    if not learned:
        return None
    first = as_date(learned[0]["occurred_on"])
    anchor = first
    interval = 3
    rated_days = set()
    practices = [first]
    for e in events:
        d = as_date(e["occurred_on"])
        if d < first or d > current:
            continue
        practices.append(d)
        rating = e.get("rating")
        if rating and d not in rated_days and e["event_type"] in {"review", "work_practice"}:
            interval = 1 if rating == "again" else max(1, math.floor(interval*.7+.5)) if rating == "hard" else min(180, interval*(3 if rating == "easy" else 2))
            rated_days.add(d)
            anchor = d
    ratio = max(0, (current-anchor).days/interval)
    stage = "recent" if ratio < .75 else "soon" if ratio <= 1 else "due"
    return {"first": first, "last_practice": max(practices), "anchor": anchor, "interval": interval,
            "next": anchor+timedelta(days=interval), "ratio": ratio, "stage": stage, "reviews": len(rated_days)}


def allocate(skill_ids: list[str], minutes: int) -> list[dict]:
    ids = list(dict.fromkeys(skill_ids))
    if not ids:
        return []
    if minutes < len(ids):
        raise ValueError("No hay suficientes minutos para el reparto.")
    whole, remainder = divmod(minutes, len(ids))
    return [{"skill_id": key, "allocated_minutes": whole+(i < remainder)} for i, key in enumerate(ids)]


def skill_coverage(data: dict, skill_id: str) -> set[str]:
    result = {l["track_id"] for l in data.get("track_skills", []) if l["skill_id"] == skill_id}
    topics = {l["topic_id"] for l in data.get("topic_skills", []) if l["skill_id"] == skill_id}
    result |= {l["track_id"] for l in data.get("track_topics", []) if l["topic_id"] in topics}
    resources = {l["resource_id"] for l in data.get("resource_topics", []) if l["topic_id"] in topics}
    result |= {l["track_id"] for l in data.get("track_resources", []) if l["resource_id"] in resources}
    live = {t["id"] for t in data.get("learning_tracks", []) if t.get("status") != "archived"}
    return result & live


def skill_stats(data: dict, skill_id: str, start: date | None = None, end: date | None = None) -> dict:
    sessions = {s["id"]: s for s in active_sessions(data)
                if (start is None or as_date(s["occurred_on"]) >= start) and (end is None or as_date(s["occurred_on"]) <= end)}
    allocations = [a for a in data.get("session_skills", []) if a["skill_id"] == skill_id and a["session_id"] in sessions]
    evidence_ids = {e["evidence_id"] for e in data.get("evidence_skills", []) if e["skill_id"] == skill_id}
    evidence = [e for e in data.get("learning_evidence", []) if e["id"] in evidence_ids
                and (not e.get("session_id") or e["session_id"] in sessions)]
    return {"track_ids": skill_coverage(data, skill_id), "minutes": sum(a["allocated_minutes"] for a in allocations),
            "sessions": len({a["session_id"] for a in allocations}), "evidence": evidence}


def evolution(data: dict, skill_id: str, rubric_id: str) -> dict:
    rows = sorted((a for a in data.get("skill_assessments", []) if a["skill_id"] == skill_id
                   and a["rubric_id"] == rubric_id and a.get("method", "self") == "self" and not a.get("voided")),
                  key=lambda a: a["occurred_on"])
    comparable = len(rows) >= 2 and rows[0]["occurred_on"] != rows[-1]["occurred_on"]
    return {"rows": rows, "comparable": comparable, "first": rows[0] if rows else None, "last": rows[-1] if rows else None}


def make_plan(data: dict, current: date, budget: int, energy: str) -> list[dict]:
    if budget not in {20, 30, 45, 60, 90, 120} or energy not in {"low", "medium", "high"}:
        raise ValueError("Elige un presupuesto y nivel de energía válidos.")
    completed = {p["unit_id"] for p in data.get("unit_progress", [])}
    sessions = active_sessions(data)
    active = [t for t in data.get("learning_tracks", []) if t.get("status") == "active"
              and any(u["id"] not in completed for u in track_units(data, t["id"]))]
    active.sort(key=lambda t: (t.get("priority", 3), max((s["occurred_on"] for s in sessions if s.get("track_id") == t["id"]), default="0000"), t["id"]))
    candidates = []
    for t in active:
        u = next(u for u in track_units(data, t["id"]) if u["id"] not in completed)
        candidates.append({"track_id": t["id"], "topic_id": None, "title": u["title"], "reason": "Continúa tu siguiente unidad pendiente."})
    due = [(t, review_state(data, t["id"], current)) for t in data.get("topics", []) if t.get("review_enabled", True)]
    due = sorted(((t, r) for t, r in due if r and r["stage"] == "due"), key=lambda x: -x[1]["ratio"])
    if due:
        t, r = due[0]
        candidates.insert(min(1, len(candidates)), {"track_id": None, "topic_id": t["id"], "title": "Repasar "+t["name"], "reason": "Pasó su fecha orientativa de repaso; tú decides."})
    limit = 1 if budget < 25 else 2 if energy == "low" or budget < 45 else 3
    candidates = candidates[:limit]
    if not candidates:
        return []
    available = budget-5*(len(candidates)-1)
    base, remainder = divmod(available, len(candidates))
    return [{**c, "planned_minutes": min(40, base+(i < remainder)), "sort_order": i} for i, c in enumerate(candidates)]


def credential_status(c: dict, current: date) -> str:
    if c.get("never_expires"):
        return "Sin caducidad declarada"
    if not c.get("expires_on"):
        return "Vigencia por confirmar"
    return "Vencida" if as_date(c["expires_on"]) < current else "Vigente según fecha registrada"
