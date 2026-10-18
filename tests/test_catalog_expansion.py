import copy
import json
from pathlib import Path
from uuid import uuid4

from atlas import catalog, domain
from atlas.catalog_export import rankings
from atlas.catalog_models import Opportunity
from atlas.catalog_seed import read_seed, seed_batch
from atlas.service import LearningService
from .sql_backend import SQLRepository
from .test_catalog_initial_research import run_sql


def uid(): return str(uuid4())


def test_expand_40_to_54_preserves_original_facts_and_learning(service):
    seed=json.loads((Path(__file__).parent/'fixtures/catalog_seed_v2_40.json').read_text(encoding='utf-8'))
    batch,summary=seed_batch(service.data,seed)
    service._commit(batch,uid(),{'action':'legacy40'},summary)
    original={o['identity_key']:copy.deepcopy(o) for o in service.data['opportunities']}
    oid=service.data['opportunities'][0]['id']
    catalog.choose(service,oid,True,'interested',uid())
    tid=catalog.adopt(service,oid,None,uid(),use_topics=True)['track_id']
    service.toggle_unit(domain.track_units(service.data,tid)[0]['id'],True,uid())
    personal={t:copy.deepcopy(service.data[t]) for t in ('learning_tracks','resources','units','unit_progress','opportunity_choices','study_sessions','topic_events','credentials')}
    result=catalog.load_seed(service,uid())
    assert result=={'added':14,'changed':0,'checked':54,'preserved':40}
    assert len(service.data['opportunities'])==len(service.data['opportunity_versions'])==54
    assert all(o==original[o['identity_key']] for o in service.data['opportunities'] if o['identity_key'] in original)
    assert all(service.data[t]==v for t,v in personal.items())
    assert sorted(v['rank'] for v in rankings(service.data).values())==list(range(1,55))
    before=copy.deepcopy(service.data)
    catalog.load_seed(service,uid())
    assert service.data==before


def test_four_projects_adopt_as_planned_without_inventing_activity(service):
    catalog.load_seed(service,uid())
    projects=[o for o in service.data['opportunities'] if o['kind']=='project']
    assert len(projects)==4
    for o in projects:
        assert any(t.startswith('Aceptación:') for t in o['topics'])
        assert o['duration_minutes'] is None  # Suggested first block is not a full project estimate.
        result=catalog.adopt(service,o['id'],None,uid(),use_topics=True)
        track=next(t for t in service.data['learning_tracks'] if t['id']==result['track_id'])
        assert track['kind']=='project' and track['status']=='planned'
        assert {u['title'] for u in domain.track_units(service.data,track['id'])}==set(o['topics'])
        assert domain.progress(service.data,track['id'])['percent']==0
    assert domain.effort(service.data)==0
    assert not service.data['topic_events'] and not service.data['credentials']


def test_sql_expansion_after_40_and_old_loader_does_not_revert_latest_priority(sql_engine):
    repo=SQLRepository(sql_engine)
    historical=(Path(__file__).resolve().parents[1]/'supabase/seeds/learning_catalog_40.sql').read_text(encoding='utf-8')
    run_sql(sql_engine,repo.user_id,historical)
    before=repo.snapshot()
    run_sql(sql_engine,repo.user_id)
    after=repo.snapshot()
    assert len(after['opportunities'])==54
    assert len(after['opportunity_versions'])==54
    original={o['id']:o for o in before['opportunities']}
    assert all(o==original[o['id']] for o in after['opportunities'] if o['id'] in original)
    assert any(r['details']['added']==14 for r in after['discovery_runs'])
    # A fresh owner loads 54 first, then accidentally executes the historical 40 loader.
    newer=SQLRepository(sql_engine)
    run_sql(sql_engine,newer.user_id)
    expected=rankings(newer.snapshot())
    run_sql(sql_engine,newer.user_id,historical)
    assert rankings(newer.snapshot())==expected
    assert len(newer.snapshot()['opportunities'])==54


def test_original_40_are_identical_and_fourteen_are_unique():
    old=json.loads((Path(__file__).parent/'fixtures/catalog_seed_v2_40.json').read_text(encoding='utf-8'))
    prior={Opportunity.model_validate(i).identity():i for i in old['opportunities']}
    current={Opportunity.model_validate(i).identity():i for i in read_seed()['opportunities']}
    assert len(set(current)-set(prior))==14 and not set(prior)-set(current)
    assert all(current[k]==v for k,v in prior.items())
    assert not any(i['title'].startswith('WCAG') for i in current.values())
    assert any(i['kind']=='project' and i['url']=='https://playwright.dev/docs/intro' for i in current.values())
