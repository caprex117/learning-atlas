import copy
import csv
import io
import json
from pathlib import Path
from uuid import uuid4

import pytest

from atlas import catalog, domain
from atlas.catalog_export import export_csv, rankings
from atlas.catalog_seed import read_seed
from atlas.catalog_models import Opportunity
from atlas.models import canonical_hash
from atlas.repository import MemoryRepository, RepositoryError
from atlas.service import LearningService
from scripts.build_catalog_seed_sql import build
from .sql_backend import SQLRepository


def uid(): return str(uuid4())


def legacy(service):
    old=json.loads((Path(__file__).parent/'fixtures/catalog_seed_v1.json').read_text(encoding='utf-8'))
    rid=catalog.begin(service,'seed',uid())
    catalog.publish(service,rid,old['opportunities'],{},uid(),checked_at=old['checked_at'],origin='curated')
    return old


def test_upgrade_legacy_17_preserves_ids_choices_progress_and_newer_research(service):
    legacy(service)
    ids={o['identity_key']:o['id'] for o in service.data['opportunities']}
    chosen=service.data['opportunities'][0]
    catalog.choose(service,chosen['id'],True,'interested',uid())
    tid=catalog.adopt(service,chosen['id'],None,uid(),use_topics=True)['track_id']
    service.toggle_unit(domain.track_units(service.data,tid)[0]['id'],True,uid())
    personal={t:copy.deepcopy(service.data[t]) for t in ('learning_tracks','opportunity_choices','units','unit_progress','resources','track_resources')}
    # Two independently newer research rows must not be reverted, even if one is curated.
    newer=service.data['opportunities'][1:3]
    from atlas.service import Batch
    b=Batch(service.data)
    for i,o in enumerate(newer):
        b.put('opportunities',{**o,'origin':'ai' if i==0 else 'curated','checked_at':'2026-10-19T00:00:00+00:00','description':'Newer verified facts'})
    service._commit(b,uid(),{'test':'newer'})
    result=catalog.load_seed(service,uid())
    assert result['added']==37 and result['changed']==15 and result['preserved']==2
    assert len(service.data['opportunities'])==54
    assert all(ids[o['identity_key']]==o['id'] for o in service.data['opportunities'] if o['identity_key'] in ids)
    assert all(service.data[t]==rows for t,rows in personal.items())
    assert all(next(o for o in service.data['opportunities'] if o['id']==v['id'])['description']=='Newer verified facts' for v in newer)
    assert len(rankings(service.data))==54
    before=copy.deepcopy(service.data)
    assert catalog.load_seed(service,uid())['added']==0
    assert service.data==before


def test_complete_csv_nested_records_prices_unicode_and_formula_safety(service):
    catalog.load_seed(service,uid())
    first=min(service.data['opportunities'],key=lambda o:rankings(service.data)[o['identity_key']]['rank'])
    catalog.choose(service,first['id'],True,'dismissed',uid())
    from atlas.service import Batch
    b=Batch(service.data)
    b.put('opportunities',{**first,'title':'=1+1','description':'  @SUM(1,2)','price_note':'Español, "comillas"\ny nueva línea'})
    service._commit(b,uid(),{'test':'csv'})
    binary=export_csv(service)
    assert binary.startswith(b'\xef\xbb\xbf')
    rows=list(csv.DictReader(io.StringIO(binary.decode('utf-8-sig'))))
    assert len(rows)==54 and [int(r['priority_rank']) for r in rows]==list(range(1,55))
    assert rows[0]['title']=="'=1+1" and rows[0]['description']=="'  @SUM(1,2)"
    assert rows[0]['price_note']=='Español, "comillas"\ny nueva línea'
    assert rows[0]['favorite']=='True' and rows[0]['decision']=='dismissed'
    assert len(json.loads(rows[0]['components']))==3
    assert json.loads(rows[0]['versions'])[0]['payload']['title'].startswith('Learning Pack')
    assert all(json.loads(r['sources']) and json.loads(r['topics']) and json.loads(r['skills']) for r in rows)
    paid=next(r for r in rows if 'CCNA' in r['title'])
    assert float(paid['price_amount'])==300 and paid['currency']=='USD'
    unknown=next(r for r in rows if 'PL-300' in r['title'])
    assert unknown['price_amount']=='' and unknown['duration_minutes']==''
    assert service.repo.user_id not in binary.decode('utf-8-sig')


def run_sql(harness, user, text=None):
    sql=text or build()
    if user:
        sql=sql.replace('target_user uuid := NULL;',f"target_user uuid := '{user}';")
    harness.exec('reset role')
    try:
        harness.exec(sql)
    except Exception:
        harness.exec('rollback')
        raise


def test_sql_editor_loader_same_data_idempotent_and_owner_isolated(sql_engine):
    a,b=SQLRepository(sql_engine),SQLRepository(sql_engine)
    other=LearningService(b)
    catalog.load_seed(other,uid())
    untouched=copy.deepcopy(other.data)
    run_sql(sql_engine,a.user_id)
    service=LearningService(a)
    assert len(service.data['opportunities'])==54
    assert len(service.data['opportunity_sources'])==99
    assert len(service.data['pack_components'])==27
    assert len(service.data['opportunity_versions'])==54
    expected={Opportunity.model_validate(i).identity():canonical_hash(i) for i in read_seed()['opportunities']}
    assert {o['identity_key']:o['content_hash'] for o in service.data['opportunities']}==expected
    assert len(rankings(service.data))==54 and not service.data['learning_tracks']
    before=copy.deepcopy(service.data)
    run_sql(sql_engine,a.user_id)
    assert a.snapshot()==before and b.snapshot()==untouched
    assert catalog.load_seed(LearningService(a),uid())['added']==0


def test_sql_editor_upgrades_legacy_without_touching_learning(sql_engine):
    repo=SQLRepository(sql_engine)
    service=LearningService(repo)
    legacy(service)
    first=service.data['opportunities'][0]
    catalog.choose(service,first['id'],True,'interested',uid())
    tid=catalog.adopt(service,first['id'],None,uid(),use_topics=True)['track_id']
    service.toggle_unit(domain.track_units(service.data,tid)[0]['id'],True,uid())
    before=copy.deepcopy(service.data)
    run_sql(sql_engine,repo.user_id)
    data=repo.snapshot()
    for table in ('learning_tracks','units','unit_progress','opportunity_choices','resources','track_resources'):
        assert data[table]==before[table]
    assert len(data['opportunities'])==54 and len(data['opportunity_versions'])==71


def test_sql_editor_requires_owner_and_rolls_back_on_failure(sql_engine):
    repo=SQLRepository(sql_engine)
    SQLRepository(sql_engine)
    before=repo.snapshot()
    with pytest.raises(RepositoryError,match='CATALOG_OWNER_REQUIRED'):
        run_sql(sql_engine,None)
    assert repo.snapshot()==before


def test_sql_editor_atomic_failure(sql_engine):
    repo=SQLRepository(sql_engine)
    before=repo.snapshot()
    broken=build().replace('"kind": "pack"','"kind": "invalid"',1)
    with pytest.raises(RepositoryError):
        run_sql(sql_engine,repo.user_id,broken)
    assert repo.snapshot()==before
    with pytest.raises(RepositoryError,match='CATALOG_PROFILE_MISSING'):
        run_sql(sql_engine,uid())


def test_seed_sources_and_priority_are_complete():
    seed=read_seed()
    assert len(seed['opportunities'])==54
    assert sum(i['kind']=='pack' for i in seed['opportunities'])==7
    assert any(i['area']=='Apps con IA' and i['kind']=='pack' for i in seed['opportunities'])
    assert all(i['prerequisites'] and i['reason'] and i['price_note'] for i in seed['opportunities'])
    assert (Path(__file__).resolve().parents[1]/'supabase/seeds/learning_catalog_54.sql').read_text(encoding='utf-8')==build()
