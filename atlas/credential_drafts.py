"""Reviewed credential batches; no implicit course completion or claimed verification."""
import csv
import io
from datetime import date
from typing import Literal
from pydantic import Field, field_validator, model_validator
from .models import StrictModel, Name, normalized, safe_url
from .service import Batch


class CredentialDraft(StrictModel):
    official_name: Name
    issuer: Name
    credential_type: Literal['professional','course','program','badge']='course'
    program_code: str=Field(default='',max_length=100)
    credential_code: str=Field(default='',max_length=200)
    earned_on: date|None=None
    period_label: str=Field(default='',max_length=100)
    expires_on: date|None=None
    never_expires: bool=False
    verification_url: str|None=None
    document_url: str|None=None
    notes: str=Field(default='',max_length=5000)
    _urls=field_validator('verification_url','document_url')(safe_url)

    @model_validator(mode='after')
    def dates(self):
        if self.expires_on and self.never_expires:
            raise ValueError('Indica fecha de vencimiento o que no caduca; no ambas.')
        if self.expires_on and self.earned_on and self.expires_on<self.earned_on:
            raise ValueError('La caducidad no puede ser anterior a la obtención.')
        return self


def identity(row):
    return tuple(normalized(str(row.get(k) or '')) for k in ('official_name','issuer','credential_code','earned_on','period_label'))


def merge_drafts(previous, incoming):
    """The model may enrich rows but cannot silently delete the accumulated draft."""
    rows=[dict(r) for r in previous]
    for item in incoming:
        values=item.model_dump(mode='json') if isinstance(item,CredentialDraft) else dict(item)
        match=next((i for i,r in enumerate(rows) if
            (values.get('credential_code') and values['credential_code']==r.get('credential_code') and normalized(values['issuer'])==normalized(r['issuer'])) or
            (normalized(values['official_name'])==normalized(r['official_name']) and normalized(values['issuer'])==normalized(r['issuer']))),None)
        if match is None:
            rows.append(values)
        else:
            rows[match]={**rows[match],**{k:v for k,v in values.items() if v not in ('',None) and not(k=='never_expires' and not v)}}
    if len(rows)>50:
        raise ValueError('Guarda o descarga este lote antes de añadir más: máximo 50 credenciales por revisión.')
    return rows


def parse_csv(contents):
    if len(contents)>2_000_000:
        raise ValueError('Divide el CSV en archivos de menos de 2 MB.')
    reader=csv.DictReader(io.StringIO(contents.decode('utf-8-sig')))
    if not {'official_name','issuer'}.issubset(reader.fieldnames or []):
        raise ValueError('Usa el CSV descargado aquí; necesita las columnas official_name e issuer.')
    rows=[]
    for row in reader:
        if len(rows)>=50:
            raise ValueError('Revisa un máximo de 50 credenciales por lote.')
        if None in row:
            raise ValueError('El CSV contiene columnas desalineadas.')
        values={k:v for k,v in row.items() if k in CredentialDraft.model_fields and v not in ('',None)}
        for k,v in values.items():
            if v.startswith("'") and v[1:].lstrip().startswith(('=','+','-','@','\t','\r')):
                values[k]=v[1:]
        rows.append(CredentialDraft.model_validate(values).model_dump(mode='json'))
    if not rows:
        raise ValueError('El archivo no contiene credenciales.')
    return rows


def save_batch(service, rows, request_id, *, reviewed=False):
    if not reviewed:
        raise ValueError('Revisa la tabla y confirma que son credenciales que ya obtuviste.')
    if not 1<=len(rows)<=50:
        raise ValueError('Revisa entre 1 y 50 credenciales por lote.')
    validated=[CredentialDraft.model_validate(r).model_dump(mode='json') for r in rows]
    b=Batch(service.data)
    known={identity(c) for c in b.data['credentials']}
    added=0
    for row in validated:
        if row['earned_on'] and date.fromisoformat(row['earned_on'])>service.current:
            raise ValueError('Una credencial obtenida no puede tener fecha futura.')
        key=identity(row)
        if key in known:
            continue
        known.add(key)
        # Empty optional new columns remain compatible until migration 003 is installed.
        columns={k:v for k,v in row.items() if k not in {'program_code','credential_code','document_url'} or v}
        b.put('credentials',{**columns,'track_id':None,'verification_status':'self_reported'})
        added+=1
    return service._commit(b,request_id,{'action':'credential_batch','rows':validated},{'added':added,'skipped':len(rows)-added})
