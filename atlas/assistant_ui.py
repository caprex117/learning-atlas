"""Conversational drafts with explicit review; no automatic database writes from AI."""
import json
from uuid import uuid4
import pandas as pd
import streamlit as st
from .auth import configuration
from . import assistant, catalog, research_policy as policy
from .credential_drafts import CredentialDraft, parse_csv, save_batch, merge_drafts
from .exports import credentials_csv, CREDENTIAL_FIELDS
from .models import ImportProposal, canonical_hash


def chat(service,mode):
    key='assistant_'+mode
    state=st.session_state.setdefault(key,{'history':[],'draft':None if mode=='import' else [],'sources':[]})
    cfg=configuration();gemini=cfg.get('gemini',{})
    ready=bool(gemini.get('api_key') and gemini.get('model') and not service.repo.is_demo)
    st.caption('El borrador y la conversación viven en esta sesión. Descárgalos antes de salir si aún no los has guardado. La búsqueda web sólo se ejecuta cuando la confirmas; conversar usa Gemini.')
    if not ready:
        st.info('Para conversar, entra con tu cuenta y configura api_key y model de Gemini en Secrets. Puedes seguir usando el formulario y los archivos sin IA.')
    for message in state['history'][-8:]:
        with st.chat_message(message['role']): st.write(message['text'])
    with st.form(key+'_form',clear_on_submit=True):
        message=st.text_area('Cuéntame qué quieres organizar',height=120,key=key+'_message',placeholder='Ej.: obtuve el certificado de Google Cybersecurity en otoño de 2024; ayúdame a organizarlo. (No incluyas claves ni contraseñas.)')
        consent=st.checkbox('Enviar este mensaje y el borrador a Gemini para preparar una propuesta',key=key+'_consent')
        sent=st.form_submit_button('Enviar a Gemini',disabled=not ready)
    if sent:
        if not consent:
            st.warning('Marca la autorización antes de enviar el contenido a Gemini.')
        else:
            try:
                with st.spinner('Preparando una propuesta…'):
                    reply=assistant.converse(mode,message,state['history'],state['draft'],state['sources'],gemini['api_key'],gemini['model'])
                state['history'].extend([{'role':'user','text':message[:12000]},{'role':'assistant','text':reply.message}])
                state['history']=state['history'][-12:]
                if mode=='import' and reply.proposal:
                    state['draft']=reply.proposal.model_dump(mode='json')
                if mode=='credentials' and reply.credentials:
                    state['draft']=merge_drafts(state['draft'],reply.credentials)
                state['citations']=reply.source_urls
                state['editor_version']=str(uuid4())
                st.rerun()
            except ValueError as exc: st.error(str(exc))
    with st.expander('Comprobar un nombre en fuentes públicas'):
        st.caption('Escribe sólo el nombre del programa y su emisor. No envíes tu ID personal ni el enlace privado de Drive. Esta consulta tiene un máximo de 2 créditos Tavily y comparte el presupuesto mensual de Learning Atlas.')
        query=st.text_input('Nombre y emisor a buscar',key=key+'_query',max_chars=240)
        consent_lookup=st.checkbox('Confirmo esta búsqueda pública y su consumo de hasta 2 créditos',key=key+'_lookup_consent')
        enabled=bool(not service.repo.is_demo and cfg.get('tavily',{}).get('api_key') and catalog.settings(service)['external_consent'])
        if not enabled:
            st.caption('Necesitas Tavily configurado y autorizar las consultas públicas en Profile & Preferences.')
        if st.button('Buscar fuentes para este nombre',key=key+'_lookup',disabled=not(enabled and consent_lookup)):
            try:
                with st.spinner('Consultando fuentes públicas…'):
                    state['sources']=assistant.lookup_name(service.repo,cfg['tavily']['api_key'],query)
                st.session_state.flash='Fuentes listas. Ahora pide a Gemini que revise el nombre usando estas fuentes.'
                st.rerun()
            except ValueError as exc: st.error(str(exc))
        for source in state['sources']:
            st.link_button(source['title'],source['url'])
        if state['sources']:
            st.caption('Estas páginas ayudan a revisar el nombre y emisor. No verifican la obtención de tu credencial. Comprueba que la fuente corresponda al programa que cursaste.')
    return state


def render_import_assistant(service):
    with st.expander('Preparar la información conversando con Gemini'):
        state=chat(service,'import')
        if state['draft']:
            proposal=ImportProposal.model_validate(state['draft'])
            st.write('**Propuesta para revisar**')
            for track in proposal.tracks:
                st.write(track.title+f' · {len(track.units)} módulos/lecciones · '+', '.join(s.name for s in track.skills))
            if proposal.route: st.write('Learning Roadmap: '+proposal.route.title)
            for evidence in proposal.evidence: st.write('Trabajo realizado: '+evidence.title)
            for warning in proposal.warnings: st.warning(warning)
            st.download_button('Descargar propuesta · TXT',assistant.import_text(proposal),'learning-atlas-propuesta.txt',mime='text/plain')
            if st.button('Llevar esta propuesta a revisión',key='assistant_to_import',type='primary'):
                for key in ('import_source','import_uploaded_path'):
                    st.session_state.pop(key,None)
                st.session_state.proposal_editor=proposal.model_dump_json(indent=2)
                st.session_state.import_model=configuration().get('gemini',{}).get('model')
                st.session_state.flash='Propuesta preparada. Continúa abajo: validar borrador → revisar → importar lo aprobado.'
                st.rerun()


def render_credentials_assistant(service):
    from .app import action
    with st.expander('Organizar mis credenciales con Gemini o CSV'):
        state=chat(service,'credentials')
        uploaded=st.file_uploader('Recuperar una tabla de credenciales · CSV',type=['csv'],key='credentials_upload')
        if uploaded and st.button('Preparar tabla desde CSV',key='credential_csv_prepare'):
            try:
                state['draft']=parse_csv(uploaded.getvalue())
                state['editor_version']=str(uuid4())
                st.rerun()
            except (ValueError,UnicodeError) as exc: st.error(str(exc))
        if state['draft']:
            st.write('**Revisa los nombres, fechas y enlaces antes de guardar.**')
            st.caption('Puedes corregir o eliminar filas. Tipo: professional = certificación profesional; course = certificado de curso; program = programa; badge = insignia. Las fechas usan AAAA-MM-DD; déjalas vacías si no las sabes.')
            frame=pd.DataFrame(state['draft'],columns=CREDENTIAL_FIELDS).fillna('')
            for col in frame.columns:
                if col!='never_expires': frame[col]=frame[col].astype(str)
            edited=st.data_editor(frame,hide_index=True,num_rows='dynamic',key='credential_editor_'+state.get('editor_version','start'),width='stretch',
                column_config={'official_name':'Nombre oficial','issuer':'Emisor','program_code':'Código del programa',
                               'credential_code':'ID personal','earned_on':'Fecha de obtención','period_label':'Período aproximado',
                               'expires_on':'Caducidad','verification_url':'Verificación del emisor','document_url':'Mis documentos','notes':'Notas',
                               'credential_type':st.column_config.SelectboxColumn('Tipo',options=['professional','course','program','badge']),
                               'never_expires':st.column_config.CheckboxColumn('No caduca')})
            raw=edited.to_dict('records')
            rows=[];valid=True
            try:
                for row in raw:
                    values={k:v for k,v in row.items() if v not in ('',None)}
                    rows.append(CredentialDraft.model_validate(values).model_dump(mode='json'))
            except ValueError:
                valid=False
                st.warning('Revisa la tabla: cada fila necesita nombre, emisor, tipo válido y fechas o enlaces válidos.')
            if valid and rows:
                # The approved content and download are exactly the table currently displayed.
                state['draft']=rows
                st.download_button('Descargar tabla preparada · CSV',credentials_csv(rows),'learning-atlas-credentials-draft.csv',mime='text/csv')
                approved=st.checkbox('Revisé esta tabla y confirmo que ya obtuve estas credenciales',key='review_credentials_'+canonical_hash(rows))
                if st.button('Guardar credenciales revisadas',disabled=not approved,key='save_credentials_batch',type='primary'):
                    result=action('credential_batch',lambda rid:save_batch(service,rows,rid,reviewed=approved))
                    if result:
                        state['draft']=[];state['editor_version']=str(uuid4())
                        st.session_state.flash=f"Credenciales guardadas: {result['result']['added']}; ya existentes: {result['result']['skipped']}. No se registraron horas ni progreso."
                        st.rerun()
