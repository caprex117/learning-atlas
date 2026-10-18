"""Complete analytical export. Arrays and related rows use JSON inside CSV cells."""
import csv
import io
import json

from .catalog_models import Opportunity


def rankings(data):
    result = {}
    runs = sorted((r for r in data['discovery_runs'] if r['status'] == 'completed' and r['origin'] == 'seed'),
                  key=lambda r: (r['details'].get('seed_sequence',0), r['finished_at'] or r['started_at']))
    for run in runs:
        for key, value in run['details'].get('rankings', {}).items():
            result[key] = {**value, 'ranked_at': run['details'].get('research_checked_at'),
                           'ranking_focus': run['focus_snapshot']['focus']}
    return result


def safe_cell(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    if value is None:
        return ''
    if isinstance(value, str) and (value.startswith(('\t', '\r', '\n')) or value.lstrip().startswith(('=', '+', '-', '@'))):
        return "'" + value
    return value


def records(service):
    from .catalog import relevance
    rank = rankings(service.data)
    choices = {r['opportunity_id']: r for r in service.data['opportunity_choices']}
    result = []
    for item in sorted(service.data['opportunities'], key=lambda r: (rank.get(r['identity_key'], {}).get('rank', 1000000), r['title'])):
        oid = item['id']
        priority = rank.get(item['identity_key'], {})
        choice = choices.get(oid, {})
        score, explanation = relevance(service, item)
        row = {'priority_rank': priority.get('rank'), 'title': item['title'], 'kind': item['kind'],
               'area': item['area'], 'phase': priority.get('phase'), 'priority_band': priority.get('priority_band')}
        row.update({k: item.get(k) for k in Opportunity.model_fields if k not in ('sources', 'components')})
        row.update({k: item.get(k) for k in ('id', 'identity_key', 'checked_at', 'provider_updated_on', 'origin', 'research_focus', 'content_hash', 'created_at')})
        row.update({'study_slice_minutes': priority.get('study_slice_minutes'), 'study_slice': priority.get('study_slice'),
                    'ranking_rationale': priority.get('rationale'), 'ranked_at': priority.get('ranked_at'),
                    'ranking_focus': priority.get('ranking_focus'), 'relevance_score': score, 'relevance_reason': explanation,
                    'favorite': choice.get('favorite', False), 'decision': choice.get('decision', ''),
                    'track_id': choice.get('track_id'), 'choice_updated_record': {k:v for k,v in choice.items() if k != 'user_id'}})
        for name, table in [('sources', 'opportunity_sources'), ('components', 'pack_components'), ('versions', 'opportunity_versions')]:
            children = [{k:v for k,v in r.items() if k != 'user_id'} for r in service.data[table] if r['opportunity_id'] == oid]
            row[name] = sorted(children, key=lambda r: r['sort_order'] if name == 'components' else str(r.get('checked_at', '')) + r['id'])
        result.append(row)
    return result


def export_csv(service):
    rows = records(service)
    stream = io.StringIO(newline='')
    fields = list(rows[0]) if rows else ['priority_rank', 'title', 'kind', 'area', 'url']
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\r\n')
    writer.writeheader()
    writer.writerows({k: safe_cell(v) for k,v in row.items()} for row in rows)
    return stream.getvalue().encode('utf-8-sig')
