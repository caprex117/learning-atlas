from __future__ import annotations

from datetime import date, timedelta
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from . import domain
from .auth import configuration, get_repository, logout
from .importing import extract_document, file_metadata, propose_with_gemini
from .models import ImportProposal, RouteDraft, SessionDraft, TrackDraft, canonical_hash
from .repository import RepositoryError, StaleData, export_json
from .seed import factory_route, initialize_dictionary, read_data
from .service import Batch, LearningService
from .ui import ACTIVITY, CSS, ENERGY, KIND, RATING, STATUS, e, heading, hero, metrics, minutes, pills

NAV = ["Mi panorama", "Mi ruta", "Mi aprendizaje", "Habilidades", "Lo aprendido", "Actividad", "Descubrir", "Mi día libre", "Importar documentos", "Credenciales", "Mi espacio"]


def action(key, callback, message="Guardado en tu espacio."):
    request_key = "request_" + key
    request_id = st.session_state.setdefault(request_key, str(uuid4()))
    try:
        result = callback(request_id)
    except StaleData as exc:
        st.session_state.pop(request_key, None)
        st.error(str(exc))
        st.button("Actualizar datos", key="refresh_" + key, on_click=lambda: None)
        return None
    except (ValueError, RepositoryError) as exc:
        st.error(str(exc))
        return None
    except Exception:
        st.error("No se pudo confirmar la operación. Conserva los datos y vuelve a intentarlo; revisa tu conexión si persiste.")
        return None
    st.session_state.pop(request_key, None)
    st.session_state.flash = message
    return {"ok": True, "result": result}


def save_and_refresh(key, callback, message="Guardado en tu espacio."):
    if action(key, callback, message):
        st.session_state.pop("active_dialog", None)
        st.rerun()


def open_dialog(kind, **kwargs):
    st.session_state.active_dialog = {"kind": kind, "kwargs": kwargs}


def dismiss_dialog():
    st.session_state.pop("active_dialog", None)


def select_record(label, rows, *, field="name", optional=False, key=None, default=None):
    mapping = domain.by_id(rows)
    values = ([None] if optional else []) + list(mapping)
    return st.selectbox(label, values, format_func=lambda v: "Sin asociar" if v is None else mapping[v][field],
                        index=values.index(default) if default in values else 0, key=key)


def multi_records(label, rows, *, field="name", default=None, key=None):
    mapping = domain.by_id(rows)
    return st.multiselect(label, list(mapping), default=[v for v in default or [] if v in mapping],
                          format_func=lambda v: mapping[v][field], key=key)


def new_track_fields(prefix="new"):
    title = st.text_input("Nombre del aprendizaje", key=prefix+"title", max_chars=180)
    a, b = st.columns(2)
    kind = a.selectbox("Tipo", list(KIND), format_func=KIND.get, key=prefix+"kind")
    area = b.text_input("Área temática", "General", key=prefix+"area")
    official = st.text_input("Nombre oficial (si es diferente)", key=prefix+"official")
    a, b = st.columns(2)
    platform = a.text_input("Plataforma", key=prefix+"platform")
    issuer = b.text_input("Emisor / institución", key=prefix+"issuer")
    url = st.text_input("Enlace de referencia", key=prefix+"url")
    lessons = st.text_area("Lecciones o unidades · una por línea", key=prefix+"units", height=100,
                           help="Sin unidades, el progreso aparecerá como ‘Sin definir’. Unidades con el mismo peso; puedes importar módulos y pesos mediante JSON.")
    topics = st.text_input("Temas cubiertos · separados por comas", key=prefix+"topics")
    notes = st.text_area("Notas", key=prefix+"notes", height=80)
    return dict(title=title, kind=kind, area=area, official_name=official, platform=platform, issuer=issuer,
                source_url=url or None, notes=notes,
                units=[{"key": f"u{i}", "title": line.strip()} for i, line in enumerate(lessons.splitlines()) if line.strip()],
                topics=[{"name": x.strip()} for x in dict.fromkeys(topics.split(",")) if x.strip()])


@st.dialog("Un nuevo punto de partida", width="large", on_dismiss=dismiss_dialog)
def add_track_dialog(service):
    with st.form("add_track"):
        payload = new_track_fields()
        a, b = st.columns(2)
        status = a.selectbox("Estado", ["planned", "active", "paused"], format_func=STATUS.get)
        favorite = b.checkbox("Guardar en favoritos")
        skill_ids = multi_records("Habilidades que cubre", service.data["skills"], key="newskills")
        submitted = st.form_submit_button("Crear aprendizaje", type="primary")
    if submitted:
        def create(rid):
            payload["skills"] = [{"name": s["name"], "definition": s.get("definition", "")} for s in service.data["skills"] if s["id"] in skill_ids]
            return service.create_track(TrackDraft.model_validate(payload), rid, status=status, favorite=favorite)
        save_and_refresh("newtrack", create, "Tu aprendizaje ya tiene un lugar.")


@st.dialog("Registrar un momento de aprendizaje", width="large", on_dismiss=dismiss_dialog)
def session_dialog(service, track_id=None, topic_id=None, block=None):
    data = service.data
    if not data["areas"]:
        st.info("Añade primero un aprendizaje o una habilidad para definir un área.")
        return
    if block:
        track_id, topic_id = block.get("track_id"), block.get("topic_id")
        st.caption("Bloque del plan: " + block["title"])
    tracks = [t for t in data["learning_tracks"] if t["status"] != "archived"]
    # Outside the form: changes can update the suggested area and coverage immediately.
    selected_track = select_record("Aprendizaje asociado", tracks, field="title", optional=True, default=track_id, key="sess_track")
    track = domain.by_id(tracks).get(selected_track)
    topic = domain.by_id(data["topics"]).get(topic_id)
    area_default = track["area_id"] if track else topic["area_id"] if topic else None
    selected_topics = [topic_id] if topic_id else []
    selected_skills = [l["skill_id"] for l in data["track_skills"] if l["track_id"] == selected_track]
    selected_skills += [l["skill_id"] for l in data["topic_skills"] if l["topic_id"] == topic_id]
    with st.form("session_form"):
        a, b, c = st.columns(3)
        occurred = a.date_input("Fecha", service.current, max_value=service.current)
        duration = b.number_input("Minutos reales", 1, 1440, block["planned_minutes"] if block else 25, step=1)
        activity = c.selectbox("Actividad", list(ACTIVITY), index=1 if topic_id else 0, format_func=ACTIVITY.get)
        area_id = select_record("Área de esta sesión", data["areas"], default=area_default, key="sess_area_"+str(selected_track)+str(topic_id))
        linked_phases = [r["phase_id"] for r in data["phase_tracks"] if r["track_id"] == selected_track]
        phase_id = select_record("Fase de la ruta (opcional)", data["goal_phases"], field="title", optional=True,
                                 default=linked_phases[0] if len(linked_phases)==1 else None, key="sess_phase_"+str(selected_track))
        topic_ids = multi_records("Temas practicados", data["topics"], default=selected_topics, key="sess_topics_"+str(selected_track)+str(topic_id))
        skill_ids = multi_records("Habilidades practicadas", data["skills"], default=list(dict.fromkeys(selected_skills)), key="sess_skills_"+str(selected_track)+str(topic_id))
        st.caption("El tiempo se reparte entre las habilidades seleccionadas; nunca se multiplica. Los temas no cuentan como aprendidos automáticamente.")
        rating = st.selectbox("Cómo lo recordaste · sólo para repaso o práctica", list(RATING), format_func=RATING.get)
        notes = st.text_area("Qué hiciste o descubriste", key="sess_notes")
        evidence_title = st.text_input("Entregable / evidencia (opcional)", key="sess_evidence")
        evidence_url = st.text_input("Enlace a la evidencia (opcional)", key="sess_url")
        submitted = st.form_submit_button("Guardar sesión", type="primary")
    if submitted:
        save_and_refresh("session", lambda rid: service.record_session(SessionDraft(
            occurred_on=occurred, duration_minutes=duration, area_id=area_id, track_id=selected_track, phase_id=phase_id,
            topic_ids=topic_ids, skill_ids=skill_ids, activity_type=activity, rating=rating, notes=notes,
            evidence_title=evidence_title, evidence_url=evidence_url or None, plan_block_id=block["id"] if block else None), rid),
            "Sesión registrada. Tus métricas ya incluyen esta práctica.")


def track_card(service, track, detail=False):
    data = service.data
    p = domain.progress(data, track["id"])
    est = domain.estimate(data, track)
    with st.container(border=True):
        pills([KIND[track["kind"]], STATUS[track["status"]], "★ Favorito"] if track.get("favorite") else [KIND[track["kind"]], STATUS[track["status"]]])
        st.subheader(track["title"])
        st.caption(" · ".join(x for x in [domain.by_id(data["areas"])[track["area_id"]]["name"], track.get("platform"), track.get("code")] if x))
        st.progress((p["percent"] or 0)/100, text=f"{p['percent']}% · {p['done']}/{p['total']} unidades" if p["percent"] is not None else "Sin definir · añade unidades para medir avance")
        total_label = minutes(est["total"]) + (f" + {est['total_missing']} por estimar" if est["total_missing"] else "")
        remaining_label = minutes(est["remaining"]) + (f" + {est['missing']} por estimar" if est["missing"] else "")
        st.caption(f"Invertido: {minutes(domain.effort(data, track['id']))}  ·  Material estimado: {total_label}  ·  Pendiente: {remaining_label}")
        if track.get("target_on"):
            st.caption("Meta personal: " + track["target_on"])
        a, b = st.columns([3, 1])
        if a.button("Registrar sesión", key="record_"+track["id"], width="stretch"):
            open_dialog("session", track_id=track["id"])
        if b.button("★" if track.get("favorite") else "☆", key="favorite_"+track["id"], help="Cambiar favorito", width="stretch"):
            save_and_refresh("favorite_"+track["id"], lambda rid: service.update_track(track["id"], {"favorite": not track.get("favorite", False)}, rid))
        if detail:
            track_details(service, track)


def track_details(service, track):
    data, tid = service.data, track["id"]
    with st.expander("Unidades, temario y detalles"):
        if track.get("source_url"):
            st.link_button("Abrir material de referencia ↗", track["source_url"])
        done = {p["unit_id"] for p in data["unit_progress"]}
        units = domain.track_units(data, tid)
        for unit in units:
            was = unit["id"] in done
            checked = st.checkbox(unit["title"] + (" · opcional" if not unit["required"] else ""), value=was, key="unit_"+unit["id"])
            if checked != was:
                save_and_refresh("unit_"+unit["id"], lambda rid, u=unit, value=checked: service.toggle_unit(u["id"], value, rid))
            with st.expander("Ajustar · "+unit["title"]):
                with st.form("editunit_"+tid+unit["id"]):
                    unit_title=st.text_input("Título de la unidad",unit["title"])
                    unit_estimate=st.number_input("Estimación en minutos · 0 si desconocida",0,600000,unit.get("estimated_minutes") or 0)
                    unit_required=st.checkbox("Unidad obligatoria",unit["required"])
                    unit_weight=st.number_input("Peso para el progreso",min_value=0.01,max_value=100.0,value=float(unit["weight"]),step=0.25)
                    remove=st.checkbox("Retirar del temario de este aprendizaje, conservando el historial")
                    if st.form_submit_button("Guardar unidad"):
                        save_and_refresh("editunit_"+tid+unit["id"],lambda rid,u=unit:service.update_unit(tid,u["id"],unit_title,unit_estimate or None,unit_required,unit_weight,remove,rid))
        if not units:
            st.caption("Todavía no hay unidades. El progreso no se infiere de las horas.")
        with st.form("addunit_"+tid):
            title = st.text_input("Nueva unidad", key="unittitle_"+tid)
            a, b = st.columns(2)
            mins = a.number_input("Estimación en minutos (0 = desconocida)", 0, 600000, 0, key="unitmins_"+tid)
            required = b.checkbox("Cuenta para completar", True, key="unitreq_"+tid)
            if st.form_submit_button("Añadir unidad"):
                save_and_refresh("addunit_"+tid, lambda rid: service.add_unit(tid, title, mins or None, rid, required))
        current_topics = {l["topic_id"] for l in data["track_topics"] if l["track_id"] == tid}
        current_skills = [l["skill_id"] for l in data["track_skills"] if l["track_id"] == tid]
        with st.form("coverage_"+tid):
            topics = st.text_area("Temas del aprendizaje · uno por línea", "\n".join(t["name"] for t in data["topics"] if t["id"] in current_topics))
            skills = multi_records("Habilidades que cubre", data["skills"], default=current_skills, key="coverage_skills_"+tid)
            st.caption("Cobertura del contenido: no acredita dominio ni añade tiempo de práctica.")
            if st.form_submit_button("Guardar temario"):
                save_and_refresh("coverage_"+tid, lambda rid: service.set_coverage(tid, topics.splitlines(), skills, rid))
        with st.form("edit_"+tid):
            title = st.text_input("Nombre", track["title"])
            status = st.selectbox("Estado", list(STATUS), index=list(STATUS).index(track["status"]), format_func=STATUS.get)
            priority = st.slider("Prioridad · 1 es la más alta", 1, 5, track["priority"])
            target = st.date_input("Fecha objetivo (opcional)", value=domain.as_date(track["target_on"]) if track.get("target_on") else None)
            official = st.text_input("Nombre oficial", track.get("official_name", ""))
            platform = st.text_input("Plataforma", track.get("platform", ""))
            issuer = st.text_input("Emisor", track.get("issuer", ""))
            code = st.text_input("Código / examen", track.get("code", ""))
            url = st.text_input("URL", track.get("source_url") or "")
            est = st.number_input("Estimación global en minutos (sin unidades; 0 = desconocida)", 0, 600000, track.get("estimated_minutes") or 0)
            notes = st.text_area("Notas", track.get("notes", ""))
            if st.form_submit_button("Guardar detalles"):
                save_and_refresh("edit_"+tid, lambda rid: service.update_track(tid, dict(title=title, status=status, priority=priority,
                    target_on=target.isoformat() if target else None, official_name=official, platform=platform, issuer=issuer, code=code,
                    source_url=url or None, estimated_minutes=est or None, notes=notes), rid))
        for linked_resource in [r for r in data["resources"] if r.get("kind") == "link" and
                                any(l["track_id"] == tid and l["resource_id"] == r["id"] for l in data["track_resources"])]:
            st.link_button(linked_resource["title"], linked_resource["url"])
            st.caption(linked_resource.get("notes", ""))
        resources = {l["resource_id"] for l in data["track_resources"] if l["track_id"] == tid}
        for attachment in [a for a in data["attachments"] if a.get("resource_id") in resources]:
            download_attachment(service, attachment)


def download_attachment(service, attachment):
    if st.button("Preparar descarga · " + attachment["original_name"], key="prepare_"+attachment["id"]):
        try:
            st.session_state["download_"+attachment["id"]] = service.repo.download(attachment["storage_path"])
        except Exception:
            st.error("No se pudo recuperar el adjunto privado.")
    if "download_"+attachment["id"] in st.session_state:
        st.download_button("Descargar adjunto", st.session_state["download_"+attachment["id"]], attachment["original_name"],
                           mime=attachment["mime_type"], key="download_button_"+attachment["id"])


def panorama(service):
    data = service.data
    heading("CRECE A TU RITMO", "Cada pequeño paso cuenta.", "Un lugar para ver lo que estás construyendo, conectar tus habilidades y elegir qué viene después.")
    active = [t for t in data["learning_tracks"] if t["status"] == "active"]
    recent = sum(s["duration_minutes"] for s in domain.active_sessions(data) if domain.as_date(s["occurred_on"]) >= service.current-timedelta(days=6))
    learned = [t for t in data["topics"] if domain.review_state(data, t["id"], service.current)]
    streak = domain.streak(data, service.current, service.profile["streak_minutes"])
    metrics([("EN MOVIMIENTO", len(active), "aprendizajes activos"), ("ESTA SEMANA", f"{recent/60:.1f} h".replace(".",","), minutes(recent)+" · últimos 7 días"),
             ("TU CONSTANCIA", f"{streak['current']} días", f"racha de ≥ {service.profile['streak_minutes']} min / día"), ("LO QUE YA CONECTAS", len(learned), "temas que marcaste como aprendidos")])
    goals = [g for g in data["learning_goals"] if g["status"] == "active"]
    if goals:
        goal = goals[-1]
        phases = [p for p in data["goal_phases"] if p["goal_id"] == goal["id"]]
        current = next((p for p in phases if p["starts_on"] <= service.current.isoformat() <= p["ends_on"]), None)
        hero("TU NORTE · " + goal["title"], current["title"] if current else "Una ruta con intención.",
             f"{minutes(goal['weekly_minutes'])} por semana · {goal['starts_on']} → {goal['target_on']}. " + (current["topics"] if current else goal["outcome"]))
    else:
        hero("EMPIEZA CON LO QUE IMPORTA", "Dale un lugar a tu próximo paso.", "Añade un aprendizaje o abre Mi ruta para cargar el plan Factory Enablement. Tu avance empieza desde cero.")
    st.subheader("Tu mesa de trabajo")
    tracks = sorted(active, key=lambda t: (not t.get("favorite"), t["priority"], t["title"]))[:4]
    if tracks:
        cols = st.columns(2)
        for i, track in enumerate(tracks):
            with cols[i % 2]:
                track_card(service, track)
    else:
        st.info("Aún no hay aprendizajes en curso. Puedes activar uno desde Mi aprendizaje.")
    st.subheader("Una mirada a tus áreas")
    sessions = domain.active_sessions(data)
    if sessions:
        areas = domain.by_id(data["areas"])
        frame = pd.DataFrame([{"Área": areas[s["area_id"]]["name"], "Minutos": s["duration_minutes"]} for s in sessions]).groupby("Área", as_index=False).sum()
        fig = px.bar(frame, x="Minutos", y="Área", orientation="h", color_discrete_sequence=["#6e9070"])
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=280, margin=dict(l=0,r=10,t=10,b=0))
        st.plotly_chart(fig, width="stretch")
    else:
        st.caption("Tus sesiones mostrarán aquí en qué áreas estás invirtiendo tiempo.")


def learning(service):
    heading("TU BIBLIOTECA VIVA", "Aprender, con intención.", "Cursos, certificaciones, proyectos y temas. Cada uno con su contenido, su ritmo y su lugar en tu historia.")
    a, b, c = st.columns([2, 1, 1])
    query = a.text_input("Buscar", placeholder="Python, redes, una plataforma…")
    state = b.selectbox("Estado", [None]+list(STATUS), format_func=lambda v: "Todos" if v is None else STATUS[v])
    favorite = c.checkbox("Sólo favoritos")
    rows = [t for t in service.data["learning_tracks"] if (state is None or t["status"] == state) and (not favorite or t.get("favorite"))
            and query.casefold() in (t["title"]+" "+t.get("platform", "")+" "+t.get("official_name", "")).casefold()]
    for track in sorted(rows, key=lambda t: (not t.get("favorite"), t["priority"], t["title"])):
        track_card(service, track, detail=True)
    if not rows:
        st.info("Aquí aparecerán tus aprendizajes. Usa ‘Añadir aprendizaje’ o importa un documento.")


def route_page(service):
    heading("UN NORTE, MUCHOS PASOS", "Tu ruta de crecimiento.", "El calendario organiza la intención. Los entregables aceptados y las sesiones cuentan lo que realmente hiciste.")
    data = service.data
    if not data["learning_goals"]:
        hero("FACTORY ENABLEMENT", "De Python a un piloto reproducible.", "12 oct 2026 → 3 ene 2027 · 8 h semanales · 88 h de trabajo y 8 h de margen. La ruta se crea sin avances registrados.")
        if st.button("Crear mi ruta Factory Enablement", type="primary"):
            save_and_refresh("factory", lambda rid: service.create_route(factory_route(), rid), "Ruta creada. No se añadieron horas ni progreso.")
    else:
        gid = select_record("Ruta / versión", data["learning_goals"], field="title", key="route_selected", default=data["learning_goals"][-1]["id"])
        goal = domain.by_id(data["learning_goals"])[gid]
        phases = sorted([p for p in data["goal_phases"] if p["goal_id"] == gid], key=lambda p:p["sort_order"])
        phase_ids = {p["id"] for p in phases}
        milestones = [m for m in data["milestones"] if m["phase_id"] in phase_ids]
        budget = sum(p["budget_minutes"] for p in phases)
        worked = sum(s["duration_minutes"] for s in domain.active_sessions(data) if s.get("phase_id") in phase_ids)
        metrics([("ENTREGABLES ACEPTADOS", f"{sum(bool(m.get('accepted_on')) for m in milestones)}/{len(milestones)}", "confirmación explícita"),
                 ("PLAN ORIGINAL", minutes(budget), f"versión {goal['version']} · {goal['status']}"), ("PRÁCTICA ASOCIADA", minutes(worked), "sesiones vinculadas a sus fases")])
        st.caption(f"{goal['starts_on']} → {goal['target_on']} · {minutes(goal['weekly_minutes'])}/semana. El presupuesto no equivale a horas disponibles desde hoy ni se recupera automáticamente.")
        for i, phase in enumerate(phases):
            ms = next((m for m in milestones if m["phase_id"] == phase["id"]), None)
            with st.container(border=True):
                pills([f"PASO {i+1:02d}", "Margen" if phase["is_buffer"] else minutes(phase["budget_minutes"]), "Aceptado" if ms and ms.get("accepted_on") else "Pendiente"])
                st.subheader(phase["title"])
                st.caption(f"{phase['starts_on']} → {phase['ends_on']} · {phase['topics']}")
                linked_ids = {r["track_id"] for r in data["phase_tracks"] if r["phase_id"] == phase["id"]}
                for learning_track in data["learning_tracks"]:
                    if learning_track["id"] in linked_ids:
                        st.write("Aprendizaje vinculado: "+learning_track["title"])
                if ms:
                    with st.expander("Entregable · " + ms["title"]):
                        st.text(ms["criteria"])
                        with st.form("milestone_"+ms["id"]):
                            accepted = st.checkbox("Revisé el resultado y cumple los criterios", bool(ms.get("accepted_on")))
                            evidence = select_record("Evidencia vinculada (opcional)", data["learning_evidence"], field="title", optional=True, default=ms.get("evidence_id"), key="mev_"+ms["id"])
                            notes = st.text_area("Notas de revisión", ms.get("notes", ""))
                            if st.form_submit_button("Guardar revisión"):
                                save_and_refresh("milestone_"+ms["id"], lambda rid: service.accept_milestone(ms["id"], accepted, notes, evidence, rid))
        with st.expander("Replanificar conservando esta versión"):
            st.caption("Edita la propuesta y guarda una versión nueva. La anterior y sus sesiones permanecerán en tu historial.")
            draft = {"title": goal["title"], "outcome": goal["outcome"], "weekly_minutes": goal["weekly_minutes"], "phases": []}
            for phase in phases:
                ms = next(m for m in milestones if m["phase_id"] == phase["id"])
                draft["phases"].append({k: phase[k] for k in ["title", "starts_on", "ends_on", "budget_minutes", "topics", "is_buffer"]} | {"milestone": ms["title"], "criteria": ms["criteria"]})
            edited = st.text_area("Propuesta de ruta en JSON", json.dumps(draft, ensure_ascii=False, indent=2), height=230, key="route_json_"+gid)
            confirm = st.checkbox("Crear versión nueva y archivar la seleccionada", key="route_accept_"+gid)
            if st.button("Guardar nueva versión", disabled=not confirm):
                save_and_refresh("replan_"+gid, lambda rid: service.create_route(RouteDraft.model_validate_json(edited), rid, supersedes=gid))


def skills_page(service):
    heading("LO QUE ESTÁS CONECTANDO", "Tu mapa de habilidades.", "Distingue el contenido que has encontrado, la práctica que has registrado y lo que ahora puedes hacer con más autonomía.")
    data = service.data
    with st.expander("Añadir una habilidad"):
        with st.form("newskill"):
            name = st.text_input("Habilidad")
            area = st.text_input("Área", "General")
            definition = st.text_input("Qué significa poder hacerlo")
            if st.form_submit_button("Añadir habilidad"):
                save_and_refresh("newskill", lambda rid: service.add_skill(name, definition, area, rid))
    if not data["skills"]:
        st.info("Puedes añadir tus propias habilidades o cargar una base de datos, software, redes y sistemas industriales.")
        if st.button("Cargar mapa inicial de habilidades"):
            save_and_refresh("dictionary", lambda rid: initialize_dictionary(service, rid))
        return
    allstats = [(s, domain.skill_stats(data, s["id"])) for s in data["skills"]]
    practiced = sum(stats["minutes"] > 0 for _, stats in allstats)
    allocated = sum(stats["minutes"] for _, stats in allstats)
    metrics([("HABILIDADES", len(allstats), "en tu mapa personal"), ("EN PRÁCTICA", practiced, "con sesiones registradas"),
             ("TIEMPO SIN ASIGNAR", minutes(domain.effort(data)-allocated), "sesiones sin distribución a habilidades")])
    frame = pd.DataFrame([{"Habilidad": s["name"], "Minutos": stats["minutes"]} for s, stats in allstats if stats["minutes"]])
    if not frame.empty:
        fig = px.bar(frame.sort_values("Minutos"), x="Minutos", y="Habilidad", orientation="h", color_discrete_sequence=["#779879"])
        fig.update_layout(height=max(250, len(frame)*38), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=0,r=0,t=10,b=0))
        st.plotly_chart(fig, width="stretch")
    for skill, stats in sorted(allstats, key=lambda x: (-x[1]["minutes"], x[0]["name"])):
        with st.expander(f"{skill['name']} · {minutes(stats['minutes'])} · {stats['sessions']} sesiones"):
            st.write(skill.get("definition", ""))
            st.caption(f"Cobertura: {len(stats['track_ids'])} aprendizajes · Evidencias: {len(stats['evidence'])}. La cobertura no demuestra dominio.")
            for track in data["learning_tracks"]:
                if track["id"] in stats["track_ids"]:
                    st.write("↳ " + track["title"])
            for evidence in stats["evidence"]:
                st.write("Evidencia: " + evidence["title"])
                if evidence.get("url"):
                    st.link_button("Abrir evidencia", evidence["url"], key="evlink_"+skill["id"]+evidence["id"])
            for rubric in data["skill_rubrics"]:
                evo = domain.evolution(data, skill["id"], rubric["id"])
                if evo["comparable"]:
                    st.info(f"Autonomía declarada: {evo['first']['level']} → {evo['last']['level']} · {evo['first']['occurred_on']} a {evo['last']['occurred_on']}. Misma rúbrica v{rubric['version']}.")
                if evo["rows"]:
                    st.dataframe(pd.DataFrame(evo["rows"])[["occurred_on", "level", "context"]], hide_index=True, width="stretch")
            with st.form("assess_"+skill["id"]):
                st.write("Una autoevaluación, con contexto")
                when = st.date_input("Fecha", service.current, max_value=service.current)
                level = st.selectbox("Qué puedes hacer", [0,1,2,3], format_func=lambda v:["0 · Todavía no puedo", "1 · Con guía", "2 · Por mi cuenta", "3 · Lo explico y compruebo"][v])
                context = st.text_area("Describe la tarea concreta")
                url = st.text_input("Evidencia (URL opcional)")
                st.caption("Se comparan autoevaluaciones de fechas distintas y la misma rúbrica. No equivale a una evaluación externa.")
                if st.form_submit_button("Registrar autoevaluación"):
                    save_and_refresh("assess_"+skill["id"], lambda rid: service.assess(skill["id"], when, level, context, url or None, rid))


def knowledge_page(service):
    heading("QUE LO APRENDIDO SE QUEDE CONTIGO", "Tu jardín de conocimiento.", "Un mapa de temas y momentos de práctica. El color sugiere qué podrías retomar; tú decides cuándo hacerlo.")
    data = service.data
    with st.expander("Ya aprendí algo · añadir al mapa"):
        with st.form("learnedtopic"):
            name = st.text_input("Tema aprendido")
            area = st.text_input("Área temática", "General")
            when = st.date_input("Cuándo lo aprendiste", service.current, max_value=service.current)
            notes = st.text_area("Qué comprendiste o lograste")
            skills = multi_records("Habilidades relacionadas", data["skills"], key="learnedskills")
            if st.form_submit_button("Añadir tema aprendido"):
                save_and_refresh("learnedtopic", lambda rid: service.add_learned_topic(name, area, when, notes, rid, skills))
    st.caption("Verde → reciente · Ámbar → se acerca el repaso · Rojo suave → podrías retomarlo. Es una regla orientativa, no una medida científica de memoria.")
    states = [(t, domain.review_state(data, t["id"], service.current)) for t in data["topics"]]
    learned = [(t,r) for t,r in states if r]
    if not learned:
        st.info("Los temarios importados aún no son aprendizajes realizados. Añade aquí los temas que ya comprendiste.")
    columns = st.columns(2)
    for i, (topic, review) in enumerate(sorted(learned, key=lambda tr: -tr[1]["ratio"])):
        with columns[i % 2], st.container(border=True):
            color = {"recent": "#e6eddf", "soon": "#f1ead7", "due": "#f3e3dc"}[review["stage"]]
            st.markdown(f"<div class='knowledge' style='background:{color}'><h3>{e(topic['name'])}</h3><p>Aprendido: {review['first']} · Última práctica: {review['last_practice']}</p><p>Próximo repaso orientativo: {review['next']} · Intervalo: {review['interval']} días</p></div>", unsafe_allow_html=True)
            st.caption(f"{review['reviews']} días con repaso valorado. Practicar sin valoración actualiza la última práctica, sin alargar automáticamente el intervalo.")
            if st.button("Repasar o registrar práctica", key="review_"+topic["id"], width="stretch"):
                open_dialog("session", topic_id=topic["id"])
            enabled = st.checkbox("Incluir en sugerencias de repaso", topic.get("review_enabled", True), key="enabled_"+topic["id"])
            if enabled != topic.get("review_enabled", True):
                def update(rid, t=topic, value=enabled):
                    batch = Batch(service.data)
                    batch.put("topics", {**t, "review_enabled": value})
                    return service._commit(batch, rid, {"action":"review_preference", "id":t["id"], "enabled":value})
                save_and_refresh("enabled_"+topic["id"], update)


def activity_page(service):
    heading("EL RITMO QUE VAS CONSTRUYENDO", "Tu aprendizaje, en el tiempo.", "Cuenta el tiempo real, también cuando practicas en el trabajo. Una sesión se cuenta una vez, aunque conecte muchas habilidades.")
    if st.button("Registrar una sesión", type="primary"):
        open_dialog("session")
    data = service.data
    a, b = st.columns(2)
    start = a.date_input("Desde", service.current-timedelta(days=89))
    end = b.date_input("Hasta", service.current, max_value=service.current)
    if start > end:
        st.warning("La fecha inicial debe ser anterior a la final.")
        return
    sessions = [s for s in domain.active_sessions(data) if start <= domain.as_date(s["occurred_on"]) <= end]
    daily = domain.daily_minutes(data)
    days = [end-timedelta(days=i) for i in range(min((end-start).days+1,366)-1,-1,-1)]
    if days:
        weeks = [d-timedelta(days=d.weekday()) for d in days]
        week_keys = sorted(set(weeks))
        z = [[None for _ in week_keys] for _ in range(7)]
        custom = [["" for _ in week_keys] for _ in range(7)]
        for d, week in zip(days, weeks):
            j = week_keys.index(week)
            z[d.weekday()][j] = daily.get(d,0)
            custom[d.weekday()][j] = d.isoformat()
        fig = go.Figure(go.Heatmap(z=z, x=[str(w) for w in week_keys], y=["Lun","Mar","Mié","Jue","Vie","Sáb","Dom"],
            customdata=custom, colorscale=[[0,"#e8ecdf"],[1,"#35694d"]], xgap=4, ygap=4,
            hovertemplate="%{customdata}<br>%{z} min<extra></extra>", colorbar=dict(title="Minutos")))
        fig.update_layout(height=240, margin=dict(l=0,r=0,t=10,b=0), paper_bgcolor="rgba(0,0,0,0)", yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig, width="stretch")
        st.caption("Calendario: hasta 366 días de la selección. Cada celda usa la fecha local que registraste.")
    metrics([("TIEMPO REGISTRADO", minutes(sum(s["duration_minutes"] for s in sessions)), "en el período seleccionado"),
             ("SESIONES", len(sessions), "sin incluir anulaciones"), ("MEJOR RACHA", f"{domain.streak(data,service.current,service.profile['streak_minutes'])['longest']} días", "historial completo")])
    tracks, areas = domain.by_id(data["learning_tracks"]), domain.by_id(data["areas"])
    for session in sorted(sessions, key=lambda s: (s["occurred_on"],s.get("created_at","")), reverse=True):
        with st.expander(f"{session['occurred_on']} · {minutes(session['duration_minutes'])} · {ACTIVITY[session['activity_type']]} · {tracks.get(session.get('track_id'), {}).get('title', areas[session['area_id']]['name'])}"):
            st.write(session.get("notes") or "Sin notas")
            linked = [a for a in data["session_skills"] if a["session_id"] == session["id"]]
            skillmap = domain.by_id(data["skills"])
            for allocation in linked:
                st.caption(skillmap[allocation["skill_id"]]["name"] + ": " + minutes(allocation["allocated_minutes"]))
            with st.form("void_"+session["id"]):
                reason = st.text_input("Motivo de corrección")
                confirm = st.checkbox("Anular esta sesión; después puedo registrar la correcta")
                if st.form_submit_button("Anular sesión"):
                    if confirm:
                        save_and_refresh("void_"+session["id"], lambda rid: service.void_session(session["id"], reason, rid), "Sesión anulada. Su tiempo ya no cuenta.")
                    else:
                        st.warning("Marca la confirmación antes de anular.")
    with st.expander("Evidencias y entregables registrados"):
        live_ids = {s["id"] for s in domain.active_sessions(data)}
        for evidence in data["learning_evidence"]:
            if evidence.get("session_id") and evidence["session_id"] not in live_ids:
                continue
            st.write(evidence["title"])
            st.caption(str(evidence.get("occurred_on") or evidence.get("period_label") or "Fecha sin precisar") + " · " + evidence["validation_status"])
            st.write(evidence.get("description", ""))
            if evidence.get("url"):
                st.link_button("Ver evidencia ↗", evidence["url"], key="evidence_"+evidence["id"])
            for attachment in [a for a in data["attachments"] if a.get("evidence_id") == evidence["id"]]:
                download_attachment(service, attachment)


def discovery_page(service):
    from .catalog_ui import render
    render(service)


def day_page(service):
    heading("UN POCO DE ESTRUCTURA, SIN PRESIÓN", "¿Y si hoy empiezas por algo pequeño?", "Elige el tiempo y la energía que tienes. Te proponemos hasta tres bloques para avanzar sin llenar todo el día.")
    with st.form("dayplan"):
        a,b=st.columns(2)
        budget=a.select_slider("Tiempo disponible",[20,30,45,60,90,120],value=45,format_func=minutes)
        energy=b.selectbox("Cómo te sientes",list(ENERGY),index=1,format_func=ENERGY.get)
        if st.form_submit_button("Preparar mi plan",type="primary"):
            save_and_refresh("dayplan",lambda rid:service.save_plan(budget,energy,rid),"Plan listo. Las horas sólo se registran cuando realizas un bloque.")
    st.caption("El plan usa tus prioridades, unidades pendientes y repasos orientativos. Se genera con reglas locales, sin enviar tus datos a una IA.")
    plans=sorted([p for p in service.data["daily_plans"] if p["plan_date"]==service.current.isoformat()],key=lambda p:p.get("created_at",""),reverse=True)
    if not plans:
        hero("HOY PUEDE SER SUFICIENTE", "Una cosa pequeña, bien hecha.", "Activa un aprendizaje con unidades o añade un tema aprendido para recibir una sugerencia.")
        return
    pid=select_record("Plan de hoy",plans,field="created_at",key="today_plan",default=plans[0]["id"])
    plan=domain.by_id(plans)[pid]
    blocks=sorted([b for b in service.data["plan_blocks"] if b["plan_id"]==pid],key=lambda b:b["sort_order"])
    used=sum(b["planned_minutes"] for b in blocks)+max(0,len(blocks)-1)*5
    st.caption(f"{minutes(used)} propuestos de {minutes(plan['budget_minutes'])} disponibles · incluye pausas de 5 min entre bloques.")
    for i,block in enumerate(blocks):
        with st.container(border=True):
            pills([f"BLOQUE {i+1:02d}",minutes(block["planned_minutes"]),"Realizado" if block.get("completed_session_id") else "A tu ritmo"])
            st.subheader(block["title"])
            st.write(block["reason"])
            if st.button("Sesión guardada" if block.get("completed_session_id") else "Lo hice · registrar tiempo real",disabled=bool(block.get("completed_session_id")),key="block_"+block["id"]):
                open_dialog("session",block=block)


def import_page(service):
    heading("DE TUS DOCUMENTOS A TU MAPA", "Trae lo que quieres aprender.", "Lee el archivo, revisa su organización y decide qué guardar. Nada se convierte en avance por aparecer en un documento.")
    data=service.data
    with st.expander("1 · Añadir un documento",expanded=True):
        uploaded=st.file_uploader("PDF, DOCX, TXT, MD o una propuesta JSON",type=["pdf","docx","txt","md","json"],max_upload_size=10,key="import_upload")
        if uploaded and st.button("Leer documento",type="primary"):
            try:
                contents=uploaded.getvalue()
                info=file_metadata(uploaded.name,contents)
                with st.spinner("Leyendo el documento…"):
                    extracted=extract_document(uploaded.name,contents)
                st.session_state.import_source={**info,"contents":contents,**extracted}
                st.session_state.pop("import_uploaded_path",None)
                st.session_state.pop("proposal_editor",None)
                if Path(uploaded.name).suffix.lower()==".json":
                    proposal=ImportProposal.model_validate_json(extracted["text"])
                    st.session_state.proposal_editor=json.dumps(proposal.model_dump(mode="json"),ensure_ascii=False,indent=2)
            except (ValueError,Exception) as exc:
                st.error(str(exc) if isinstance(exc,ValueError) else "No se pudo leer el documento.")
        source=st.session_state.get("import_source")
        if source:
            st.success(f"Leído: {source['filename']} · {len(source['text']):,} caracteres")
            for warning in source["warnings"]:
                st.warning(warning)
            with st.expander("Texto extraído · comprueba que esté completo"):
                st.text_area("Contenido",source["text"],height=220,disabled=True,key="extracted_"+source["sha256"])
            gemini={} if service.repo.is_demo else configuration().get("gemini",{})
            consent=st.checkbox("Quiero enviar este texto a Google Gemini para obtener una propuesta. Revisé que puedo compartir su contenido.",key="gemini_consent")
            if st.button("Proponer organización con Gemini",disabled=not(consent and gemini.get("api_key") and gemini.get("model"))):
                try:
                    with st.spinner("Gemini está preparando una propuesta revisable…"):
                        proposal=propose_with_gemini(source["text"],gemini["api_key"],gemini["model"])
                    st.session_state.proposal_editor=json.dumps(proposal.model_dump(mode="json"),ensure_ascii=False,indent=2)
                    st.session_state.import_model=gemini["model"]
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
            if not gemini.get("api_key") or not gemini.get("model"):
                st.caption("Gemini requiere una cuenta conectada y una clave configurada. La captura manual y la importación JSON funcionan sin IA.")
    with st.expander("2 · Organizar y validar",expanded=bool(st.session_state.get("import_source"))):
        st.caption("Puedes crear una propuesta manual con este formulario o editar JSON para módulos, habilidades, evidencias y fases de una ruta.")
        with st.form("manualproposal"):
            payload=new_track_fields("importmanual_")
            if st.form_submit_button("Preparar propuesta manual"):
                try:
                    proposal=ImportProposal(tracks=[TrackDraft.model_validate(payload)])
                    st.session_state.proposal_editor=json.dumps(proposal.model_dump(mode="json"),ensure_ascii=False,indent=2)
                    st.session_state.pop("import_model",None)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        raw=st.text_area("Propuesta JSON · editable",key="proposal_editor",height=260)
        st.download_button("Descargar esquema JSON",json.dumps(ImportProposal.model_json_schema(),ensure_ascii=False,indent=2),"learning-atlas-import.schema.json",mime="application/json")
        duplicate=bool(source and any(j["sha256"]==source["sha256"] and j["status"]!="cancelled" for j in data["import_jobs"]))
        allow_duplicate=False
        if duplicate:
            st.warning("Este mismo archivo ya tiene una importación guardada o pendiente. Revisa las importaciones de abajo antes de crear otra.")
            allow_duplicate=st.checkbox("Quiero preparar otra importación del mismo archivo conscientemente")
        if st.button("Validar y guardar borrador",type="primary",disabled=not raw or duplicate and not allow_duplicate):
            def stage(rid):
                proposal=ImportProposal.model_validate_json(raw)
                metadata={"filename":"captura-manual.json","sha256":sha256(raw.encode()).hexdigest(),"storage_path":None,"mime_type":"application/json",
                          "extractor_version":"extract-v1","model_id":st.session_state.get("import_model"),"prompt_version":"import-v1" if st.session_state.get("import_model") else None}
                if source:
                    path=st.session_state.get("import_uploaded_path")
                    if not path:
                        path=service.repo.user_id+"/imports/"+str(uuid4())+Path(source["filename"]).suffix.lower()
                        service.repo.upload(path,source["contents"],source["mime_type"])
                        st.session_state.import_uploaded_path=path
                    metadata.update({k:source[k] for k in ("filename","sha256","mime_type")})
                    metadata["storage_path"]=path
                return service.stage_import(proposal,metadata,rid)
            answer=action("stageimport",stage,"Borrador validado. Falta tu aprobación para incorporar el contenido.")
            if answer:
                for key in ("import_source","import_uploaded_path","proposal_editor","import_model"):
                    st.session_state.pop(key,None)
                st.rerun()
    st.subheader("3 · Revisar y aprobar")
    jobs=sorted(data["import_jobs"],key=lambda j:j.get("created_at",""),reverse=True)
    if not jobs:
        st.caption("Aquí aparecerán las propuestas validadas, incluidas las que dejes pendientes para otro día.")
    for job in jobs:
        with st.expander(job["filename"]+" · "+{"draft":"Pendiente de revisión","imported":"Importado","cancelled":"Cancelado"}[job["status"]],expanded=job["status"]=="draft"):
            if job["status"]=="draft":
                proposal=ImportProposal.model_validate(job["proposal"])
                st.write(f"{len(proposal.tracks)} aprendizajes · {sum(len(t.units) for t in proposal.tracks)} unidades (incluye módulos) · {len(proposal.evidence)} evidencias · {len(proposal.route.phases) if proposal.route else 0} fases")
                st.caption("Se reutilizan áreas, temas y habilidades por nombre normalizado. Los aprendizajes con nombre parecido requieren tu decisión.")
                for warning in proposal.warnings:
                    st.warning(warning)
                for draft in proposal.tracks:
                    st.write("**"+draft.title+"** · "+KIND[draft.kind]+" · "+draft.area)
                    if draft.units:
                        parents={u.parent_key for u in draft.units if u.parent_key}
                        st.dataframe(pd.DataFrame([{"Unidad":u.title,"Tipo":"Módulo" if u.key in parents else "Lección",
                            "Minutos estimados":u.estimated_minutes,"Obligatoria":u.required,"Peso":u.weight} for u in draft.units]),hide_index=True,width="stretch")
                    pills([t.name for t in draft.topics])
                    if draft.skills:
                        st.caption("Habilidades cubiertas: "+", ".join(s.name for s in draft.skills))
                    matches=[t["title"] for t in data["learning_tracks"] if t["title"].casefold().strip()==draft.title.casefold().strip()]
                    if matches:
                        st.warning("Ya tienes un aprendizaje con este nombre: "+draft.title)
                if proposal.route:
                    st.write("Ruta: "+proposal.route.title)
                    st.dataframe(pd.DataFrame([{"Fase":p.title,"Inicio":p.starts_on,"Fin":p.ends_on,"Minutos":p.budget_minutes,"Entregable":p.milestone} for p in proposal.route.phases]),hide_index=True,width="stretch")
                for evidence in proposal.evidence:
                    st.write("Evidencia declarada: "+evidence.title+" · "+str(evidence.occurred_on or evidence.period_label or "Fecha sin precisar"))
                with st.expander("Editar estructura completa · JSON"):
                    edited=st.text_area("Propuesta a guardar",json.dumps(job["proposal"],ensure_ascii=False,indent=2),height=230,key="draft_"+job["id"])
                if st.button("Validar cambios del borrador",key="editdraft_"+job["id"]):
                    info={k:job.get(k) for k in ["filename","sha256","storage_path","mime_type","extractor_version","model_id","prompt_version"]}
                    save_and_refresh("editdraft_"+job["id"],lambda rid,j=job,i=info:service.stage_import(ImportProposal.model_validate_json(edited),i,rid,job_id=j["id"]),"Borrador actualizado. Revísalo y apruébalo de nuevo.")
                target=None
                if len(proposal.tracks)==1 and not proposal.route and not proposal.evidence:
                    target=select_record("Destino · sin asociar crea un aprendizaje nuevo",data["learning_tracks"],field="title",optional=True,key="import_target_"+job["id"])
                changed=False
                try:
                    changed=ImportProposal.model_validate_json(edited).model_dump(mode="json") != job["proposal"]
                except ValueError:
                    changed=True
                approved=st.checkbox("Revisé el temario, las fechas, estimaciones y el destino. Aprobar esta propuesta.",key="approve_"+job["id"]+job["proposal_hash"]+str(target))
                if changed:
                    st.caption("Valida los cambios del texto antes de aprobar.")
                a,b=st.columns(2)
                if a.button("Importar lo aprobado",type="primary",disabled=not approved or changed,key="apply_"+job["id"]):
                    save_and_refresh("apply_"+job["id"],lambda rid,j=job,t=target:service.apply_import(j["id"],j["proposal_hash"],rid,target_track_id=t,accepted=True),"Importación completa. No se añadieron horas ni progreso automático.")
                if b.button("Cancelar borrador",key="cancel_"+job["id"]):
                    answer=action("cancel_"+job["id"],lambda rid,j=job:service.cancel_import(j["id"],rid))
                    if answer:
                        st.session_state.flash="Borrador cancelado."+(" El archivo necesita un reintento de limpieza." if answer["result"]["cleanup_pending"] else "")
                        st.rerun()
            elif job["status"]=="imported":
                st.success("Contenido guardado. Reabrir esta importación no lo vuelve a insertar.")
                st.json(job["result"],expanded=False)
            elif job.get("storage_path") and st.button("Reintentar limpieza del archivo cancelado",key="cleanup_"+job["id"]):
                answer=action("cleanup_"+job["id"],lambda rid,j=job:service.cancel_import(j["id"],rid))
                if answer:
                    st.info("Limpieza pendiente; vuelve a intentar más tarde." if answer["result"]["cleanup_pending"] else "Archivo eliminado o ya ausente.")


def credentials_page(service):
    heading("LOGROS CON SU PROPIO CONTEXTO", "Tus credenciales.", "Un certificado de curso, un programa y una certificación profesional son cosas distintas. Regístralos con su nombre y emisor.")
    data=service.data
    with st.expander("Registrar una credencial obtenida"):
        credential_form(service)
    for credential in data["credentials"]:
        with st.container(border=True):
            pills([credential["issuer"],domain.credential_status(credential,service.current)])
            st.subheader(credential["official_name"])
            st.caption((credential.get("earned_on") or credential.get("period_label") or "Fecha sin precisar")+" · Declarada por ti; sin verificación automática.")
            st.write(credential.get("notes", ""))
            if credential.get("verification_url"):
                st.link_button("Consultar credencial ↗",credential["verification_url"],key="clink_"+credential["id"])
            with st.expander("Corregir información de la credencial"):
                credential_form(service,credential)
    if not data["credentials"]:
        st.info("Aquí podrás registrar tus credenciales previas sin inventar horas, fechas exactas ni unidades completadas.")


def credential_form(service,credential=None):
    row=credential or {}
    key="credential_"+row.get("id","new")
    types=["professional","course","program","badge"]
    with st.form(key):
        name=st.text_input("Nombre oficial",row.get("official_name",""))
        issuer=st.text_input("Emisor",row.get("issuer",""))
        ctype=st.selectbox("Tipo de credencial",types,index=types.index(row.get("credential_type","professional")),format_func=lambda x:{"professional":"Certificación profesional","course":"Certificado de curso","program":"Certificado de programa","badge":"Insignia"}[x])
        track=select_record("Aprendizaje relacionado",service.data["learning_tracks"],field="title",optional=True,default=row.get("track_id"),key=key+"track")
        earned=st.date_input("Fecha exacta (opcional)",value=domain.as_date(row["earned_on"]) if row.get("earned_on") else None,max_value=service.current)
        period=st.text_input("Período si no recuerdas el día",row.get("period_label",""),placeholder="Ej. Fall 2024")
        expires=st.date_input("Fecha de caducidad conocida (opcional)",value=domain.as_date(row["expires_on"]) if row.get("expires_on") else None)
        never=st.checkbox("El emisor declara que no caduca",row.get("never_expires",False))
        url=st.text_input("URL de verificación (opcional)",row.get("verification_url") or "")
        notes=st.text_area("Notas",row.get("notes",""))
        if st.form_submit_button("Guardar credencial",type="primary"):
            fields=dict(official_name=name,issuer=issuer,credential_type=ctype,track_id=track,earned_on=earned.isoformat() if earned else None,period_label=period,
                expires_on=expires.isoformat() if expires else None,never_expires=never,verification_url=url or None,notes=notes)
            save_and_refresh(key,lambda rid:service.add_credential(fields,rid,credential_id=row.get("id")))


def settings_page(service):
    heading("HECHO A TU MEDIDA", "Tu espacio, tus reglas.", "Ajusta tu ritmo y conserva una copia de tus datos cuando quieras.")
    with st.form("settings"):
        name=st.text_input("Nombre de tu espacio",service.profile["display_name"])
        zone=st.text_input("Zona horaria IANA",service.profile["timezone"],help="Ejemplos: America/Puerto_Rico, America/La_Paz")
        weekly=st.number_input("Disponibilidad semanal · minutos",10,10080,service.profile["weekly_minutes"])
        threshold=st.number_input("Minutos por día para contar en la racha",1,1440,service.profile["streak_minutes"])
        st.caption("La zona horaria aplica a nuevas fechas; no cambia las fechas locales de sesiones previas. Cambiar disponibilidad no modifica las versiones de tu ruta.")
        if st.form_submit_button("Guardar preferencias",type="primary"):
            save_and_refresh("settings",lambda rid:service.settings(name,zone,weekly,threshold,rid))
    st.subheader("Tu copia de los datos")
    st.download_button("Exportar mis datos · JSON",export_json(service.data),"learning-atlas-export.json",mime="application/json",type="primary")
    st.caption("Incluye registros e historial; no contraseñas, tokens ni el contenido binario de adjuntos. Es una exportación de respaldo, no el formato de propuestas del importador. Descarga los adjuntos desde sus aprendizajes o evidencias.")
    if st.button("Actualizar desde la base de datos"):
        st.rerun()
    st.caption("Persistencia: "+("demo temporal en esta sesión" if service.repo.is_demo else "Supabase · datos privados de tu usuario"))
    with st.expander("Cómo se calculan tus métricas"):
        st.write("Progreso: unidades hoja obligatorias completadas / peso total obligatorio. Sin unidades, sin porcentaje. Tiempo: suma de sesiones vigentes. Las estimaciones pendientes suman material sin terminar; no restan horas invertidas.")
        st.write("Racha: días consecutivos con al menos tu umbral, conservada hasta ayer si hoy aún no estudiaste. Temas: se registran como aprendidos explícitamente. Repaso: intervalo inicial 3 días; volver a verlo 1 día; difícil ×0,7; recordado ×2; fácil ×3, máximo 180 días, una valoración efectiva al día.")
        st.write("Habilidades: minutos repartidos entre las seleccionadas; tiempo sin habilidades queda sin asignar. Autonomía: compara la misma rúbrica en fechas distintas. Ninguna métrica certifica dominio por sí sola.")


def run():
    st.markdown(CSS,unsafe_allow_html=True)
    repo=get_repository()
    try:
        service=LearningService(repo)
    except Exception:
        st.error("No se pudo recuperar tu espacio. Comprueba la conexión y la instalación de Supabase.")
        if st.button("Reintentar"):
            st.rerun()
        if st.button("Cerrar sesión"):
            logout()
        st.stop()
    with st.sidebar:
        st.markdown("<div class='eyebrow'>UN ESPACIO PARA CRECER</div>",unsafe_allow_html=True)
        st.header("Learning Atlas")
        st.caption("Aprende. Conecta. Sigue creciendo.")
        if st.button("＋ Añadir aprendizaje",type="primary",width="stretch",key="add_learning"):
            open_dialog("track")
        st.divider()
        page=st.radio("Tu espacio",NAV,key="navigation",label_visibility="collapsed")
        st.divider()
        st.caption(service.profile["display_name"])
        st.caption(minutes(service.profile["weekly_minutes"])+" por semana · "+("Demo" if repo.is_demo else "Conectado a Supabase"))
        if st.button("Salir de la demo" if repo.is_demo else "Cerrar sesión",width="stretch"):
            logout()
    if repo.is_demo:
        st.caption("ESPACIO DE DEMOSTRACIÓN · Datos ficticios y cambios temporales; no reflejan tu avance real.")
    if "flash" in st.session_state:
        st.success(st.session_state.pop("flash"))
    pages=dict(zip(NAV,[panorama,route_page,learning,skills_page,knowledge_page,activity_page,discovery_page,day_page,import_page,credentials_page,settings_page]))
    pages[page](service)
    dialog=st.session_state.get("active_dialog")
    if dialog:
        if dialog["kind"]=="track":
            add_track_dialog(service)
        elif dialog["kind"]=="session":
            session_dialog(service,**dialog["kwargs"])
