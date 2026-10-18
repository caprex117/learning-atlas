"""Versioned manual research; upgrades old curated rows without reverting live research."""
import json
from pathlib import Path
from uuid import uuid4

from .catalog_models import Opportunity
from .models import canonical_hash
from .service import Batch


def read_seed():
    seed = json.loads((Path(__file__).resolve().parents[1]/'data/catalog_seed.json').read_text(encoding='utf-8'))
    items = [Opportunity.model_validate(i) for i in seed['opportunities']]
    keys = {i.identity() for i in items}
    if len(keys) != len(items) or set(seed['rankings']) != keys:
        raise ValueError('La selección y sus prioridades no coinciden.')
    if sorted(r['rank'] for r in seed['rankings'].values()) != list(range(1, len(items)+1)):
        raise ValueError('Las prioridades deben ser únicas y consecutivas.')
    return seed


def seed_batch(data, seed):
    from .catalog import now, stamp
    items = [Opportunity.model_validate(i) for i in seed['opportunities']]
    existing = {o['identity_key']:o for o in data['opportunities']}
    candidates = []
    for item in items:
        old = existing.get(item.identity())
        digest = canonical_hash(item.model_dump(mode='json'))
        if not old or (old['origin'] == 'curated' and stamp(old['checked_at']) <= stamp(seed['checked_at']) and old['content_hash'] != digest):
            candidates.append((item, old, digest))
    loaded = any(r['status'] == 'completed' and r['origin'] == 'seed' and r['details'].get('seed_revision') == seed['seed_revision'] for r in data['discovery_runs'])
    summary = {'added':sum(old is None for _,old,_ in candidates), 'changed':sum(old is not None for _,old,_ in candidates),
               'checked':len(items), 'preserved':len(items)-len(candidates)}
    if not candidates and loaded:
        return None, summary
    batch = Batch(data)
    checked_at = seed['checked_at']
    current = now().isoformat()
    rid = batch.put('discovery_runs', {'status':'completed','origin':'seed','started_at':current,'finished_at':current,
        'model_id':'curated','focus_snapshot':seed['focus'], 'error_message':'',
        'details':{**summary, 'seed_revision':seed['seed_revision'],'seed_sequence':seed.get('seed_sequence',0),'rankings':seed['rankings'],
                   'research_checked_at':checked_at, 'method':seed['note']}})
    for item,old,digest in candidates:
        full = item.model_dump(mode='json')
        oid = batch.put('opportunities', {**item.model_dump(mode='json', exclude={'sources','components'}),
            'id':old['id'] if old else str(uuid4()), 'identity_key':item.identity(), 'checked_at':checked_at,
            'content_hash':digest,'origin':'curated','research_focus':seed['focus']['focus']})
        previous = [v for v in data['opportunity_versions'] if v['opportunity_id'] == oid]
        before = max(previous, key=lambda v:v['checked_at'])['payload'] if previous else {}
        batch.put('opportunity_versions', {'opportunity_id':oid,'run_id':rid,'content_hash':digest,
            'payload':full,'changed_fields':[k for k,v in full.items() if before.get(k) != v],'checked_at':checked_at})
        for table in ('opportunity_sources','pack_components'):
            for row in list(batch.data[table]):
                if row['opportunity_id'] == oid:
                    batch.remove(table, row['id'])
        for src in item.sources:
            batch.put('opportunity_sources', {'opportunity_id':oid, **src.model_dump(), 'checked_at':checked_at})
        for index, part in enumerate(item.components):
            batch.put('pack_components', {'opportunity_id':oid, **part.model_dump(), 'sort_order':index})
    return batch, summary
