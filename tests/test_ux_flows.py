import copy
import json
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4
import httpx
import pytest
from atlas import assistant, catalog, domain, research, research_policy as policy
from atlas.catalog_models import ResearchResult, defaults
from atlas.credential_drafts import CredentialDraft, save_batch, parse_csv, merge_drafts
from atlas.exports import abilities_csv, abilities_records, credentials_csv
from atlas.models import ImportProposal, TrackDraft, SessionDraft
from atlas.repository import MemoryRepository
from atlas.service import LearningService
from atlas.seed import factory_route
from .test_catalog import sample, enable, put, fake_web


def uid(): return str(uuid4())


def credential(**changes):
    return {'official_name':'Test Professional Certificate','issuer':'Test issuer','credential_type':'program',
            'program_code':'TEST-1','credential_code':'personal-123','document_url':'https://drive.google.com/file/example',
            'period_label':'Spring 2025',**changes}


def test_reviewed_credential_batch_is_atomic_idempotent_and_does_not_invent_learning(service):
    rows=[credential(),credential(official_name='Second certificate')]
    with pytest.raises(ValueError,match='Revisa'):
        save_batch(service,rows,uid())
    before=copy.deepcopy(service.data)
    with pytest.raises(ValueError,match='futura'):
        save_batch(service,[rows[0],credential(earned_on=(service.current+timedelta(days=1)).isoformat())],uid(),reviewed=True)
    assert service.data==before
    request=uid()
    first=save_batch(service,rows,request,reviewed=True)
    assert first['added']==2
    assert save_batch(service,rows,request,reviewed=True)==first
    assert save_batch(service,rows,uid(),reviewed=True)['skipped']==2
    assert len(service.data['credentials'])==2
    assert all(c['verification_status']=='self_reported' for c in service.data['credentials'])
    assert not service.data['study_sessions'] and not service.data['unit_progress'] and not service.data['topic_events']
    assert service.data['credentials'][0]['credential_code']=='personal-123'
    assert parse_csv(credentials_csv(service.data['credentials']))[0]['document_url'].startswith('https://drive.google.com')


def test_csv_protects_formulas_and_preserves_unknown_dates():
    data=CredentialDraft.model_validate(credential(official_name='=SUM(1,2)')).model_dump(mode='json')
    raw=credentials_csv([data])
    assert b"'=SUM" in raw
    restored=parse_csv(raw)[0]
    assert restored['official_name']=='=SUM(1,2)' and restored['earned_on'] is None


def test_assistant_accumulates_credentials_without_dropping_old_rows_or_known_dates():
    previous=[CredentialDraft.model_validate(credential(earned_on='2025-04-01')).model_dump(mode='json')]
    next_row=CredentialDraft.model_validate(credential(official_name='Another title',credential_code='another'))
    accumulated=merge_drafts(previous,[next_row])
    assert len(accumulated)==2 and accumulated[0]['earned_on']=='2025-04-01'
    corrected=merge_drafts(accumulated,[CredentialDraft.model_validate(credential(notes='Confirmed issuer'))])
    assert len(corrected)==2 and corrected[0]['earned_on']=='2025-04-01'


def test_import_txt_roundtrip_does_not_call_ai():
    proposal=ImportProposal(tracks=[TrackDraft(title='Mi curso',units=[{'key':'u','title':'Práctica'}])])
    assert assistant.proposal_from_text(assistant.import_text(proposal))==proposal
    assert assistant.proposal_from_text('Un texto normal') is None


def test_abilities_export_includes_coverage_real_practice_and_assessment(service):
    track=TrackDraft(title='SQL course',kind='course',skills=[{'name':'SQL'}],topics=[{'name':'JOIN','skills':['SQL']}])
    service.create_track(track,uid())
    tid=service.data['learning_tracks'][0]['id'];sid=service.data['skills'][0]['id']
    service.record_session(SessionDraft(occurred_on=service.current,duration_minutes=25,area_id=service.data['areas'][0]['id'],track_id=tid,skill_ids=[sid],activity_type='work_practice',notes='Cruzar tablas'),uid())
    service.assess(sid,service.current,2,'Resuelvo joins',None,uid())
    row=abilities_records(service.data)[0]
    assert row['minutos_practicados']==25
    assert row['aprendizajes_relacionados'][0]['nombre']=='SQL course'
    assert row['practicas'][0]['tipo']=='work_practice'
    assert row['autoevaluaciones'][0]['nivel']==2
    assert 'Cruzar tablas' in abilities_csv(service.data).decode('utf-8-sig')


def test_link_imported_learning_to_phase_without_progress(service):
    service.create_route(factory_route(),uid())
    service.create_track(TrackDraft(title='New course'),uid())
    pid=service.data['goal_phases'][0]['id'];tid=service.data['learning_tracks'][0]['id']
    service.link_phase(pid,[tid],uid())
    service.link_phase(pid,[tid],uid())
    assert len(service.data['phase_tracks'])==1
    assert not service.data['unit_progress'] and not service.data['study_sessions']
    service.link_phase(pid,[],uid())
    assert not service.data['phase_tracks']


def test_refresh_has_hard_new_and_existing_limits_and_keeps_history(service):
    enable(service)
    originals=[sample().model_copy(update={'url':f'https://example.org/old{i}','title':f'Old {i}','sources':[sample().sources[0].model_copy(update={'url':f'https://example.org/old{i}'})]}) for i in range(4)]
    rid=catalog.begin(service,'seed',uid())
    catalog.publish(service,rid,originals,{},uid(),origin='curated')
    newer=[o.model_copy(update={'description':'New details'}) for o in originals]
    additions=[sample().model_copy(update={'url':f'https://example.org/new{i}','title':f'New {i}','sources':[sample().sources[0].model_copy(update={'url':f'https://example.org/new{i}'})]}) for i in range(7)]
    rid=catalog.begin(service,'manual',uid())
    result=catalog.publish(service,rid,newer+additions,{},uid())
    assert result['added']==5 and result['checked']==8
    assert len(service.data['opportunities'])==9
    assert next(o for o in service.data['opportunities'] if o['title']=='Old 3')['description']!='New details'


def test_research_zero_opportunities_is_valid():
    assert research.grounded(ResearchResult(opportunities=[]),[])==([],0)


def test_budget_is_reserved_before_calls_and_failed_attempts_count(service):
    enable(service)
    for _ in range(5):
        rid=catalog.begin(service,'manual',uid(),reserved_credits=8)
        from atlas.service import Batch
        b=Batch(service.data);r=b.find('discovery_runs',rid)
        b.put('discovery_runs',{**r,'status':'failed','finished_at':catalog.now().isoformat()})
        service._commit(b,uid(),{'finish':rid})
    assert policy.spent(service.data)==40
    transport=httpx.MockTransport(lambda _:pytest.fail('Must stop before network'))
    with pytest.raises(ValueError,match='mensual'):
        catalog.refresh(service.repo,'t','g',transport=transport)
    with pytest.raises(ValueError,match='mensual'):
        assistant.lookup_name(service.repo,'t','Public name',transport=transport)


def test_schedule_waits_twenty_one_days_and_lookup_does_not_reset_it(service,monkeypatch):
    put(service);enable(service,weekly=True)
    due=policy.next_due(service.data)
    latest=max(policy.timestamp(r['finished_at']) for r in policy.catalog_runs(service.data))
    assert due-latest==timedelta(days=21)
    monkeypatch.setattr(catalog,'now',lambda:due-timedelta(seconds=1))
    transport=httpx.MockTransport(lambda _:pytest.fail('No request before due date'))
    assert 'skipped' in catalog.refresh(service.repo,'t','g',origin='weekly',transport=transport)
    run={'origin':'manual','status':'completed','started_at':due.isoformat(),'finished_at':due.isoformat(),'details':{'purpose':'name_lookup','tavily_credits':2}}
    assert policy.next_due({**service.data,'discovery_runs':service.data['discovery_runs']+[run]})==due


def test_name_lookup_uses_two_calls_and_shared_accounting(service):
    enable(service)
    calls=[]
    def handle(request):
        calls.append(json.loads(request.content))
        if request.url.path=='/search':
            return httpx.Response(200,json={'results':[{'url':'https://example.org/official','title':'Official'}],'usage':{'credits':1}})
        return httpx.Response(200,json={'results':[{'url':'https://example.org/official','raw_content':'Official professional certificate.'}],'usage':{'credits':1}})
    sources=assistant.lookup_name(service.repo,'key','Public certificate',transport=httpx.MockTransport(handle))
    data=service.repo.snapshot()
    assert len(calls)==2 and len(sources)==1 and policy.spent(data)==2
    assert calls[0]['search_depth']=='basic' and len(calls[1]['urls'])<=5
    assert not data['credentials'] and policy.next_due(data) is None


def test_assistant_fallback_and_no_invented_source_links():
    calls=[]
    def handle(request):
        calls.append(request)
        body=assistant.Reply(message='Nombre sugerido: revisa el emisor.',credentials=[CredentialDraft.model_validate(credential())]).model_dump_json()
        if len(calls)==1: return httpx.Response(503)
        return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':body}]}}]})
    result=assistant.converse('credentials','Obtuve un certificado',[],[],[],'test','primary',transport=httpx.MockTransport(handle))
    assert result.credentials[0].program_code=='TEST-1'
    assert len(calls)==2 and 'gemini-3.5-flash-lite' in str(calls[1].url)
    assert all(r.url.host=='generativelanguage.googleapis.com' for r in calls)
