import copy
import json
from uuid import uuid4

import httpx
import pytest

from atlas import catalog, domain, research
from atlas.catalog_models import Opportunity, ResearchResult, defaults, public_url
from atlas.repository import RepositoryError
from atlas.seed import factory_route
from atlas.service import LearningService
from .sql_backend import SQLRepository


def uid(): return str(uuid4())


def sample(**changes):
    return Opportunity.model_validate(dict(title='SQL tutorial',kind='course',provider='Test provider',
        url='https://example.org/sql',description='Introducción a SQL.',reason='Datos operativos.',area='Datos',
        tags=['SQL','datos'],topics=['Consultas','Joins'],skills=['SQL'],
        sources=[{'url':'https://example.org/sql','title':'SQL tutorial','evidence':'Learn SQL queries and joins.'}],**changes))


def enable(service, weekly=False):
    catalog.save_settings(service,{**defaults(),'external_consent':True,'weekly_enabled':weekly},uid())


def put(service, item=None):
    enable(service)
    rid=catalog.begin(service,'manual',uid())
    catalog.publish(service,rid,[item or sample()],{'model':'test'},uid())
    return service.data['opportunities'][0]['id']


def test_seed_is_idempotent_and_has_no_learning_activity(service):
    result=catalog.load_seed(service,uid())
    assert result['added']==54
    before=copy.deepcopy(service.data)
    assert catalog.load_seed(service,uid())['added']==0
    assert service.data==before
    assert len(service.data['opportunity_versions'])==54
    assert not service.data['learning_tracks'] and domain.effort(service.data)==0
    assert not service.data['credentials'] and not service.data['topic_events']


def test_catalog_update_preserves_adopted_progress_and_decisions(service):
    oid=put(service)
    catalog.choose(service,oid,True,'interested',uid())
    service.create_route(factory_route(),uid())
    phase=service.data['goal_phases'][0]['id']
    request=uid()
    first=catalog.adopt(service,oid,phase,request,use_topics=True)
    assert catalog.adopt(service,oid,phase,request,use_topics=True)==first
    tid=first['track_id']
    assert len(service.data['phase_tracks'])==1
    assert service.data['learning_tracks'][0]['favorite']
    assert domain.progress(service.data,tid)['percent']==0 and domain.effort(service.data)==0
    unit=domain.track_units(service.data,tid)[0]
    service.toggle_unit(unit['id'],True,uid())
    personal={t:copy.deepcopy(service.data[t]) for t in ('learning_tracks','units','unit_progress','phase_tracks','opportunity_choices')}
    updated=sample().model_copy(update={'description':'Nueva descripción','topics':['Nuevo tema']})
    rid=catalog.begin(service,'manual',uid())
    catalog.publish(service,rid,[updated.model_dump(mode='json')],{'model':'fallback'},uid())
    assert len(service.data['opportunities'])==1 and len(service.data['opportunity_versions'])==2
    assert all(service.data[t]==rows for t,rows in personal.items())
    assert service.data['opportunities'][0]['id']==oid
    rid=catalog.begin(service,'manual',uid())
    catalog.publish(service,rid,[updated],{'model':'test'},uid())
    assert len(service.data['opportunity_versions'])==2
    catalog.adopt(service,oid,phase,uid(),use_topics=True)
    assert len(service.data['learning_tracks'])==1 and len(service.data['phase_tracks'])==1
    assert domain.progress(service.data,tid)['percent']==50


def test_pack_adoption_creates_components_without_invented_time(service):
    catalog.load_seed(service,uid())
    item=next(o for o in service.data['opportunities'] if o['kind']=='pack')
    components=[p for p in service.data['pack_components'] if p['opportunity_id']==item['id']]
    result=catalog.adopt(service,item['id'],None,uid())
    assert {u['title'] for u in domain.track_units(service.data,result['track_id'])}=={c['title'] for c in components}
    assert {r['url'] for r in service.data['resources'] if r['kind']=='link'}=={c['url'] for c in components}
    assert not service.data['study_sessions'] and not service.data['topic_events']
    assert not service.data['unit_progress'] and not service.data['credentials']


def test_only_one_research_and_no_external_calls_without_consent(service):
    with pytest.raises(ValueError,match='Autoriza'):
        catalog.begin(service,'manual',uid())
    enable(service)
    catalog.begin(service,'manual',uid())
    with pytest.raises(ValueError,match='curso'):
        catalog.begin(LearningService(service.repo),'manual',uid())
    assert len(service.data['discovery_runs'])==1


def fake_web(primary_status=503, fallback_status=200, during=None):
    calls=[]
    def handle(request):
        calls.append(request)
        if request.url.host=='api.tavily.com':
            if request.url.path=='/search':
                return httpx.Response(200,json={'results':[{'url':'https://example.org/sql','title':'SQL','content':'Learn SQL queries and joins.'}],'usage':{'credits':1 if json.loads(request.content)['search_depth']=='basic' else 2}})
            body=json.loads(request.content)
            assert len(body['urls'])<=12
            return httpx.Response(200,json={'results':[{'url':'https://example.org/sql','raw_content':'Learn SQL queries and joins.'}],'usage':{'credits':1}})
        if 'gemini-3.8-flash:' in str(request.url):
            return httpx.Response(primary_status,json={})
        assert 'gemini-3.5-flash-lite:' in str(request.url)
        if during:
            during()
        if fallback_status!=200:
            return httpx.Response(fallback_status,json={})
        return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':ResearchResult(opportunities=[sample()]).model_dump_json()}]}}],
                                        'usageMetadata':{'promptTokenCount':500,'candidatesTokenCount':200}})
    return httpx.MockTransport(handle),calls


@pytest.mark.parametrize('status',[429,503,404])
def test_fallback_reuses_search_and_reports_model(status):
    from atlas.repository import MemoryRepository
    repo=MemoryRepository()
    enable(LearningService(repo))
    transport,calls=fake_web(status)
    result=catalog.refresh(repo,'test-tavily','test-gemini',transport=transport,sleep=lambda _:None)
    assert result['model']=='gemini-3.5-flash-lite' and result['added']==1
    assert len([r for r in calls if r.url.path=='/search'])==4
    assert len([r for r in calls if r.url.path=='/extract'])==1
    assert result['tavily_credits']==7
    assert len(result['attempts'])==(2 if status==404 else 3)


def test_both_models_failing_preserves_catalog_and_records_failure(service):
    put(service)
    old=copy.deepcopy(service.data['opportunities'])
    versions=copy.deepcopy(service.data['opportunity_versions'])
    transport,calls=fake_web(503,429)
    with pytest.raises(research.ResearchError,match='Ambos'):
        catalog.refresh(service.repo,'t','g',transport=transport,sleep=lambda _:None)
    data=service.repo.snapshot()
    assert data['opportunities']==old and data['opportunity_versions']==versions
    failure=next(r for r in data['discovery_runs'] if r['status']=='failed')
    assert len(failure['details']['attempts'])==4
    assert 'test-gemini' not in json.dumps(failure)


def test_weekly_disabled_or_recent_skips_network(service):
    transport=httpx.MockTransport(lambda _:pytest.fail('Unexpected external request'))
    assert 'skipped' in catalog.refresh(service.repo,'t','g',origin='weekly',transport=transport)
    put(service)
    enable(service,weekly=True)
    assert 'skipped' in catalog.refresh(service.repo,'t','g',origin='weekly',transport=transport)


def test_focus_changed_during_research_keeps_prior_records(service):
    put(service)
    before=copy.deepcopy(service.data['opportunities'])
    def change():
        current=LearningService(service.repo)
        catalog.save_settings(current,{**defaults(),'focus':'Nueva dirección profesional','external_consent':True},uid())
    transport,_=fake_web(during=change)
    with pytest.raises(research.ResearchError,match='enfoque cambió'):
        catalog.refresh(service.repo,'t','g',transport=transport,sleep=lambda _:None)
    assert service.repo.snapshot()['opportunities']==before


def test_grounding_rejects_invented_urls_and_prices():
    source=[{'url':'https://example.org/sql','text':'Learn SQL queries and joins.'}]
    good=sample()
    bad_price=good.model_copy(update={'price_kind':'one_time','price_amount':99,'currency':'USD','price_evidence':'Only USD 99'})
    accepted,rejected=research.grounded(ResearchResult(opportunities=[good,bad_price]),source)
    assert len(accepted)==1 and rejected==1
    with pytest.raises(research.ResearchError):
        research.grounded(ResearchResult(opportunities=[good]),[{'url':'https://other.example.org/','text':source[0]['text']}])


def test_bad_key_fails_without_retry_or_fallback():
    transport,calls=fake_web(403)
    with pytest.raises(research.ResearchError,match='clave'):
        research.analyze('test',defaults(),[],transport=transport,sleep=lambda _:pytest.fail('Retry not expected'))
    assert len(calls)==1


@pytest.mark.parametrize('failure',['timeout','malformed','untrusted'])
def test_network_or_invalid_primary_response_falls_back(failure):
    transport,base_calls=fake_web()
    seen=[]
    def handle(request):
        seen.append(str(request.url))
        if 'gemini-3.8-flash:' in str(request.url):
            if failure=='timeout':
                raise httpx.ReadTimeout('local test',request=request)
            bad=sample().model_dump(mode='json')
            bad['sources'][0]['evidence']='This sentence does not appear in the source.'
            raw='{}' if failure=='malformed' else json.dumps({'opportunities':[bad]})
            return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':raw}]}}]})
        return transport.handle_request(request)
    result,info=research.analyze('test',defaults(),[{'url':'https://example.org/sql','text':'Learn SQL queries and joins.'}],
                                 transport=httpx.MockTransport(handle),sleep=lambda _:None)
    assert info['model']=='gemini-3.5-flash-lite' and len(result)==1
    assert len(seen)==(3 if failure=='timeout' else 2)


def test_partial_research_accepts_only_grounded_entries(service):
    enable(service)
    good=sample()
    bad=sample().model_copy(update={'price_kind':'free','price_evidence':'not in the source'})
    accepted,rejected=research.grounded(ResearchResult(opportunities=[good,bad]),[{'url':good.url,'text':good.sources[0].evidence}])
    rid=catalog.begin(service,'manual',uid())
    result=catalog.publish(service,rid,accepted,{'model':'test','rejected':rejected},uid())
    assert result['checked']==1
    assert service.data['discovery_runs'][0]['status']=='partial'


@pytest.mark.parametrize('url',['http://example.org','https://127.0.0.1/x','https://localhost/','https://me:secret@example.org/','https://server.internal/x'])
def test_sources_reject_private_or_credentialed_links(url):
    with pytest.raises(ValueError): public_url(url)


def test_catalog_tables_have_owner_rls_and_cross_owner_fks(sql_engine):
    a,b=SQLRepository(sql_engine),SQLRepository(sql_engine)
    sa,sb=LearningService(a),LearningService(b)
    oid=put(sa)
    sql_engine.actor(b.user_id)
    assert not sql_engine.query('select * from public.opportunities')
    with pytest.raises(RepositoryError):
        b.commit([{'op':'upsert','table':'opportunity_choices','row':{'id':uid(),'opportunity_id':oid}}],uid(),sb.profile['revision'],{'action':'cross-owner'})
    sql_engine.actor(a.user_id)
    with pytest.raises(RepositoryError):
        sql_engine.query("update public.opportunities set title='Bad' where id=$1",[oid])
    sql_engine.actor(None)
    with pytest.raises(RepositoryError): sql_engine.query('select * from public.opportunities')
