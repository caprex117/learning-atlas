import json
from copy import deepcopy
from pathlib import Path

from streamlit.testing.v1 import AppTest

from atlas.app import NAV, NAV_ICONS
from atlas.models import ImportProposal,TrackDraft
from atlas import domain
from atlas.repository import MemoryRepository


def start_demo():
    app=AppTest.from_file(Path(__file__).resolve().parents[1]/"streamlit_app.py",default_timeout=45).run()
    assert not app.exception
    app.button(key="enter_demo").click().run()
    assert not app.exception
    return app


def goto(app,page):
    aliases={'Mi aprendizaje':('Dashboard','My Learning'),'Habilidades':('Dashboard','Abilities'),'Mi ruta':('Learning Roadmap',None),'Importar documentos':('Import',None),'Descubrir':('Learning Radar',None)}
    page,section=aliases.get(page,(page,None))
    app.button(key='nav_'+NAV_ICONS[NAV.index(page)]).click().run()
    if section:
        app.button_group(key='dashboard_section').set_value(section).run()
    return app


def test_all_pages_render_without_errors():
    app=start_demo()
    for page in NAV:
        goto(app,page)
        assert not app.exception, (page,[x.message for x in app.exception])
    goto(app,'Habilidades')
    assert not app.exception
    assert any('Descargar todas mis habilidades' in b.proto.label for b in app.get('download_button'))


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
    goto(app,"Mi aprendizaje")
    unit=domain.track_units(repo.data,track["id"])[0]
    app.checkbox(key="unit_"+unit["id"]).check().run()
    assert not app.exception
    assert domain.progress(repo.data,track["id"])["percent"]==50


def test_import_manual_json_review_then_save():
    app=start_demo()
    goto(app,"Importar documentos")
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


def test_catalog_review_then_adopt_to_route_and_filter():
    app=start_demo()
    goto(app,'Descubrir')
    app.button(key='catalog_seed').click().run()
    assert not app.exception
    repo=app.session_state['repository']
    assert len(repo.data['opportunities'])==54
    assert not any(b.key=='catalog_seed' for b in app.button)
    assert next(s for s in app.selectbox if s.label=='Ordenar').value=='Prioridad personal'
    assert any('Descargar catálogo completo' in b.proto.label for b in app.get('download_button'))
    app.text_input(key='catalog_search').set_value('Primer mapa de integración').run()
    item=next(o for o in repo.data['opportunities'] if 'Primer mapa' in o['title'])
    oid=item['id']
    before=len(repo.data['learning_tracks'])
    # A form must be submittable before checkbox state is sent to the server.
    submit=next(b for b in app.button if b.label=='Añadir aprendizaje')
    assert not submit.disabled
    submit.click().run()
    assert len(repo.data['learning_tracks'])==before
    app.checkbox(key='catreview_'+oid).check()
    phase=repo.data['goal_phases'][0]['id']
    app.selectbox(key='catphase_'+oid).set_value(phase)
    next(b for b in app.button if b.label=='Añadir aprendizaje').click().run()
    assert not app.exception, [x.message for x in app.exception]
    assert len(repo.data['learning_tracks'])==before+1
    choice=next(c for c in repo.data['opportunity_choices'] if c['opportunity_id']==oid)
    assert any(r['track_id']==choice['track_id'] and r['phase_id']==phase for r in repo.data['phase_tracks'])
    assert domain.progress(repo.data,choice['track_id'])['percent']==0
    goto(app,'Mi ruta')
    assert not app.exception


def test_catalog_missing_migration_shows_setup_help():
    app=start_demo()
    repo=app.session_state['repository']
    del repo.data['opportunities']
    goto(app,'Descubrir')
    assert not app.exception
    assert any('002_discovery_catalog.sql' in i.value for i in app.info)


def test_research_dialog_cancel_does_not_call_api(monkeypatch):
    from atlas import catalog
    from atlas.service import LearningService
    from atlas.catalog_models import defaults
    from uuid import uuid4
    app=start_demo()
    repo=app.session_state['repository'];repo.is_demo=False
    app.secrets['tavily']={'api_key':'fake-tavily'}
    app.secrets['gemini']={'api_key':'fake-gemini','model':'fake-model'}
    catalog.save_settings(LearningService(repo),{**defaults(),'external_consent':True},str(uuid4()))
    calls=[]
    def fake_refresh(*args,**kwargs):
        calls.append(True)
        return {'added':0,'changed':0,'checked':0}
    monkeypatch.setattr(catalog,'refresh',fake_refresh)
    goto(app,'Learning Radar')
    app.button(key='catalog_refresh').click().run()
    assert not calls and not app.exception
    app.button(key='cancel_research').click().run()
    assert not calls and not app.exception
    app.button(key='catalog_refresh').click().run()
    app.button(key='confirm_research').click().run()
    assert calls==[True] and not app.exception


def test_import_assistant_prepares_draft_before_any_database_write(monkeypatch):
    from atlas import assistant
    app=start_demo()
    repo=app.session_state['repository'];repo.is_demo=False
    app.secrets['gemini']={'api_key':'fake-gemini','model':'fake-model'}
    proposal=ImportProposal(tracks=[TrackDraft(title='Conversational course',kind='course')])
    monkeypatch.setattr(assistant,'converse',lambda *a,**k:assistant.Reply(message='Revisa la propuesta.',proposal=proposal))
    goto(app,'Import')
    app.text_area(key='assistant_import_message').set_value('Quiero organizar un curso')
    app.checkbox(key='assistant_import_consent').check()
    next(b for b in app.button if b.label=='Enviar a Gemini').click().run()
    assert not app.exception
    assert not repo.data['import_jobs']
    app.button(key='assistant_to_import').click().run()
    assert not app.exception
    assert 'Conversational course' in app.text_area(key='proposal_editor').value
    assert not repo.data['import_jobs']


def test_credentials_assistant_table_requires_explicit_review(monkeypatch):
    from atlas import assistant
    from atlas.credential_drafts import CredentialDraft
    app=start_demo();repo=app.session_state['repository'];repo.is_demo=False
    app.secrets['gemini']={'api_key':'fake-gemini','model':'fake-model'}
    original=len(repo.data['credentials'])
    monkeypatch.setattr(assistant,'converse',lambda *a,**k:assistant.Reply(message='Revisa la tabla.',credentials=[CredentialDraft(official_name='UI certificate',issuer='UI provider',credential_code='ABC-123')]))
    goto(app,'Credentials')
    app.text_area(key='assistant_credentials_message').set_value('Ya obtuve este certificado')
    app.checkbox(key='assistant_credentials_consent').check()
    next(b for b in app.button if b.label=='Enviar a Gemini').click().run()
    assert not app.exception
    assert app.button(key='save_credentials_batch').disabled and len(repo.data['credentials'])==original
    next(c for c in app.checkbox if c.label.startswith('Revisé esta tabla')).check().run()
    app.button(key='save_credentials_batch').click().run()
    assert not app.exception and len(repo.data['credentials'])==original+1


def test_edit_skill_from_abilities_cancel_then_save_and_reopen():
    app = start_demo()
    repo = app.session_state["repository"]
    skill = next(s for s in repo.data["skills"] if domain.skill_stats(repo.data, s["id"])["minutes"])
    skill_id = skill["id"]
    prefix = "edit_skill_" + skill_id
    before = deepcopy(repo.data)
    goto(app, "Habilidades")
    app.button(key="edit_skill_button_"+skill_id).click().run()
    assert not app.exception
    app.text_input(key=prefix+"_name").set_value("No guardar")
    next(b for b in app.button if b.label == "Cancelar").click().run()
    assert not app.exception and repo.data == before
    app.button(key="edit_skill_button_"+skill_id).click().run()
    assert app.text_input(key=prefix+"_name").value == skill["name"]
    app.text_input(key=prefix+"_name").set_value("Programación aplicada a mis proyectos")
    app.text_area(key=prefix+"_definition").set_value("Crear y comprobar soluciones reproducibles.")
    # AppTest cannot serialize newly typed selectbox options. Exercise selection
    # here; new-area creation is covered against both service repositories.
    existing_area = next(a["name"] for a in repo.data["areas"] if a["id"] != skill["area_id"])
    app.selectbox(key=prefix+"_area").select(existing_area)
    next(b for b in app.button if b.label == "Guardar cambios").click().run()
    assert not app.exception, [error.message for error in app.exception]
    updated = domain.by_id(repo.data["skills"])[skill_id]
    assert updated["name"] == "Programación aplicada a mis proyectos"
    assert domain.by_id(repo.data["areas"])[updated["area_id"]]["name"] == existing_area
    assert domain.skill_stats(repo.data, skill_id) == domain.skill_stats(before, skill_id)
    app.button(key="edit_skill_button_"+skill_id).click().run()
    assert app.text_input(key=prefix+"_name").value == updated["name"]
    assert app.selectbox(key=prefix+"_area").value == existing_area


def test_create_from_roadmap_and_shared_progress_in_two_phases():
    from atlas.service import LearningService
    from uuid import uuid4
    app = start_demo()
    repo = app.session_state["repository"]
    phase, second_phase = repo.data["goal_phases"][:2]
    goto(app, "Learning Roadmap")
    app.button(key="phase_create_"+phase["id"]).click().run()
    app.text_input(key="newtitle").set_value("Mi proyecto desde una fase")
    app.text_input(key="newarea").set_value("Python")
    app.text_area(key="newunits").set_value("Leer CSV\nValidar filas")
    next(b for b in app.button if b.label == "Crear aprendizaje").click().run()
    assert not app.exception
    track = next(t for t in repo.data["learning_tracks"] if t["title"] == "Mi proyecto desde una fase")
    LearningService(repo).link_phase(second_phase["id"], [track["id"]], str(uuid4()))
    app.run()
    unit = domain.track_units(repo.data, track["id"])[0]
    first_key = "route_unit_"+phase["id"]+track["id"]+unit["id"]
    second_key = "route_unit_"+second_phase["id"]+track["id"]+unit["id"]
    app.checkbox(key=first_key).check().run()
    assert not app.exception and app.checkbox(key=second_key).value
    assert domain.progress(repo.data, track["id"])["percent"] == 50
    app.checkbox(key=second_key).uncheck().run()
    assert not app.exception and not app.checkbox(key=first_key).value
    app.checkbox(key=first_key).check().run()
    app.button(key="phase_open_"+phase["id"]+track["id"]).click().run()
    assert not app.exception
    assert app.selectbox(key="learning_selected").value == track["id"]
    assert app.checkbox(key="unit_"+unit["id"]).value
    app.checkbox(key="unit_"+unit["id"]).uncheck().run()
    goto(app, "Learning Roadmap")
    assert not app.exception and not app.checkbox(key=first_key).value


def test_session_edit_prefilled_cancel_save_and_preserve_original():
    app = start_demo()
    repo = app.session_state["repository"]
    old = deepcopy(repo.data["study_sessions"][0])
    before = deepcopy(repo.data)
    total = domain.effort(repo.data)
    goto(app, "Learning Log")
    app.button(key="edit_session_"+old["id"]).click().run()
    prefix = "sess_"+old["id"]+"_"
    assert app.number_input(key=prefix+"duration").value == old["duration_minutes"]
    assert app.text_area(key=prefix+"notes").value == old["notes"]
    app.number_input(key=prefix+"duration").set_value(12)
    next(b for b in app.button if b.label == "Cancelar").click().run()
    assert repo.data == before
    app.button(key="edit_session_"+old["id"]).click().run()
    assert app.number_input(key=prefix+"duration").value == old["duration_minutes"]
    app.number_input(key=prefix+"duration").set_value(12)
    app.text_input(key=prefix+"reason").set_value("Anoté demasiados minutos")
    next(b for b in app.button if b.label == "Guardar corrección").click().run()
    assert not app.exception and not app.error
    assert domain.effort(repo.data) == total-old["duration_minutes"]+12
    assert domain.by_id(repo.data["study_sessions"])[old["id"]]["voided"]
    assert len(repo.data["study_sessions"]) == len(before["study_sessions"])+1


def test_phase_selector_hides_old_finished_and_toggle_restores_it():
    from atlas.service import Batch, LearningService
    from datetime import timedelta
    from uuid import uuid4
    app = start_demo()
    repo = app.session_state["repository"]
    service = LearningService(repo)
    m = repo.data["milestones"][0]
    b = Batch(service.data)
    b.put("milestones", {**m, "accepted_on": (service.current-timedelta(days=3)).isoformat()})
    service._commit(b, str(uuid4()), {"action": "test_earlier_completion"})
    goto(app, "Learning Log")
    next(b for b in app.button if b.label == "Registrar una sesión").click().run()
    phases = next(s for s in app.selectbox if s.label == "Fase de la ruta (opcional)")
    assert not any("finalizada" in option for option in phases.options)
    app.checkbox(key="sess_finished").check().run()
    assert not app.exception
    phases = next(s for s in app.selectbox if s.label == "Fase de la ruta (opcional)")
    assert any("finalizada" in option for option in phases.options)


def test_empty_learning_explains_route_and_filters_do_not_claim_library_empty():
    app = start_demo()
    goto(app, "Mi aprendizaje")
    app.text_input(key="learning_search").set_value("Nothing-matches-123").run()
    assert any("coincidan con estos filtros" in i.value for i in app.info)
    repo = app.session_state["repository"]
    repo.data = MemoryRepository().data
    app.run()
    assert not app.exception
    assert any("Tener una ruta con fases no crea" in i.value for i in app.info)
