import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from atlas.app import NAV
from atlas.models import ImportProposal,TrackDraft
from atlas import domain
from atlas.repository import MemoryRepository


def start_demo():
    app=AppTest.from_file(Path(__file__).resolve().parents[1]/"streamlit_app.py",default_timeout=45).run()
    assert not app.exception
    app.button(key="enter_demo").click().run()
    assert not app.exception
    return app


def test_all_pages_render_without_errors():
    app=start_demo()
    for page in NAV:
        app.radio(key="navigation").set_value(page).run()
        assert not app.exception, (page,[x.message for x in app.exception])


def test_create_course_from_sidebar_and_complete_unit():
    app=start_demo()
    app.button(key="add_learning").click().run()
    assert not app.exception
    app.text_input(key="newtitle").set_value("Curso de prueba de interfaz")
    app.text_input(key="newarea").set_value("Testing")
    app.text_area(key="newunits").set_value("Primer paso\nSegundo paso")
    next(b for b in app.button if b.label=="Crear aprendizaje").click().run()
    assert not app.exception
    repo=app.session_state["repository"]
    track=next(t for t in repo.data["learning_tracks"] if t["title"]=="Curso de prueba de interfaz")
    assert domain.progress(repo.data,track["id"])["percent"]==0
    app.radio(key="navigation").set_value("Mi aprendizaje").run()
    unit=domain.track_units(repo.data,track["id"])[0]
    app.checkbox(key="unit_"+unit["id"]).check().run()
    assert not app.exception
    assert domain.progress(repo.data,track["id"])["percent"]==50


def test_import_manual_json_review_then_save():
    app=start_demo()
    app.radio(key="navigation").set_value("Importar documentos").run()
    proposal=ImportProposal(tracks=[TrackDraft(title="Importado desde interfaz",kind="course",units=[{"key":"u","title":"Unidad"}])])
    app.text_area(key="proposal_editor").set_value(proposal.model_dump_json()).run()
    next(b for b in app.button if b.label=="Validar y guardar borrador").click().run()
    assert not app.exception
    repo=app.session_state["repository"]
    assert len(repo.data["import_jobs"])==1
    assert not any(t["title"]=="Importado desde interfaz" for t in repo.data["learning_tracks"])
    checkbox=next(c for c in app.checkbox if c.label.startswith("Revisé el temario"))
    checkbox.check().run()
    next(b for b in app.button if b.label=="Importar lo aprobado").click().run()
    assert not app.exception
    assert any(t["title"]=="Importado desde interfaz" for t in repo.data["learning_tracks"])


def test_record_real_session_from_track():
    app=start_demo()
    repo=app.session_state["repository"]
    track=repo.data["learning_tracks"][0]
    before=domain.effort(repo.data)
    app.button(key="record_"+track["id"]).click().run()
    assert not app.exception
    next(n for n in app.number_input if n.label=="Minutos reales").set_value(37)
    next(b for b in app.button if b.label=="Guardar sesión").click().run()
    assert not app.exception
    assert domain.effort(repo.data)==before+37


def test_sign_in_and_sign_out_clear_session_data(monkeypatch):
    from types import SimpleNamespace
    import supabase
    import atlas.auth
    repo=MemoryRepository()
    repo.is_demo=False
    calls=[]
    def sign_in(credentials):
        assert credentials=={"email":"test@example.org","password":"local-test-only"}
        return SimpleNamespace(user=SimpleNamespace(id=repo.user_id),session=object())
    client=SimpleNamespace(auth=SimpleNamespace(sign_in_with_password=sign_in,sign_out=lambda options:calls.append(options)))
    def factory(url,key,options):
        assert not options.persist_session
        return client
    monkeypatch.setattr(supabase,"create_client",factory)
    monkeypatch.setattr(atlas.auth,"SupabaseRepository",lambda c,user_id:repo)
    app=AppTest.from_file(Path(__file__).resolve().parents[1]/"streamlit_app.py",default_timeout=45)
    app.secrets["supabase"]={"url":"https://test.supabase.co","key":"sb_publishable_test"}
    app.secrets["app"]={"allow_demo":False}
    app.run()
    app.text_input(key="login_email").set_value("test@example.org")
    app.text_input(key="login_password").set_value("local-test-only")
    next(b for b in app.button if b.label=="Entrar").click().run()
    assert not app.exception and not app.error
    assert not repo.data["study_sessions"] and not repo.data["learning_tracks"]
    assert app.session_state["repository"] is repo
    next(b for b in app.button if b.label=="Cerrar sesión").click().run()
    assert not app.exception
    assert calls==[{"scope":"local"}]
    assert "repository" not in app.session_state
