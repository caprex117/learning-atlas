"""Persistent discovery, with atomic publication and explicit adoption into learning."""
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
from uuid import uuid4

from .catalog_models import Focus, Opportunity, defaults
from .models import TrackDraft, canonical_hash, normalized
from .service import Batch, LearningService
from . import research


def now():
    return datetime.now(timezone.utc)


def stamp(value):
    return datetime.fromisoformat(str(value).replace('Z', '+00:00'))


def settings(service):
    return service.data.get('discovery_settings', [])[0] if service.data.get('discovery_settings') else defaults()


def save_settings(service, values, request_id):
    values = Focus.model_validate(values).model_dump()
    b = Batch(service.data)
    b.put('discovery_settings', {'id': service.repo.user_id, **values})
    return service._commit(b, request_id, {'action': 'discovery_settings', **values})


def begin(service, origin, request_id):
    current = now()
    config = settings(service)
    if origin != 'seed' and not config['external_consent']:
        raise ValueError('Autoriza el envío del enfoque a Tavily y Gemini en los ajustes de Descubrir.')
    b = Batch(service.data)
    for run in b.data['discovery_runs']:
        if run['status'] == 'running':
            if current-stamp(run['started_at']) < timedelta(minutes=15):
                raise ValueError('Ya hay una actualización en curso. Espera antes de reintentar.')
            b.put('discovery_runs', {**run, 'status': 'failed', 'finished_at': current.isoformat(),
                                    'error_message': 'La ejecución anterior se interrumpió y su reserva expiró.'})
    rid = b.put('discovery_runs', {'status': 'running', 'origin': origin, 'started_at': current.isoformat(),
                                  'finished_at': None, 'model_id': None, 'focus_snapshot': {
                                      k: config[k] for k in ('focus', 'primary_tags', 'related_tags')},
                                  'details': {}, 'error_message': ''})
    service._commit(b, request_id, {'action': 'discovery_begin', 'origin': origin}, {'run_id': rid})
    return rid


def publish(service, run_id, items, details, request_id, *, checked_at=None, origin='ai'):
    """A batch changes catalog records only; learning and personal decisions are preserved."""
    items = [i if isinstance(i, Opportunity) else Opportunity.model_validate(i) for i in items]
    b = Batch(service.data)
    run = b.find('discovery_runs', run_id)
    if run['status'] != 'running':
        raise ValueError('Esta actualización ya terminó. Actualiza la pantalla.')
    checked_at = checked_at or now().isoformat()
    changed, added, seen = 0, 0, set()
    for candidate in items:
        item = candidate if isinstance(candidate, Opportunity) else Opportunity.model_validate(candidate)
        key = item.identity()
        if key in seen:
            continue
        seen.add(key)
        old = next((o for o in b.data['opportunities'] if o['identity_key'] == key), None)
        # Loading the bundled seed again only fills missing entries, never rolls back live research.
        if origin == 'curated' and old:
            continue
        full = item.model_dump(mode='json')
        content_hash = canonical_hash(full)
        columns = item.model_dump(mode='json', exclude={'sources', 'components'})
        oid = b.put('opportunities', {**columns, 'id': old['id'] if old else str(uuid4()), 'identity_key': key,
                                      'checked_at': checked_at, 'content_hash': content_hash, 'origin': origin,
                                      'research_focus': run['focus_snapshot']['focus']})
        if not old or old['content_hash'] != content_hash:
            previous = [v for v in b.data['opportunity_versions'] if v['opportunity_id'] == oid]
            before = max(previous, key=lambda v:v['checked_at'])['payload'] if previous else {}
            fields = [k for k, v in full.items() if before.get(k) != v]
            b.put('opportunity_versions', {'opportunity_id': oid, 'run_id': run_id, 'content_hash': content_hash,
                                           'payload': full, 'changed_fields': fields, 'checked_at': checked_at})
            changed += bool(old)
            added += not old
        for table in ('opportunity_sources', 'pack_components'):
            for row in list(b.data[table]):
                if row['opportunity_id'] == oid:
                    b.remove(table, row['id'])
        for source in item.sources:
            b.put('opportunity_sources', {'opportunity_id': oid, **source.model_dump(), 'checked_at': checked_at})
        for i, part in enumerate(item.components):
            b.put('pack_components', {'opportunity_id': oid, **part.model_dump(), 'sort_order': i})
    summary = {**details, 'added': added, 'changed': changed, 'checked': len(seen)}
    b.put('discovery_runs', {**run, 'status': 'partial' if details.get('rejected') or details.get('warnings') else 'completed',
                            'finished_at': now().isoformat(), 'model_id': details.get('model'), 'details': summary})
    return service._commit(b, request_id, {'action': 'discovery_publish', 'run_id': run_id,
                                          'hashes': [canonical_hash(i.model_dump(mode='json')) for i in items]}, summary)


def refresh(repository, tavily_key, gemini_key, *, origin='manual', transport=None, sleep=None, notify=lambda message: None):
    service = LearningService(repository)
    config = settings(service)
    if origin == 'weekly':
        if not config['weekly_enabled'] or not config['external_consent']:
            return {'skipped': 'La actualización semanal está desactivada.'}
        recent = [r for r in service.data['discovery_runs'] if r['origin'] != 'seed' and r['status'] in ('completed','partial')]
        if recent and now()-max(stamp(r['finished_at']) for r in recent) < timedelta(days=6):
            return {'skipped': 'Ya hubo una actualización reciente.'}
    if not tavily_key or not gemini_key:
        raise research.ResearchError('Añade las claves de Tavily y Gemini antes de actualizar.')
    rid = begin(service, origin, str(uuid4()))
    details = {}
    try:
        public_focus = {k: config[k] for k in ('focus', 'primary_tags', 'related_tags')}
        sources, credits, warnings = research.retrieve(tavily_key, public_focus, service.data['opportunities'], transport=transport, notify=notify)
        details = {'tavily_credits': credits, 'sources_read': len(sources), 'warnings': warnings}
        options = {'transport': transport, 'notify': notify}
        if sleep is not None:
            options['sleep'] = sleep
        items, model_info = research.analyze(gemini_key, public_focus, sources, **options)
        details.update(model_info)
        # Preserve any personal edits made while external research was running.
        service = LearningService(repository)
        if public_focus != {k: settings(service)[k] for k in public_focus}:
            raise research.ResearchError('Tu enfoque cambió durante la investigación. Actualiza con el enfoque nuevo.')
        return publish(service, rid, items, details, str(uuid4()))
    except Exception as exc:
        if isinstance(exc, research.ResearchError):
            details.update(exc.details)
        message = str(exc) if isinstance(exc, research.ResearchError) else 'No se pudo completar la actualización. El catálogo anterior se conserva.'
        # Never persist response bodies, keys or raw exception strings from external libraries.
        try:
            latest = LearningService(repository)
            b = Batch(latest.data)
            run = b.find('discovery_runs', rid)
            if run['status'] == 'running':
                b.put('discovery_runs', {**run, 'status': 'failed', 'finished_at': now().isoformat(),
                                        'details': details, 'error_message': message})
                latest._commit(b, str(uuid4()), {'action': 'discovery_fail', 'run_id': rid})
        except Exception:
            pass  # Interrupted reservations expire without replacing valid catalog data.
        raise research.ResearchError(message) from None


def load_seed(service, request_id):
    seed = json.loads((Path(__file__).resolve().parents[1]/'data/catalog_seed.json').read_text(encoding='utf-8'))
    items = [Opportunity.model_validate(i) for i in seed['opportunities']]
    missing = [i for i in items if i.identity() not in {o['identity_key'] for o in service.data['opportunities']}]
    if not missing:
        return {'added': 0, 'checked': 0}
    rid = begin(service, 'seed', str(uuid4()))
    return publish(service, rid, missing, {'model': 'curated', 'warnings': []}, request_id,
                   checked_at=seed['checked_at'], origin='curated')


def choose(service, opportunity_id, favorite, decision, request_id):
    b = Batch(service.data)
    b.find('opportunities', opportunity_id)
    old = next((r for r in b.data['opportunity_choices'] if r['opportunity_id'] == opportunity_id), {})
    if decision not in ('interested', 'dismissed', 'added'):
        raise ValueError('Decisión no válida.')
    b.put('opportunity_choices', {**old, 'opportunity_id': opportunity_id, 'favorite': favorite,
                                  'decision': 'added' if old.get('track_id') else decision, 'track_id': old.get('track_id')})
    return service._commit(b, request_id, {'action':'catalog_choice','id':opportunity_id,'favorite':favorite,'decision':decision})


def adopt(service, opportunity_id, phase_id, request_id, *, use_topics=False):
    b = Batch(service.data)
    item = b.find('opportunities', opportunity_id)
    if item['availability'] == 'retired':
        raise ValueError('Esta oportunidad figura retirada. Revisa su fuente antes de incorporarla.')
    if phase_id:
        phase = b.find('goal_phases', phase_id)
        goal = b.find('learning_goals', phase['goal_id'])
        if goal['status'] != 'active':
            raise ValueError('Selecciona una fase de una ruta activa.')
    source_key = 'catalog:' + opportunity_id
    existing = next((t for t in b.data['learning_tracks'] if t.get('source_key') == source_key), None)
    if existing:
        tid = existing['id']
    else:
        parts = sorted([p for p in b.data['pack_components'] if p['opportunity_id'] == opportunity_id], key=lambda p:p['sort_order'])
        units = [{'key': f'u{i}', 'title': p['title']} for i,p in enumerate(parts)] if parts else (
            [{'key': f'u{i}', 'title': t} for i,t in enumerate(item['topics'])] if use_topics else [])
        notes = (item['description']+'\n\n'+item['price_note']+'\nTemario: '+item['syllabus_scope']+
                 '\nFuente comprobada: '+item['checked_at']+'\n\n'+item['reason'])[:5000]
        draft = TrackDraft(title=item['title'], kind='topic' if item['kind']=='resource' else item['kind'],
                           area=item['area'], platform=item['provider'], source_url=item['url'], notes=notes,
                           estimated_minutes=item['duration_minutes'], units=units,
                           topics=[{'name': n} for n in item['topics']], skills=[{'name': n} for n in item['skills']])
        favorite = next((r['favorite'] for r in b.data['opportunity_choices'] if r['opportunity_id']==opportunity_id), False)
        tid, _ = service._draft_track(b, draft, source_key=source_key, favorite=favorite)
        for part in parts:
            resource = b.put('resources', {'title': part['title'], 'url': part['url'], 'kind': 'link', 'notes': part['purpose']})
            b.link('track_resources', track_id=tid, resource_id=resource)
    if phase_id:
        b.link('phase_tracks', phase_id=phase_id, track_id=tid)
    old = next((r for r in b.data['opportunity_choices'] if r['opportunity_id'] == opportunity_id), {})
    b.put('opportunity_choices', {**old, 'opportunity_id': opportunity_id, 'favorite': old.get('favorite',False), 'decision':'added','track_id':tid})
    return service._commit(b, request_id, {'action':'catalog_adopt','id':opportunity_id,'phase':phase_id,'units':use_topics}, {'track_id':tid})


def relevance(service, item):
    config = settings(service)
    haystack = normalized(' '.join([item['title'],item['area'],*item['tags'],*item['skills']]))
    core = [t for t in config['primary_tags'] if normalized(t) in haystack]
    related = [t for t in config['related_tags'] if normalized(t) in haystack]
    # Only declared autonomy, never mere syllabus coverage, counts as already practiced independently.
    latest = {}
    for a in service.data['skill_assessments']:
        if not a.get('voided') and (a['skill_id'] not in latest or a['occurred_on'] > latest[a['skill_id']]['occurred_on']):
            latest[a['skill_id']] = a
    known = {normalized(s['name']) for s in service.data['skills'] if latest.get(s['id'],{}).get('level',0)>=2}
    gaps = [s for s in item['skills'] if normalized(s) not in known]
    age = max(0,(service.current-stamp(item['checked_at']).date()).days)
    score = min(40,len(core)*15)+min(20,len(related)*7)+round(20*len(gaps)/max(1,len(item['skills'])))+(10 if age<=30 else 5 if age<=90 else 0)
    if item['duration_minutes'] and item['duration_minutes'] <= service.profile['weekly_minutes']:
        score += 10
    if item['availability'] == 'retired':
        score = 0
    reasons = (['Enfoque: '+', '.join(core)] if core else []) + (['Áreas relacionadas: '+', '.join(related)] if related else [])
    reasons += [f'{len(gaps)} habilidades sin autonomía declarada', f'Fuentes comprobadas hace {age} días']
    return score, ' · '.join(reasons)
