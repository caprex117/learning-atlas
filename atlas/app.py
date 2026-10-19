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

NAV = ["Dashboard", "Learning Roadmap", "Garden of Knowledge", "Learning Log", "Learning Radar", "Focus Plan", "Import", "Credentials", "Profile & Preferences"]
NAV_ICONS = ["dashboard", "route", "yard", "history", "explore", "timer", "upload_file", "workspace_premium", "tune"]


def navigate(page, section=None):
    st.session_state.navigation = page
    if page!='Learning Radar':
        st.session_state.pop('catalog_confirm_open',None)
    if section:
        st.session_state.dashboard_section = section


def dashboard(service):
    section = st.segmented_control("Dentro de Dashboard", ["Overview", "My Learning", "Abilities"],
                                   default="Overview", key="dashboard_section", selection_mode="single")
    {"Overview": panorama, "My Learning": learning, "Abilities": skills_page}.get(section, panorama)(service)



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
                           help="Sin unidades, el progreso aparecerá como ‘Sin definir’. Estas lecciones tienen el mismo peso. Para organizar un programa con módulos, usa Import y revisa la propuesta antes de guardarla.")
    topics = st.text_input("Temas cubiertos · separados por comas", key=prefix+"topics")
    notes = st.text_area("Notas", key=prefix+"notes", height=80)
    return dict(title=title, kind=kind, area=area, official_name=official, platform=platform, issuer=issuer,
                source_url=url or None, notes=notes,
                units=[{"key": f"u{i}", "title": line.strip()} for i, line in enumerate(lessons.splitlines()) if line.strip()],
                topics=[{"name": x.strip()} for x in dict.fromkeys(topics.split(",")) if x.strip()])


@st.dialog("Un nuevo punto de partida", width="large", on_dismiss=dismiss_dialog)
def add_track_dialog(service, phase_id=None):
    if phase_id:
        phase = domain.by_id(service.data["goal_phases"])[phase_id]
        st.info("Se creará en My Learning y quedará vinculado a esta fase: " + phase["title"])
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
            return service.create_track(TrackDraft.model_validate(payload), rid, status=status, favorite=favorite, phase_id=phase_id)
        save_and_refresh("newtrack", create, "Tu aprendizaje ya tiene un lugar.")


@st.dialog("Editar habilidad", width="large", on_dismiss=dismiss_dialog)
def edit_skill_dialog(service, skill_id):
    skill = domain.by_id(service.data["skills"]).get(skill_id)
    if not skill:
        st.info("Esta habilidad ya no está disponible. Cierra esta ventana y actualiza tus datos.")
        return
    areas = domain.by_id(service.data["areas"])
    current_area = areas[skill["area_id"]]["name"]
    names = sorted((a["name"] for a in areas.values()), key=str.casefold)
    prefix = "edit_skill_" + skill_id
    st.caption("Corrige los datos de esta habilidad. Sus cursos, sesiones y autoevaluaciones seguirán vinculados; para una capacidad diferente, añade otra habilidad.")
    with st.form(prefix):
        name = st.text_input("Nombre de la habilidad", skill["name"], max_chars=180, key=prefix+"_name")
        definition = st.text_area("Descripción · qué significa poder hacerlo", skill.get("definition", ""), max_chars=700, key=prefix+"_definition")
        area = st.selectbox("Área de la habilidad", names, index=names.index(current_area), accept_new_options=True,
                            key=prefix+"_area", help="Selecciona un área existente o escribe una nueva y pulsa Enter.")
        st.caption("El área clasifica esta habilidad. Cada sesión conserva el área con la que la registraste.")
        a, b = st.columns(2)
        submitted = a.form_submit_button("Guardar cambios", type="primary", width="stretch")
        cancelled = b.form_submit_button("Cancelar", width="stretch")
    if cancelled:
        dismiss_dialog()
        st.rerun()
    if submitted:
        save_and_refresh(prefix, lambda rid: service.update_skill(skill_id, name, definition, area or "", rid),
                         "Habilidad actualizada. Se conservaron su práctica y sus relaciones.")


@st.dialog("Tu sesión de aprendizaje", width="large", on_dismiss=dismiss_dialog)
def session_dialog(service, track_id=None, topic_id=None, block=None, session_id=None, phase_id=None):
    data = service.data
    old = domain.by_id(data["study_sessions"]).get(session_id) if session_id else None
    if session_id and (not old or old.get("voided")):
        st.info("Esta sesión ya fue corregida o anulada. Cierra esta ventana y abre el registro vigente.")
        return
    prefix = "sess_" + (session_id+"_" if session_id else "")
    events = [e for e in data["topic_events"] if old and e.get("session_id") == session_id and not e.get("voided")]
    if old:
        track_id = old.get("track_id")
        st.caption("Corrige la sesión sin escribirla de nuevo. La anterior quedará anulada en el historial; se conservarán sus trabajos, adjuntos y vínculo con Focus Plan. Sólo contará el tiempo corregido.")
    if block:
        track_id, topic_id = block.get("track_id"), block.get("topic_id")
        st.caption("Bloque del plan: " + block["title"])
    tracks = [t for t in data["learning_tracks"] if t["status"] != "archived" or t["id"] == track_id]
    # Outside the form: changes can update the suggested area and coverage immediately.
    selected_track = select_record("Aprendizaje asociado", tracks, field="title", optional=True, default=track_id, key=prefix+"track")
    st.caption("Selecciona el curso o proyecto en el que trabajaste. ‘Sin asociar’ sirve para práctica independiente o trabajo; esos minutos también cuentan.")
    show_finished = st.checkbox("Mostrar finalizadas y rutas archivadas", key=prefix+"finished")
    st.caption("Las fases pendientes y las finalizadas hoy o ayer aparecen por defecto. Activa esta opción para registrar trabajo anterior; no se borra ninguna fase.")
    phases = domain.session_phases(data, service.current, show_finished=show_finished, keep_id=old.get("phase_id") if old else phase_id)
    track = domain.by_id(tracks).get(selected_track)
    topic = domain.by_id(data["topics"]).get(topic_id)
    area_default = old["area_id"] if old else track["area_id"] if track else topic["area_id"] if topic else None
    selected_topics = [e["topic_id"] for e in events] if old else [topic_id] if topic_id else []
    selected_skills = [l["skill_id"] for l in data["session_skills"] if l["session_id"] == session_id] if old else (
        [l["skill_id"] for l in data["track_skills"] if l["track_id"] == selected_track] +
        [l["skill_id"] for l in data["topic_skills"] if l["topic_id"] == topic_id])
    context = prefix + str(selected_track) + str(topic_id)
    area_names = {a["name"]: a["id"] for a in data["areas"]}
    area_label = next((name for name, aid in area_names.items() if aid == area_default), None)
    with st.form(prefix+"form"):
        a, b, c = st.columns(3)
        occurred = a.date_input("Fecha", domain.as_date(old["occurred_on"]) if old else service.current, max_value=service.current, key=prefix+"date")
        duration = b.number_input("Minutos reales", 1, 1440, old["duration_minutes"] if old else block["planned_minutes"] if block else 25, step=1, key=prefix+"duration")
        activity = c.selectbox("Actividad", list(ACTIVITY), index=list(ACTIVITY).index(old["activity_type"]) if old else 1 if topic_id else 0, format_func=ACTIVITY.get, key=prefix+"activity")
        area_name = st.selectbox("Área de esta sesión", list(area_names), index=list(area_names).index(area_label) if area_label else None,
                                 accept_new_options=True, key=context+"_area", placeholder="Escoge un área o escribe una nueva…",
                                 help="Es la categoría de esta práctica, por ejemplo Python o Redes. Para añadir una, escribe el nombre y pulsa Enter.")
        linked_phases = [r["phase_id"] for r in data["phase_tracks"] if r["track_id"] == selected_track and r["phase_id"] in domain.by_id(phases)]
        phase_id = select_record("Fase de la ruta (opcional)", phases, field="label", optional=True,
                                 default=old.get("phase_id") if old else phase_id or (linked_phases[0] if len(linked_phases)==1 else None),
                                 key=context+"_phase_"+str(show_finished))
        topic_ids = multi_records("Temas practicados", data["topics"], default=selected_topics, key=context+"_topics")
        skill_ids = multi_records("Habilidades practicadas", data["skills"], default=list(dict.fromkeys(selected_skills)), key=context+"_skills")
        st.caption("El tiempo se reparte entre las habilidades seleccionadas; nunca se multiplica. Los temas no cuentan como aprendidos automáticamente.")
        rating = st.selectbox("Cómo lo recordaste · sólo para repaso o práctica", list(RATING), format_func=RATING.get,
                              index=list(RATING).index(events[0].get("rating")) if events else 0, key=prefix+"rating")
        notes = st.text_area("Qué hiciste o descubriste", value=old.get("notes", "") if old else "", key=prefix+"notes", max_chars=3000)
        if old:
            evidence_title, evidence_url = "", None
            reason = st.text_input("Qué estás corrigiendo", key=prefix+"reason", max_chars=300)
            st.caption("Los trabajos y sus habilidades asociadas conservan su contenido. Sus enlaces seguirán funcionando, incluso si ya respaldan un entregable de Roadmap.")
        else:
            evidence_title = st.text_input("Entregable / evidencia (opcional)", key=prefix+"evidence", max_chars=180)
            evidence_url = st.text_input("Enlace a la evidencia (opcional)", key=prefix+"url")
        a, b = st.columns(2)
        submitted = a.form_submit_button("Guardar corrección" if old else "Guardar sesión", type="primary")
        cancelled = b.form_submit_button("Cancelar")
    if cancelled:
        dismiss_dialog()
        st.rerun()
    if submitted:
        def save(rid):
            draft = SessionDraft(occurred_on=occurred, duration_minutes=duration, area_id=area_names.get(area_name, ""),
                track_id=selected_track, phase_id=phase_id, topic_ids=topic_ids, skill_ids=skill_ids, activity_type=activity,
                rating=rating, notes=notes, evidence_title=evidence_title, evidence_url=evidence_url or None,
                plan_block_id=block["id"] if block else None)
            new_area = None if area_name in area_names else area_name or ""
            if old:
                return service.update_session(session_id, draft, reason, rid, area_name=new_area)
            return service.record_session(draft, rid, area_name=new_area)
        save_and_refresh(prefix+"save", save, "Sesión corregida; sólo cuenta el registro vigente." if old else "Sesión registrada. Tus métricas ya incluyen esta práctica.")


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
            notes = st.text_area("Notas y materiales", track.get("notes", ""),
                                 help="Guarda un resumen propio y enlaces a tus notas o carpetas de Drive. La app conserva el texto; todavía no abre ni lee automáticamente esas carpetas.")
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
    heading("DASHBOARD · OVERVIEW", "Tu aprendizaje de un vistazo.", "Consulta tu progreso, tiempo de práctica y constancia. Abre My Learning para gestionar cursos y proyectos, o Abilities para ver las habilidades relacionadas con lo que haces.")
    with st.expander("Cómo se conectan las secciones · un ejemplo con SQL"):
        st.markdown("""
| Sección | Para qué la usas | Ejemplo |
|---|---|---|
| **My Learning** | Organizar cada curso o proyecto y completar sus lecciones. | Curso de SQL: 3 de 10 lecciones completadas. |
| **Learning Roadmap** | Reunir esos aprendizajes en fases hacia una meta con fechas. | Aprender SQL y Python para construir un dashboard en tres meses. |
| **Focus Plan** | Elegir unos bloques pequeños para el tiempo que tienes hoy. | Dedicar 25 minutos a la próxima lección de SQL. |
| **Learning Log** | Registrar lo que hiciste y cuánto tiempo real te tomó. | Hoy practiqué consultas SQL durante 30 minutos. |
| **Abilities** | Ver qué habilidades cubres, cuáles practicas y de dónde vienen. | Consultar datos: relacionada con el curso y con la sesión registrada. |
""")
        st.caption("Puedes empezar con un solo curso, sin crear una ruta. Añádelo con ‘Añadir aprendizaje’, desde Learning Radar o mediante Import. Planificar un bloque no registra actividad: después confirmas lo que hiciste. Marcar una lección y registrar minutos son acciones distintas.")
    with st.expander("Recorrido completo · tu proyecto de Python, paso a paso"):
        guide = (Path(__file__).resolve().parent.parent / "docs" / "WALKTHROUGH.md").read_text(encoding="utf-8")
        st.download_button("Descargar este recorrido", guide, "Learning-Atlas-recorrido.md", mime="text/markdown")
        st.markdown(guide)
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
        hero("EMPIEZA CON LO QUE IMPORTA", "Dale un lugar a tu próximo paso.", "Añade un aprendizaje o abre Learning Roadmap para cargar el plan Factory Enablement. Tu avance empieza desde cero.")
    st.subheader("Tu mesa de trabajo")
    tracks = sorted(active, key=lambda t: (not t.get("favorite"), t["priority"], t["title"]))[:4]
    if tracks:
        cols = st.columns(2)
        for i, track in enumerate(tracks):
            with cols[i % 2]:
                track_card(service, track)
    else:
        st.info("Aún no hay aprendizajes en curso. Puedes activar uno desde Dashboard → My Learning.")
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


def _open_learning(track_id):
    st.session_state.learning_search = ""
    st.session_state.learning_status = None
    st.session_state.learning_favorites = False
    st.session_state.learning_selected = track_id
    navigate("Dashboard", "My Learning")


def _route_unit_change(service, unit_id, key):
    action(key, lambda rid: service.toggle_unit(unit_id, st.session_state[key], rid))


def learning(service):
    heading("DASHBOARD · MY LEARNING", "Lo que eliges aprender.", "Aquí están tus cursos, certificaciones y proyectos: pendientes, en curso y terminados. Abre uno para organizar sus lecciones, marcar lo completado y registrar práctica. Los temas que ya comprendiste viven en Garden of Knowledge.")
    st.caption("Cada ficha reúne un aprendizaje y sus lecciones. Puedes añadirlo manualmente, traerlo de Learning Radar o prepararlo en Import. Learning Roadmap te permite agrupar varios de estos aprendizajes en fases hacia una meta.")
    a, b, c = st.columns([2, 1, 1])
    query = a.text_input("Buscar", placeholder="Python, redes, una plataforma…", key="learning_search")
    state = b.selectbox("Estado", [None]+list(STATUS), format_func=lambda v: "Todos" if v is None else STATUS[v], key="learning_status")
    favorite = c.checkbox("Sólo favoritos", key="learning_favorites")
    rows = [t for t in service.data["learning_tracks"] if (state is None or t["status"] == state) and (not favorite or t.get("favorite"))
            and query.casefold() in (t["title"]+" "+t.get("platform", "")+" "+t.get("official_name", "")).casefold()]
    rows = sorted(rows, key=lambda t: (not t.get("favorite"), t["priority"], t["title"]))
    if rows:
        labels = {t["id"]: t["title"] for t in rows}
        if st.session_state.get("learning_selected") not in labels:
            st.session_state.learning_selected = None
        selected = st.selectbox("Abrir un aprendizaje", [None]+list(labels),
                                format_func=lambda value: "Todos los resultados" if value is None else labels[value], key="learning_selected")
        if selected:
            rows = [t for t in rows if t["id"] == selected]
    for track in rows:
        track_card(service, track, detail=True)
    if not rows:
        if service.data["learning_tracks"]:
            st.info("No hay aprendizajes que coincidan con estos filtros. Borra la búsqueda o cambia Estado y Sólo favoritos.")
        else:
            st.info("Aún no has añadido cursos o proyectos a tu biblioteca. Tener una ruta con fases no crea automáticamente sus aprendizajes. Puedes crear uno desde esa fase y aparecerá aquí también.")
            a, b = st.columns(2)
            a.button("Añadir mi primer aprendizaje", on_click=open_dialog, args=("track",), type="primary")
            b.button("Ir a Learning Roadmap", on_click=navigate, args=("Learning Roadmap",))


def route_page(service):
    heading("LEARNING ROADMAP", "Un plan hacia tu próxima meta.", "Organiza tu objetivo en fases con fechas y resultados concretos. Vincula aprendizajes a cada fase y confirma los entregables que terminaste; el tiempo real se registra en Learning Log.")
    st.caption("Tu ruta combina cursos o proyectos hacia una meta. Puedes crearlos desde una fase o vincular los que ya existen. Las lecciones que marques aquí y en My Learning son las mismas: no tienes que completarlas dos veces. El entregable confirma el resultado final de la fase.")
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
                        p = domain.progress(data, learning_track["id"])
                        with st.expander("Aprendizaje · " + learning_track["title"]):
                            st.progress((p["percent"] or 0)/100, text=f"{p['done']}/{p['total']} unidades · {p['percent']}%" if p["percent"] is not None else "Sin unidades definidas")
                            st.caption("Este avance es el mismo de My Learning. Marcar una lección no registra tiempo ni acepta el entregable de la fase.")
                            done = {row["unit_id"] for row in data["unit_progress"]}
                            for unit in domain.track_units(data, learning_track["id"]):
                                key = "route_unit_"+phase["id"]+learning_track["id"]+unit["id"]
                                was = unit["id"] in done
                                # Bind the widget to persisted progress: the same unit can be shown in two phases.
                                st.session_state[key] = was
                                st.checkbox(unit["title"] + (" · opcional" if not unit["required"] else ""), key=key,
                                            disabled=goal["status"] != "active", on_change=_route_unit_change,
                                            args=(service, unit["id"], key))
                            a, b = st.columns(2)
                            a.button("Registrar práctica", key="phase_session_"+phase["id"]+learning_track["id"],
                                     on_click=open_dialog, args=("session",), kwargs={"track_id": learning_track["id"], "phase_id": phase["id"]})
                            b.button("Abrir en My Learning", key="phase_open_"+phase["id"]+learning_track["id"],
                                     on_click=_open_learning, args=(learning_track["id"],))
                if not linked_ids:
                    st.caption("Esta fase tiene un resultado previsto, pero todavía no tiene cursos o proyectos vinculados. Crea uno con sus lecciones o elige uno de tu biblioteca.")
                st.button("Crear aprendizaje para esta fase", key="phase_create_"+phase["id"], disabled=goal["status"] != "active",
                          on_click=open_dialog, args=("track",), kwargs={"phase_id": phase["id"]})
                with st.expander("Elegir aprendizajes para esta fase"):
                    with st.form('phase_links_'+phase['id']):
                        labels={t['id']:t['title'] for t in data['learning_tracks']}
                        selected=st.multiselect('Cursos o proyectos relacionados',list(labels),default=list(linked_ids),format_func=labels.get,key='phase_selection_'+phase['id'])
                        st.caption('Puedes vincular aquí lo que hayas creado en My Learning o Import. Esto organiza la ruta sin marcar progreso.')
                        if st.form_submit_button('Guardar aprendizajes de la fase',disabled=goal['status']!='active'):
                            save_and_refresh('phase_links_'+phase['id'],lambda rid,pid=phase['id'],chosen=selected:service.link_phase(pid,chosen,rid))
                if ms:
                    with st.expander("Entregable · " + ms["title"]):
                        st.text(ms["criteria"])
                        st.caption("Marca la casilla cuando hayas terminado este resultado. Puedes asociar un trabajo registrado en Learning Log o Import, y dejar notas. Esto no completa lecciones ni añade horas.")
                        with st.form("milestone_"+ms["id"]):
                            accepted = st.checkbox("Revisé el resultado y cumple los criterios", bool(ms.get("accepted_on")))
                            evidence = select_record("Trabajo que respalda el resultado (opcional)", data["learning_evidence"], field="title", optional=True, default=ms.get("evidence_id"), key="mev_"+ms["id"])
                            notes = st.text_area("Qué comprobaste o qué queda pendiente (opcional)", ms.get("notes", ""), placeholder="Ej.: el script procesa el CSV y las pruebas pasan; falta documentarlo.")
                            if st.form_submit_button("Guardar estado del entregable"):
                                save_and_refresh("milestone_"+ms["id"], lambda rid: service.accept_milestone(ms["id"], accepted, notes, evidence, rid))
        with st.expander("Opciones avanzadas · crear otra versión de la ruta"):
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
    heading("DASHBOARD · ABILITIES", "Lo que estás aprendiendo a hacer.", "Consulta qué habilidades aparecen en tus cursos, dónde las has practicado y qué trabajos las respaldan. Estas conexiones se reúnen automáticamente a partir de tus registros; valorar tu autonomía es opcional.")
    data = service.data
    from .exports import abilities_csv
    st.download_button("Descargar todas mis habilidades · CSV", abilities_csv(data), "learning-atlas-abilities.csv", mime="text/csv", key="abilities_csv", width="stretch")
    st.caption("Ejemplo: JOIN es un tema; combinar tablas para resolver una consulta es una habilidad. Un curso indica que la cubre, una sesión registra práctica y una autoevaluación expresa tu autonomía.")
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
        details, edit = st.columns([6, 1.2])
        edit.button("Editar", icon=":material/edit:", key="edit_skill_button_"+skill["id"],
                    help="Editar habilidad", width="stretch", on_click=open_dialog, args=("skill",), kwargs={"skill_id": skill["id"]})
        with details.expander(f"{skill['name']} · {minutes(stats['minutes'])} · {stats['sessions']} sesiones"):
            st.write(skill.get("definition", ""))
            st.caption("Área: " + domain.by_id(data["areas"])[skill["area_id"]]["name"])
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
                st.write("Opcional · ¿qué puedes hacer por tu cuenta?")
                when = st.date_input("Fecha", service.current, max_value=service.current)
                level = st.selectbox("Qué puedes hacer", [0,1,2,3], format_func=lambda v:["0 · Todavía no puedo", "1 · Con guía", "2 · Por mi cuenta", "3 · Lo explico y compruebo"][v])
                context = st.text_area("Describe la tarea concreta")
                url = st.text_input("Evidencia (URL opcional)")
                st.caption("Se comparan autoevaluaciones de fechas distintas y la misma rúbrica. No equivale a una evaluación externa.")
                if st.form_submit_button("Registrar autoevaluación"):
                    save_and_refresh("assess_"+skill["id"], lambda rid: service.assess(skill["id"], when, level, context, url or None, rid))


def knowledge_page(service):
    heading("GARDEN OF KNOWLEDGE", "Cuida lo que ya aprendiste.", "Añade los temas que ya comprendiste y registra cuándo los practicas o repasas. El color te ayuda a decidir qué retomar; practicar en el trabajo también cuenta cuando lo registras.")
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
    heading("LEARNING LOG", "Un registro de tu práctica real.", "Anota cuánto tiempo estudiaste, repasaste o aplicaste algo en el trabajo. Puedes vincular la sesión a un curso, una fase, temas y habilidades. Este registro alimenta tus horas, rachas y calendario.")
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
            st.button("Editar sesión", key="edit_session_"+session["id"], on_click=open_dialog, args=("session",), kwargs={"session_id": session["id"]})
            with st.form("void_"+session["id"]):
                reason = st.text_input("Motivo de anulación")
                confirm = st.checkbox("Anular porque esta sesión no debe contar; para corregir datos usa Editar sesión")
                if st.form_submit_button("Anular sesión"):
                    if confirm:
                        save_and_refresh("void_"+session["id"], lambda rid: service.void_session(session["id"], reason, rid), "Sesión anulada. Su tiempo ya no cuenta.")
                    else:
                        st.warning("Marca la confirmación antes de anular.")
    with st.expander("Historial de correcciones y anulaciones"):
        old_sessions = [s for s in data["study_sessions"] if s.get("voided") and start <= domain.as_date(s["occurred_on"]) <= end]
        if not old_sessions:
            st.caption("No hay correcciones ni anulaciones en este período.")
        for old in sorted(old_sessions, key=lambda s: s["occurred_on"], reverse=True):
            st.write(f"{old['occurred_on']} · {minutes(old['duration_minutes'])} · {old.get('notes') or 'Sin notas'}")
            reason = old.get("void_reason", "")
            if reason.startswith("Corregida por sesión ") and ": " in reason:
                reason = "Corregida: " + reason.split(": ", 1)[1]
            st.caption(reason + " · Estos minutos ya no cuentan.")
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
    heading("FOCUS PLAN", "Decide qué hacer con el tiempo que tienes.", "Elige tus minutos disponibles y tu energía. Recibirás hasta tres bloques de lecciones pendientes o repasos, con pausas. Preparar el plan no cuenta como estudio: registra el tiempo real cuando lo hagas.")
    with st.form("dayplan"):
        a,b=st.columns(2)
        budget=a.select_slider("Tiempo disponible",[20,30,45,60,90,120],value=45,format_func=minutes)
        energy=b.selectbox("Cómo te sientes",list(ENERGY),index=1,format_func=ENERGY.get)
        if st.form_submit_button("Preparar mi plan",type="primary"):
            save_and_refresh("dayplan",lambda rid:service.save_plan(budget,energy,rid),"Plan listo. Las horas sólo se registran cuando realizas un bloque.")
    st.caption("El plan usa tus prioridades, unidades pendientes y repasos orientativos. Se genera con reglas locales, sin enviar tus datos a una IA.")
    st.caption("Un plan pendiente no se borra automáticamente. La racha se calcula con los minutos reales registrados: puedes estudiar sin terminar una lección. Marcar una lección en My Learning no registra tiempo.")
    plans=sorted([p for p in service.data["daily_plans"] if p["plan_date"]==service.current.isoformat()],key=lambda p:p.get("created_at",""),reverse=True)
    if not plans:
        hero("HOY PUEDE SER SUFICIENTE", "Una cosa pequeña, bien hecha.", "Ve a Dashboard → My Learning, abre un curso o proyecto, ponlo En curso y añade sus lecciones. También puedes registrar un tema en Garden of Knowledge: aparecerá aquí cuando corresponda repasarlo.")
        a,b=st.columns(2)
        a.button("Abrir My Learning",key="focus_to_learning",on_click=navigate,args=("Dashboard","My Learning"))
        b.button("Abrir Garden of Knowledge",key="focus_to_garden",on_click=navigate,args=("Garden of Knowledge",))
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
    heading("IMPORT", "Convierte información en un plan que puedas seguir.", "Sube un documento, escribe la información o prepara una propuesta conversando con Gemini. Revisa lo organizado antes de guardarlo: los cursos van a My Learning, las rutas con fases a Learning Roadmap y las habilidades quedan relacionadas en Abilities.")
    from .assistant_ui import render_import_assistant
    render_import_assistant(service)
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
                elif Path(uploaded.name).suffix.lower()==".txt":
                    from .assistant import proposal_from_text
                    proposal=proposal_from_text(extracted['text'])
                    if proposal:
                        st.session_state.proposal_editor=proposal.model_dump_json(indent=2)
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
    with st.expander("2 · Organizar y validar",expanded=bool(st.session_state.get("import_source") or st.session_state.get("proposal_editor"))):
        st.caption("Prepara la información con el formulario o el asistente. JSON es un archivo estructurado que permite a la app conservar lecciones y relaciones; no necesitas escribirlo.")
        with st.expander("Captura manual · preparar sin IA"):
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
        raw=st.session_state.get("proposal_editor", "")
        if raw:
            try:
                proposed=ImportProposal.model_validate_json(raw)
                st.write("Propuesta preparada: "+", ".join(t.title for t in proposed.tracks))
            except ValueError:
                st.warning("La propuesta necesita correcciones antes de guardarla.")
        with st.expander("Avanzado · formato JSON"):
            st.caption("JSON guarda campos y relaciones en texto. Úsalo sólo si quieres editar la estructura o intercambiarla con otra herramienta; el asistente y el formulario lo preparan por ti.")
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
                with st.expander("Avanzado · editar la estructura JSON"):
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
                st.caption("Consulta My Learning para los cursos, Learning Roadmap para las fases y Learning Log para los trabajos importados. El temario no se marca como aprendido automáticamente.")
            elif job.get("storage_path") and st.button("Reintentar limpieza del archivo cancelado",key="cleanup_"+job["id"]):
                answer=action("cleanup_"+job["id"],lambda rid,j=job:service.cancel_import(j["id"],rid))
                if answer:
                    st.info("Limpieza pendiente; vuelve a intentar más tarde." if answer["result"]["cleanup_pending"] else "Archivo eliminado o ya ausente.")


def credentials_page(service):
    heading("CREDENTIALS", "Tus títulos y certificados, bien organizados.", "Registra credenciales que ya obtuviste, con nombre, emisor, fechas y enlaces. Gemini puede ayudarte a preparar una tabla; tú revisas y eliges qué guardar. Una credencial no completa cursos ni registra horas automáticamente.")
    from .assistant_ui import render_credentials_assistant
    render_credentials_assistant(service)
    from .exports import credentials_csv
    data=service.data
    st.download_button("Descargar mis credenciales · CSV", credentials_csv(data["credentials"]), "learning-atlas-credentials.csv", mime="text/csv")
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
            if credential.get('program_code') or credential.get('credential_code'):
                st.caption('Programa/examen: '+(credential.get('program_code') or 'sin código')+' · ID personal: '+(credential.get('credential_code') or 'sin ID'))
            if credential.get('document_url'):
                st.link_button('Abrir mis documentos',credential['document_url'],key='cdoc_'+credential['id'])
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
        code=st.text_input("Código del examen o programa (opcional)",row.get("program_code", ""),help="Ej.: PL-300. No es el número personal de tu certificado.")
        credential_id=st.text_input("ID de tu credencial (opcional)",row.get("credential_code", ""))
        url=st.text_input("Enlace de verificación del emisor (opcional)",row.get("verification_url") or "")
        document_url=st.text_input("Enlace a tu certificado o carpeta de Drive (opcional)",row.get("document_url") or "",help="Un enlace a Drive sirve para consultar tus documentos; no equivale a verificación del emisor.")
        notes=st.text_area("Notas",row.get("notes",""))
        if st.form_submit_button("Guardar credencial",type="primary"):
            fields=dict(official_name=name,issuer=issuer,credential_type=ctype,track_id=track,earned_on=earned.isoformat() if earned else None,period_label=period,
                expires_on=expires.isoformat() if expires else None,never_expires=never,verification_url=url or None,notes=notes,program_code=code,credential_code=credential_id,document_url=document_url or None)
            save_and_refresh(key,lambda rid:service.add_credential(fields,rid,credential_id=row.get("id")))


def settings_page(service):
    heading("PROFILE & PREFERENCES", "Ajusta la app a tu ritmo y dirección.", "Configura tu disponibilidad, zona horaria y constancia diaria. Define tu enfoque para Learning Radar y descarga una copia de tus registros. Cambiar preferencias no modifica automáticamente tu ruta existente.")
    with st.form("settings"):
        name=st.text_input("Nombre de tu espacio",service.profile["display_name"])
        zone=st.text_input("Zona horaria IANA",service.profile["timezone"],help="Ejemplos: America/Puerto_Rico, America/La_Paz")
        weekly=st.number_input("Disponibilidad semanal · minutos",10,10080,service.profile["weekly_minutes"])
        threshold=st.number_input("Minutos por día para contar en la racha",1,1440,service.profile["streak_minutes"])
        st.caption("La zona horaria aplica a nuevas fechas; no cambia las fechas locales de sesiones previas. Cambiar disponibilidad no modifica las versiones de tu ruta.")
        if st.form_submit_button("Guardar preferencias",type="primary"):
            save_and_refresh("settings",lambda rid:service.settings(name,zone,weekly,threshold,rid))
    from .catalog_ui import focus_settings
    focus_settings(service)
    st.subheader("Tu copia de los datos")
    st.download_button("Exportar mis datos · JSON",export_json(service.data),"learning-atlas-export.json",mime="application/json",type="primary")
    st.caption("Incluye perfil, cursos, lecciones, rutas, sesiones, temas, habilidades, credenciales, importaciones, planes y catálogo con sus relaciones e historial; no contraseñas, tokens ni el contenido binario de adjuntos. Es una exportación de respaldo, no el formato de propuestas del importador. Descarga los adjuntos desde sus aprendizajes o evidencias.")
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
        if st.session_state.get("navigation") not in NAV:
            st.session_state.navigation="Dashboard"
        with st.container(key="navigation_menu"):
            for name, icon in zip(NAV, NAV_ICONS):
                st.button(name, icon=f":material/{icon}:", type="primary" if st.session_state.navigation==name else "tertiary",
                          key="nav_"+icon, width="stretch", on_click=navigate, args=(name,))
        page=st.session_state.navigation
        st.divider()
        st.caption(service.profile["display_name"])
        st.caption(minutes(service.profile["weekly_minutes"])+" por semana · "+("Demo" if repo.is_demo else "Conectado a Supabase"))
        if st.button("Salir de la demo" if repo.is_demo else "Cerrar sesión",width="stretch"):
            logout()
    if repo.is_demo:
        st.caption("ESPACIO DE DEMOSTRACIÓN · Datos ficticios y cambios temporales; no reflejan tu avance real.")
    if "flash" in st.session_state:
        st.success(st.session_state.pop("flash"))
    pages=dict(zip(NAV,[dashboard,route_page,knowledge_page,activity_page,discovery_page,day_page,import_page,credentials_page,settings_page]))
    pages[page](service)
    dialog=st.session_state.get("active_dialog")
    if dialog:
        if dialog["kind"]=="track":
            add_track_dialog(service,**dialog["kwargs"])
        elif dialog["kind"]=="session":
            session_dialog(service,**dialog["kwargs"])
        elif dialog["kind"]=="skill":
            edit_skill_dialog(service,**dialog["kwargs"])
