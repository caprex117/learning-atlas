"""Discovery catalog UI; learning adoption always remains an explicit user action."""
import streamlit as st
from datetime import datetime, timezone
from . import research_policy as policy
from . import catalog
from .catalog_export import export_csv, rankings
from .catalog_seed import read_seed
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
    heading('LEARNING RADAR', 'Tu próximo aprendizaje.',
            'Descubre cursos, certificaciones, proyectos y Learning Packs relacionados con tu dirección profesional. Guarda favoritos o añade lo que elijas a My Learning y a tu ruta. Las revisiones amplían este catálogo y comprueban algunas fichas; no sustituyen tus aprendizajes.')
    if 'opportunities' not in service.data:
        st.info('Falta instalar la migración 002_discovery_catalog.sql en Supabase. Consulta docs/DISCOVERY_SETUP.md.')
        return
    config = catalog.settings(service)
    cfg = configuration()
    runs = sorted(service.data['discovery_runs'], key=lambda r:r['started_at'], reverse=True)
    relevant=policy.catalog_runs(service.data)
    last=max(relevant,key=lambda r:r['finished_at']) if relevant else None
    due=policy.next_due(service.data)
    used=policy.spent(service.data)
    a,b,c=st.columns(3)
    a.metric('Última carga / revisión', last['finished_at'][:10] if last else 'Sin revisión')
    b.metric('Próxima revisión prevista', due.date().isoformat() if due else 'Pendiente de la primera')
    c.metric('Tavily · presupuesto mensual', f'{used:g} / {policy.MONTHLY_CREDITS} créditos')
    st.caption('Fechas UTC · cada 21 días. La última carga puede corresponder a la selección inicial, no a una búsqueda nueva. La fecha prevista es orientativa: la automatización requiere el workflow de GitHub activo. Este presupuesto sólo cubre llamadas realizadas por Learning Atlas; no muestra el saldo global de Tavily.')
    with st.expander('Calendario de revisiones'):
        render_calendar(relevant,due)
    if runs and runs[0]['status']=='failed':
        st.warning('Último intento sin completar: '+runs[0]['error_message']+' El catálogo guardado sigue disponible.')
    seed=read_seed()
    installed={o['identity_key'] for o in service.data['opportunities']}
    from .catalog_models import Opportunity
    missing_seed=sum(Opportunity.model_validate(o).identity() not in installed for o in seed['opportunities'])
    if missing_seed:
        st.info('Tienes disponible una selección inicial investigada para ti. Cargarla no consume Tavily ni Gemini. El catálogo puede seguir creciendo sin un límite de 54 fichas.')
        if st.button('Cargar selección inicial' if not installed else 'Completar selección inicial',key='catalog_seed',width='stretch'):
            save_and_refresh('catalog_seed', lambda rid: catalog.load_seed(service,rid), 'Selección inicial incorporada. No se registró progreso.')
    missing=readiness(service,cfg,config)
    if st.button('Buscar novedades',key='catalog_refresh',type='primary',disabled=bool(missing),width='stretch'):
        st.session_state.catalog_confirm_open=True
    if st.session_state.get('catalog_confirm_open'):
        confirm_refresh(service)
    if missing:
        st.info('Para buscar novedades: '+' · '.join(missing))
    else:
        st.caption('Conexiones configuradas. Buscar novedades pedirá confirmación antes de consumir APIs.')
    st.caption('Por revisión: hasta 5 oportunidades nuevas y 3 fichas existentes comprobadas. Puede haber menos o ninguna novedad. Se conservan favoritos, decisiones, rutas y progreso.')
    with st.expander('Mi enfoque y opciones de actualización'):
        focus_settings(service)
    library, history = st.tabs(['Catálogo', 'Historial de actualizaciones'])
    with library:
        priority = rankings(service.data)
        if service.data['opportunities']:
            st.download_button('Descargar catálogo completo · CSV', export_csv(service), 'learning-atlas-oportunidades.csv',
                               mime='text/csv', key='catalog_csv', width='stretch')
            st.caption('Incluye todas las fichas, aunque uses filtros: temas, habilidades, precios, fuentes, componentes, historial y tus decisiones. Las listas se guardan como JSON dentro del CSV; no es un archivo de restauración.')
        if priority:
            st.caption('Prioridad personal: selección del 18 de octubre de 2026 para Factory Enablement y apps con IA. Los bloques sugeridos son puntos de entrada, no duraciones oficiales ni horas que debas sumar a tu ruta de 96 h. Relevancia usa tus etiquetas actuales.')
        a,b,c=st.columns([2,1,1])
        query=a.text_input('Buscar oportunidad o habilidad',key='catalog_search')
        kind=b.selectbox('Tipo de oportunidad',[None]+list(KINDS),format_func=lambda x:KINDS.get(x,'Todos'))
        language=c.selectbox('Idioma del recurso',['Todos','es','en'])
        a,b,c=st.columns(3)
        order=a.selectbox('Ordenar',(['Prioridad personal'] if priority else [])+['Relevancia','Última comprobación','Actualización del proveedor','Nombre'])
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
        key={'Prioridad personal':lambda r:(priority.get(r[0]['identity_key'],{}).get('rank',1000000),-r[2],r[0]['title']),
             'Relevancia':lambda r:(-r[2],r[0]['title']), 'Última comprobación':lambda r:r[0]['checked_at'],
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
                personal = priority.get(item['identity_key'])
                if personal:
                    pills([f"Prioridad #{personal['rank']}",personal['phase'],personal['priority_band']])
                    st.write('**Cómo empezaría en tu caso:** '+personal['study_slice'])
                    st.caption('Primer bloque sugerido: '+minutes(personal['study_slice_minutes'])+' · Puede solaparse con otros componentes de un pack.')
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
                    if item['kind']=='project' and item['provider'].startswith('Learning Atlas'):
                        st.caption('Proyecto diseñado para practicar con estas tecnologías. Los entregables son una propuesta propia basada en las fuentes; no es un curso ni una certificación oficial.')
                    else:
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
                        phase=st.selectbox('Fase de una ruta activa (opcional)',[None]+list(phase_labels),format_func=lambda p:phase_labels.get(p,'Sólo a My Learning'),key='catphase_'+oid)
                        use_topics=st.checkbox('Usar este temario como unidades de seguimiento',False,key='catunits_'+oid,disabled=item['kind']=='pack' or bool(choice.get('track_id')))
                        st.caption('Los Learning Packs crean una unidad por componente. Puedes ajustar las unidades después. No se registran horas, temas aprendidos ni credenciales. Añadir a la ruta vincula la fase sin modificar sus fechas o presupuesto.')
                        reviewed=st.checkbox('Revisé las fuentes, el precio y el temario',key='catreview_'+oid)
                        if st.form_submit_button('Vincular a la ruta' if choice.get('track_id') else 'Añadir aprendizaje',type='primary',disabled=item['availability']=='retired'):
                            if not reviewed:
                                st.warning('Revisa las fuentes, el precio y el temario, y marca la confirmación antes de añadirlo.')
                            else:
                                save_and_refresh('adopt_'+oid,lambda rid,i=oid,p=phase,u=use_topics:catalog.adopt(service,i,p,rid,use_topics=u),'Aprendizaje incorporado sin progreso automático.')
    with history:
        st.caption('El workflow comprueba diariamente si han pasado 21 días desde la última revisión. Sólo entonces investiga. Las verificaciones de nombres usan el mismo presupuesto, pero no aplazan la próxima revisión del catálogo. GitHub puede retrasar la ejecución.')
        for run in runs[:30]:
            with st.expander(run['started_at']+' · '+run['status']+' · '+run['origin']):
                st.write(run.get('model_id') or 'Sin respuesta de un modelo')
                if run['error_message']:
                    st.write(run['error_message'])
                st.json(run['details'])


def readiness(service, cfg, config):
    missing=[]
    if service.repo.is_demo:
        missing.append('inicia sesión con tu cuenta; la demo no utiliza APIs')
    if not cfg.get('tavily',{}).get('api_key'):
        missing.append('falta la clave de Tavily en Secrets')
    if not cfg.get('gemini',{}).get('api_key'):
        missing.append('falta la clave de Gemini en Secrets')
    if not config['external_consent']:
        missing.append('autoriza el uso de tu enfoque en las opciones de actualización')
    if policy.spent(service.data)+policy.REFRESH_CREDITS>policy.MONTHLY_CREDITS:
        missing.append('no queda presupuesto mensual suficiente para esta revisión')
    return missing


def dismiss_refresh():
    st.session_state.pop('catalog_confirm_open',None)


@st.dialog('¿Buscar novedades ahora?',on_dismiss=dismiss_refresh)
def confirm_refresh(service):
    st.write('Esta revisión buscará recursos relacionados con tu enfoque: hasta 5 oportunidades nuevas y 3 fichas existentes. No borra el catálogo ni modifica tu progreso.')
    st.write('Tavily: hasta 8 créditos por ejecución con la tarifa actual. Gemini: hasta 6.000 tokens de salida por intento, con un máximo de 4 intentos entre los dos modelos. La entrada contiene fuentes acotadas y un resumen del catálogo.')
    st.caption('Los intentos fallidos también pueden consumir cuota. Una revisión completada mueve la siguiente fecha prevista 21 días hacia delante.')
    a,b=st.columns(2)
    if b.button('Cancelar',key='cancel_research',width='stretch'):
        dismiss_refresh()
        st.rerun()
    if a.button('Sí, buscar novedades',key='confirm_research',type='primary',width='stretch'):
        cfg=configuration()
        with st.status('Buscando novedades…',expanded=True) as status:
            try:
                result=catalog.refresh(service.repo,cfg.get('tavily',{}).get('api_key',''),cfg.get('gemini',{}).get('api_key',''),notify=lambda message:status.update(label=message))
                status.update(label='Revisión guardada',state='complete')
                st.session_state.flash=f"Revisión terminada: {result['added']} nuevas y {result['changed']} fichas modificadas. Se comprobó un total de {result['checked']} fichas. Tus aprendizajes se conservaron."
                dismiss_refresh()
                st.rerun()
            except (ValueError,RepositoryError) as exc:
                status.update(label='Revisión sin completar',state='error')
                st.error(str(exc))


def focus_settings(service):
    from .app import save_and_refresh
    if 'discovery_settings' not in service.data:
        return
    config=catalog.settings(service)
    st.caption('Tu dirección profesional orienta las búsquedas y el orden de relevancia. Las horas de práctica y los documentos privados no se envían para investigar oportunidades.')
    with st.form('discovery_focus'):
        focus=st.text_area('Dirección profesional actual',config['focus'],max_chars=600)
        primary=st.text_input('Temas prioritarios · separados por comas',', '.join(config['primary_tags']))
        related=st.text_input('Áreas relacionadas · separadas por comas',', '.join(config['related_tags']))
        consent=st.checkbox('Autorizar el envío del enfoque y nombres públicos a Tavily y Gemini',config['external_consent'])
        automatic=st.checkbox('Permitir revisión automática cada 21 días',config['weekly_enabled'])
        st.caption('Activar esta preferencia no instala la automatización: requiere los secretos y el workflow de GitHub descritos en docs/DISCOVERY_SETUP.md.')
        if st.form_submit_button('Guardar enfoque'):
            values={'focus':focus,'primary_tags':[x.strip() for x in primary.split(',') if x.strip()],
                    'related_tags':[x.strip() for x in related.split(',') if x.strip()],'weekly_enabled':automatic,'external_consent':consent}
            save_and_refresh('discovery_focus',lambda rid:catalog.save_settings(service,values,rid),'Enfoque guardado.')


def render_calendar(runs,due):
    import calendar
    import pandas as pd
    point=due.date() if due else datetime.now(timezone.utc).date()
    days={r['finished_at'][:10] for r in runs}
    rows=[]
    for week in calendar.monthcalendar(point.year,point.month):
        row=[]
        for day in week:
            label=str(day) if day else ''
            iso=f'{point.year:04d}-{point.month:02d}-{day:02d}'
            if day and iso in days: label+=' ✓'
            if day and due and day==point.day: label+=' ◉'
            row.append(label)
        rows.append(row)
    st.write(f'{point.year}-{point.month:02d}')
    st.table(pd.DataFrame(rows,columns=['Lun','Mar','Mié','Jue','Vie','Sáb','Dom']))
    st.caption('✓ Revisión registrada · ◉ Próxima fecha prevista. El calendario muestra el mes de la próxima revisión; el historial conserva los meses anteriores.')
