"""Small presentation helpers. Escape every user-provided value in custom HTML."""
from html import escape
import streamlit as st

CSS = """
<style>
:root{--ink:#20352f;--green:#23684f;--paper:#f6f7f2;--muted:#778078}
.stApp{background:var(--paper)}
[data-testid="stSidebar"]{background:#eef1e9;border-right:1px solid #dfe4d7}
[data-testid="stSidebar"] h2{font-family:Georgia,serif;font-size:1.8rem!important}
.block-container{max-width:1440px;padding-top:2rem;padding-bottom:3rem}
h1,h2,h3{font-family:Georgia,'Times New Roman',serif!important;font-weight:400!important;letter-spacing:-.035em}
h1{font-size:3.2rem!important;line-height:1.1!important}h2{font-size:2rem!important}
.eyebrow{font-size:.69rem;font-weight:700;letter-spacing:.18em;color:#65806b;margin-bottom:14px;text-transform:uppercase}
.intro{font-size:1.04rem;color:#6d786e;max-width:740px;line-height:1.7;margin-bottom:1.6rem}
.hero{background:#e5ecde;border-radius:22px;padding:28px 32px;margin:12px 0 24px;border:1px solid #dbe3d2}
.metric-grid{display:grid;grid-template-columns:repeat(var(--metric-count,4),minmax(0,1fr));gap:16px}
.hero h2{margin:5px 0 12px;font-size:2.25rem!important}.hero p{color:#50634f;margin:0;line-height:1.7}
.metric{background:#fffefa;border:1px solid #e0e5d8;border-radius:18px;padding:20px 22px;margin-bottom:18px;min-height:150px}
.metric .label{font-size:.75rem;color:#73806f}.metric .value{font-family:Georgia,serif;font-size:1.85rem;line-height:1.6;color:#244b39;white-space:nowrap}.metric .sub{font-size:.72rem;color:#80897c}
.pill{display:inline-block;padding:4px 10px;background:#edf1e5;color:#49644c;border-radius:20px;font-size:.7rem;margin:2px 5px 6px 0}
.small{font-size:.78rem;color:#76816f}.knowledge{border-radius:16px;padding:19px 22px;border:1px solid #dce2d6;margin-bottom:10px}
.knowledge h3{font-size:1.35rem!important;margin:2px 0 10px}.knowledge p{font-size:.79rem;color:#62715f;margin:4px 0}
.stButton button,.stFormSubmitButton button{border-radius:10px;min-height:2.6rem}
[data-testid="stVerticalBlockBorderWrapper"]>div{border-radius:18px}
[data-testid="stMetricValue"]{font-family:Georgia,serif}
[data-testid="stSidebar"] [data-testid="stRadio"] label p{font-size:.86rem}
@media(max-width:700px){h1{font-size:2.35rem!important}.block-container{padding:4.5rem 1rem 2rem}.hero{padding:21px}.metric{min-height:110px;padding:16px}.metric-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.metric .value{font-size:1.65rem}}
</style>
"""


def e(value):
    return escape(str(value))


def heading(eyebrow, title, description):
    st.markdown(f"<div class='eyebrow'>{e(eyebrow)}</div><h1>{e(title)}</h1><div class='intro'>{e(description)}</div>", unsafe_allow_html=True)


def hero(label, title, body):
    st.markdown(f"<div class='hero'><div class='eyebrow'>{e(label)}</div><h2>{e(title)}</h2><p>{e(body)}</p></div>", unsafe_allow_html=True)


def metrics(items):
    cards="".join(f"<div class='metric'><div class='label'>{e(label)}</div><div class='value'>{e(value)}</div><div class='sub'>{e(sub)}</div></div>" for label,value,sub in items)
    st.markdown(f"<div class='metric-grid' style='--metric-count:{len(items)}'>{cards}</div>",unsafe_allow_html=True)


def pills(values):
    st.markdown("".join(f"<span class='pill'>{e(v)}</span>" for v in values), unsafe_allow_html=True)


def minutes(value):
    if value is None:
        return "Por estimar"
    h, m = divmod(int(value), 60)
    return f"{h} h {m:02d} min" if h else f"{m} min"


KIND = {"course": "Curso", "certification": "Certificación", "topic": "Tema / ruta", "project": "Proyecto", "lab": "Laboratorio", "paper": "Paper", "pack": "Learning Pack"}
STATUS = {"planned": "Por empezar", "active": "En curso", "paused": "En pausa", "completed": "Completado", "archived": "Archivado"}
ENERGY = {"low": "Con calma", "medium": "A buen ritmo", "high": "Con energía"}
ACTIVITY = {"study": "Estudio", "review": "Repaso", "work_practice": "Práctica en el trabajo"}
RATING = {None: "Sin valorar retención", "again": "Necesito volver a verlo", "hard": "Me costó", "good": "Lo recordé", "easy": "Lo expliqué con facilidad"}
