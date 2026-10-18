"""Discovery catalog UI; learning adoption always remains an explicit user action."""
import streamlit as st
from . import catalog
from .auth import configuration
from .repository import RepositoryError
from .ui import heading, pills, minutes

KINDS = {'certification':'Certificación', 'course':'Curso', 'resource':'Recurso', 'paper':'Paper',
         'project':'Proyecto', 'lab':'Laboratorio', 'pack':'Learning Pack'}


def price_label(item):
    if item['price_kind'] == 'free':
        return 'Acceso gratuito'
    if item.get('price_amount') is not None:
        return f"{item['currency'] or ''} {float(item['price_amount']):,.2f} · " + {'subscription':'suscripción','one_time':'pago único'}.get(item['price_kind'],'ver condiciones')
    return {'unknown':'Precio por confirmar','mixed':'Precio según modalidad','subscription':'Suscripción','one_time':'De pago'}.get(item['price_kind'],'Consultar precio')


def render(service):
    from .app import action, save_and_refresh
    heading('UN CATÁLOGO QUE CRECE CONTIGO', 'Tu próximo aprendizaje.',
            'Oportunidades vigentes, fuentes y caminos relacionados con tu carrera. Tú decides qué incorporar a tu biblioteca y a tu ruta.')
    if 'opportunities' not in service.data:
        st.info('Falta instalar la migración 002_discovery_catalog.sql en Supabase. Consulta docs/DISCOVERY_SETUP.md.')
        return
    config = catalog.settings(service)
    cfg = configuration()
    runs = sorted(service.data['discovery_runs'], key=lambda r:r['started_at'], reverse=True)
    successful = [r for r in runs if r['status'] in ('completed','partial') and r['origin']!='seed']
    if successful:
        r = successful[0]
        st.caption(f"Última revisión guardada (UTC): {r['finished_at']} · {r.get('model_id') or 'sin modelo'} · {r['details'].get('checked',0)} oportunidades comprobadas. Cada ficha conserva su propia fecha.")
    elif service.data['opportunities']:
        st.caption('Catálogo inicial revisado el 18 de octubre de 2026. Aún no hay una investigación con APIs completada.')
    else:
        st.caption('Todavía no hay una revisión guardada. Puedes cargar la investigación inicial.')
    if runs and runs[0]['status'] == 'failed':
        st.warning('Actualización pendiente. '+runs[0]['error_message']+' Último intento: '+runs[0]['started_at'])
    elif runs and runs[0]['status'] == 'running':
        st.info('Hay una actualización en curso o interrumpida. Una reserva interrumpida vence a los 15 minutos.')
    if service.repo.is_demo:
        st.caption('Demo: el catálogo inicial usa fuentes reales; los cambios son temporales. La investigación con APIs funciona en tu cuenta conectada.')
    controls = st.columns(2)
    if controls[0].button('Cargar investigación inicial', key='catalog_seed', width='stretch'):
        save_and_refresh('catalog_seed', lambda rid: catalog.load_seed(service,rid), 'Catálogo inicial incorporado. No se registró progreso.')
    ready = bool(cfg.get('tavily',{}).get('api_key') and cfg.get('gemini',{}).get('api_key') and config['external_consent'] and not service.repo.is_demo)
    if controls[1].button('Actualizar ahora', key='catalog_refresh', type='primary', disabled=not ready, width='stretch'):
        with st.status('Actualizando el catálogo…', expanded=True) as status:
            try:
                result = catalog.refresh(service.repo, cfg['tavily']['api_key'],cfg['gemini']['api_key'],notify=lambda message: status.update(label=message))
                status.update(label='Investigación guardada',state='complete')
                st.session_state.flash=f"Actualización: {result['added']} nuevas, {result['changed']} modificadas. Modelo: {result['model']}."
                st.rerun()
            except (ValueError, RepositoryError) as exc:
                status.update(label='Actualización pendiente', state='error')
                st.error(str(exc))
    if not ready and not service.repo.is_demo:
        st.caption('Para actualizar: añade las claves de Tavily y Gemini, y autoriza el uso de tu enfoque en el panel siguiente.')
    with st.expander('Mi enfoque y actualización semanal', expanded=not bool(service.data['opportunities'])):
        with st.form('discovery_focus'):
            focus = st.text_area('Dirección profesional actual', config['focus'],max_chars=600)
            primary = st.text_input('Temas prioritarios · separados por comas', ', '.join(config['primary_tags']))
            related = st.text_input('Áreas relacionadas · separadas por comas', ', '.join(config['related_tags']))
            consent = st.checkbox('Autorizar el envío de este enfoque y sus etiquetas a Tavily y Gemini',config['external_consent'])
            weekly = st.checkbox('Permitir revisión semanal desde GitHub Actions',config['weekly_enabled'])
            st.caption('Se envían el enfoque, etiquetas y URLs públicas del catálogo. Las sesiones, documentos privados, contraseñas y claves de Supabase no se incluyen en la investigación. El horario requiere configurar el workflow; marcar esta opción no lo instala.')
            if st.form_submit_button('Guardar enfoque'):
                values={'focus':focus,'primary_tags':[x.strip() for x in primary.split(',') if x.strip()],
                        'related_tags':[x.strip() for x in related.split(',') if x.strip()], 'weekly_enabled':weekly,'external_consent':consent}
                save_and_refresh('discovery_focus',lambda rid:catalog.save_settings(service,values,rid),'Enfoque guardado; la relevancia se recalcula con tus etiquetas actuales.')
    library, history = st.tabs(['Catálogo', 'Historial de actualizaciones'])
    with library:
        a,b,c=st.columns([2,1,1])
        query=a.text_input('Buscar oportunidad o habilidad',key='catalog_search')
        kind=b.selectbox('Tipo de oportunidad',[None]+list(KINDS),format_func=lambda x:KINDS.get(x,'Todos'))
        language=c.selectbox('Idioma del recurso',['Todos','es','en'])
        a,b,c=st.columns(3)
        order=a.selectbox('Ordenar',['Relevancia','Última comprobación','Actualización del proveedor','Nombre'])
        decision=b.selectbox('Mostrar',['Disponibles','Todos','Favoritos','En mi aprendizaje','Descartados'])
        free=c.checkbox('Sólo acceso gratuito')
        choices={r['opportunity_id']:r for r in service.data['opportunity_choices']}
        candidates=[]
        for item in service.data['opportunities']:
            choice=choices.get(item['id'],{})
            if kind and item['kind']!=kind or language!='Todos' and language not in item['language'] or free and item['price_kind']!='free':
                continue
            if decision=='Disponibles' and (choice.get('decision') in ('dismissed','added') or item['availability']=='retired'):
                continue
            if decision=='Favoritos' and not choice.get('favorite') or decision=='En mi aprendizaje' and not choice.get('track_id') or decision=='Descartados' and choice.get('decision')!='dismissed':
                continue
            if query.casefold() not in ' '.join([item['title'],item['description'],*item['skills'],*item['topics']]).casefold():
                continue
            score, explanation=catalog.relevance(service,item)
            candidates.append((item,choice,score,explanation))
        key={'Relevancia':lambda r:(-r[2],r[0]['title']), 'Última comprobación':lambda r:r[0]['checked_at'],
             'Actualización del proveedor':lambda r:r[0].get('provider_updated_on') or '', 'Nombre':lambda r:r[0]['title']}[order]
        candidates.sort(key=key,reverse=order in ('Última comprobación','Actualización del proveedor'))
        st.caption(f'{len(candidates)} oportunidades · Relevancia orientativa sobre 100: etiquetas prioritarias y relacionadas, habilidades sin autonomía declarada, vigencia de la consulta y duración. No mide demanda laboral ni calidad garantizada.')
        if not candidates:
            st.info('Carga la investigación inicial o ajusta los filtros. Guardar una oportunidad no la añade automáticamente a tu ruta.')
        pages=max(1,(len(candidates)+7)//8)
        page=st.selectbox('Página',list(range(1,pages+1)),key='catalog_page')
        active_goals={g['id'] for g in service.data['learning_goals'] if g['status']=='active'}
        phases=[p for p in service.data['goal_phases'] if p['goal_id'] in active_goals]
        phase_labels={p['id']:p['title'] for p in phases}
        for item,choice,score,explanation in candidates[(page-1)*8:page*8]:
            oid=item['id']
            with st.container(border=True):
                pills([KINDS[item['kind']],item['language'].upper(),f'Relevancia {score}/100',price_label(item)])
                st.subheader(item['title'])
                st.caption(item['provider']+' · '+item['area']+' · '+item['availability'])
                st.write(item['description'])
                st.write('**Relación con tu enfoque actual:** '+explanation)
                pills(item['skills'])
                st.write(item['price_note'])
                st.caption('Duración: '+(minutes(item['duration_minutes']) if item.get('duration_minutes') else 'sin estimar')+
                           ' · Comprobado (UTC): '+item['checked_at']+
                           ' · Actualización declarada por la fuente: '+str(item.get('provider_updated_on') or 'no indicada'))
                if item.get('url'):
                    st.link_button('Abrir fuente',item['url'])
                with st.expander('Ver temario, fuentes y cambios'):
                    st.caption({'summary':'Resumen del temario disponible; consulta la fuente para el detalle completo.',
                                'published_outline':'Temario publicado por la fuente.', 'custom_pack':'Learning Pack diseñado para tu enfoque; no es una certificación oficial.'}[item['syllabus_scope']])
                    for topic in item['topics']:
                        st.write('• '+topic)
                    st.write('**Requisitos:** '+(item['prerequisites'] or 'No precisados por la fuente.'))
                    st.write('**Nota de investigación:** '+item['reason'])
                    st.caption('Enfoque utilizado en esa investigación: '+item['research_focus']+' · '+('Selección revisada manualmente' if item['origin']=='curated' else 'Propuesta de IA con fuentes; comprueba los detalles antes de elegir'))
                    for part in sorted([p for p in service.data['pack_components'] if p['opportunity_id']==oid],key=lambda p:p['sort_order']):
                        st.link_button(f"{part['sort_order']+1}. {part['title']}",part['url'])
                        st.write(part['purpose'])
                    for source in [s for s in service.data['opportunity_sources'] if s['opportunity_id']==oid]:
                        st.link_button('Fuente · '+source['title'],source['url'])
                    versions=sorted([v for v in service.data['opportunity_versions'] if v['opportunity_id']==oid],key=lambda v:v['checked_at'],reverse=True)
                    for v in versions[:5]:
                        st.caption(v['checked_at']+' · Campos cambiados: '+', '.join(v['changed_fields']))
                    if versions:
                        import json
                        st.download_button('Descargar historial de esta oportunidad',json.dumps(versions,ensure_ascii=False,indent=2,default=str),'opportunity-history.json',key='history_'+oid)
                a,b=st.columns(2)
                if a.button('★ Favorito' if choice.get('favorite') else '☆ Guardar favorito',key='catfav_'+oid,width='stretch'):
                    save_and_refresh('catfav_'+oid,lambda rid,i=oid,ch=choice:catalog.choose(service,i,not ch.get('favorite',False),ch.get('decision','interested'),rid))
                if b.button('Recuperar' if choice.get('decision')=='dismissed' else 'Descartar',key='catdismiss_'+oid,disabled=bool(choice.get('track_id')),width='stretch'):
                    save_and_refresh('catdismiss_'+oid,lambda rid,i=oid,ch=choice:catalog.choose(service,i,ch.get('favorite',False),'interested' if ch.get('decision')=='dismissed' else 'dismissed',rid))
                with st.expander('Añadir a mi aprendizaje o a mi ruta'):
                    with st.form('adopt_'+oid):
                        phase=st.selectbox('Fase de una ruta activa (opcional)',[None]+list(phase_labels),format_func=lambda p:phase_labels.get(p,'Sólo a Mi aprendizaje'),key='catphase_'+oid)
                        use_topics=st.checkbox('Usar este temario como unidades de seguimiento',False,key='catunits_'+oid,disabled=item['kind']=='pack' or bool(choice.get('track_id')))
                        st.caption('Los Learning Packs crean una unidad por componente. Puedes ajustar las unidades después. No se registran horas, temas aprendidos ni credenciales. Añadir a la ruta vincula la fase sin modificar sus fechas o presupuesto.')
                        reviewed=st.checkbox('Revisé las fuentes, el precio y el temario',key='catreview_'+oid)
                        if st.form_submit_button('Vincular a la ruta' if choice.get('track_id') else 'Añadir aprendizaje',type='primary',disabled=item['availability']=='retired'):
                            if not reviewed:
                                st.warning('Revisa las fuentes, el precio y el temario, y marca la confirmación antes de añadirlo.')
                            else:
                                save_and_refresh('adopt_'+oid,lambda rid,i=oid,p=phase,u=use_topics:catalog.adopt(service,i,p,rid,use_topics=u),'Aprendizaje incorporado sin progreso automático.')
    with history:
        st.caption('Revisión semanal prevista: domingo a las 12:17 UTC. GitHub Actions puede retrasarla. Consulta docs/DISCOVERY_SETUP.md para activarla; la app muestra aquí cada ejecución que logra iniciar sesión.')
        for run in runs[:30]:
            with st.expander(run['started_at']+' · '+run['status']+' · '+run['origin']):
                st.write(run.get('model_id') or 'Sin respuesta de un modelo')
                if run['error_message']:
                    st.write(run['error_message'])
                st.json(run['details'])
