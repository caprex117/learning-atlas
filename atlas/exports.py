"""User-facing CSV exports with full provenance and spreadsheet-safe cells."""
import csv
import io
import json
from . import domain


def csv_bytes(rows, fields):
    out=io.StringIO(newline='')
    writer=csv.DictWriter(out,fieldnames=fields,extrasaction='ignore')
    writer.writeheader()
    for row in rows:
        cells={}
        for key in fields:
            value=row.get(key)
            if isinstance(value,(list,dict)):
                value=json.dumps(value,ensure_ascii=False,default=str)
            if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@','\t','\r')):
                value="'"+value
            cells[key]=value
        writer.writerow(cells)
    return out.getvalue().encode('utf-8-sig')


def abilities_records(data):
    rows=[]
    for skill in sorted(data['skills'],key=lambda s:s['name'].casefold()):
        stats=domain.skill_stats(data,skill['id'])
        tracks=[t for t in data['learning_tracks'] if t['id'] in stats['track_ids']]
        topics=[t for t in data['topics'] if any(r['skill_id']==skill['id'] and r['topic_id']==t['id'] for r in data['topic_skills'])]
        session_ids={r['session_id'] for r in data['session_skills'] if r['skill_id']==skill['id']}
        sessions=[s for s in domain.active_sessions(data) if s['id'] in session_ids]
        assessments=[a for a in data['skill_assessments'] if a['skill_id']==skill['id'] and not a.get('voided')]
        rows.append({'habilidad':skill['name'],'definicion':skill.get('definition',''),
            'minutos_practicados':stats['minutes'],'sesiones':stats['sessions'],
            'aprendizajes_relacionados':[{'nombre':t['title'],'estado':t['status'],'enlace':t.get('source_url')} for t in tracks],
            'temas_relacionados':[t['name'] for t in topics],
            'practicas':[{'fecha':s['occurred_on'],'tipo':s['activity_type'],'notas':s.get('notes','')} for s in sessions],
            'trabajos':[{'titulo':e['title'],'url':e.get('url'),'fecha':e.get('occurred_on'),'estado':e['validation_status']} for e in stats['evidence']],
            'credenciales_relacionadas':[{'nombre':c['official_name'],'emisor':c['issuer']} for c in data['credentials'] if c.get('track_id') in stats['track_ids']],
            'autoevaluaciones':[{'fecha':a['occurred_on'],'nivel':a['level'],'contexto':a['context'],'rubrica':a['rubric_id']} for a in assessments],
            'interpretacion':'Contenido relacionado y práctica registrada; no certifica dominio.'})
    return rows


def abilities_csv(data):
    return csv_bytes(abilities_records(data),['habilidad','definicion','minutos_practicados','sesiones','aprendizajes_relacionados','temas_relacionados','practicas','trabajos','credenciales_relacionadas','autoevaluaciones','interpretacion'])


CREDENTIAL_FIELDS=['official_name','issuer','credential_type','program_code','credential_code','earned_on','period_label','expires_on','never_expires','verification_url','document_url','notes']


def credentials_csv(rows):
    return csv_bytes(rows,CREDENTIAL_FIELDS)
