"""Public research facts, separate from personal learning activity."""
from datetime import date
from hashlib import sha256
import ipaddress
from typing import Literal
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from pydantic import Field, field_validator, model_validator
from .models import StrictModel, Name, normalized

CATALOG_TABLES = ('discovery_settings', 'discovery_runs', 'opportunities',
                  'opportunity_sources', 'opportunity_versions', 'pack_components', 'opportunity_choices')
DEFAULT_FOCUS = 'Factory Enablement y apps con IA: datos, automatización y software verificable'
DEFAULT_TAGS = ['Python', 'SQL', 'Power BI', 'automatización', 'datos', 'Factory Enablement', 'apps con IA', 'Streamlit', 'Supabase']
DEFAULT_RELATED = ['redes', 'OT', 'ciberseguridad', 'APIs', 'software', 'sistemas']


def public_url(value):
    if not value:
        return None
    u = urlsplit(value.strip())
    host = (u.hostname or '').lower()
    if u.scheme != 'https' or not host or u.username or u.password or u.port not in (None, 443):
        raise ValueError('Usa una URL HTTPS pública sin credenciales.')
    if '.' not in host or host.endswith(('.local', '.localhost', '.internal', '.test')):
        raise ValueError('La fuente debe ser una página pública.')
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError('No se admiten direcciones IP como fuentes.')
    query = [(k, v) for k, v in parse_qsl(u.query) if not k.lower().startswith('utm_') and k.lower() not in {'fbclid', 'gclid'}]
    return urlunsplit(('https', host.removeprefix('www.'), u.path.rstrip('/') or '/', urlencode(query), ''))


class Source(StrictModel):
    url: str
    title: Name
    evidence: str = Field(default='', max_length=400)
    _url = field_validator('url')(public_url)


class Component(StrictModel):
    title: Name
    url: str
    purpose: str = Field(min_length=1, max_length=700)
    _url = field_validator('url')(public_url)


class Opportunity(StrictModel):
    title: Name
    kind: Literal['certification', 'course', 'resource', 'paper', 'project', 'lab', 'pack']
    provider: Name
    url: str | None = None
    description: str = Field(min_length=1, max_length=1500)
    reason: str = Field(min_length=1, max_length=1200)
    area: Name
    tags: list[Name] = Field(min_length=1, max_length=20)
    topics: list[Name] = Field(min_length=1, max_length=80)
    skills: list[Name] = Field(min_length=1, max_length=30)
    language: Literal['en', 'es', 'en/es'] = 'en'
    level: Literal['introductory', 'intermediate', 'advanced', 'mixed'] = 'mixed'
    prerequisites: str = Field(default='', max_length=1000)
    syllabus_scope: Literal['summary', 'published_outline', 'custom_pack'] = 'summary'
    duration_minutes: int | None = Field(default=None, ge=1, le=600000)
    price_kind: Literal['free', 'one_time', 'subscription', 'mixed', 'unknown'] = 'unknown'
    price_amount: float | None = Field(default=None, ge=0, le=1000000)
    currency: str | None = Field(default=None, pattern=r'^[A-Z]{3}$')
    price_note: str = Field(default='Consultar precio vigente en la fuente.', max_length=700)
    price_evidence: str = Field(default='', max_length=300)
    provider_updated_on: date | None = None
    availability: Literal['available', 'retired', 'uncertain'] = 'available'
    sources: list[Source] = Field(min_length=1, max_length=8)
    components: list[Component] = Field(default_factory=list, max_length=12)
    _url = field_validator('url')(public_url)

    @model_validator(mode='after')
    def consistent(self):
        urls = {s.url for s in self.sources}
        if self.kind == 'pack':
            if len(self.components) < 2 or self.syllabus_scope != 'custom_pack':
                raise ValueError('Un Learning Pack necesita al menos dos recursos y un temario propio.')
        elif not self.url or self.url not in urls or self.components:
            raise ValueError('La oportunidad debe tener su enlace principal entre las fuentes.')
        if any(c.url not in urls for c in self.components):
            raise ValueError('Cada componente requiere su fuente.')
        if self.price_amount is not None and self.price_kind != 'free' and not self.currency:
            raise ValueError('Indica moneda para un precio conocido.')
        if self.price_kind == 'free' and self.price_amount not in (None, 0):
            raise ValueError('Un recurso gratuito no puede tener precio positivo.')
        for field in ('tags', 'topics', 'skills'):
            values = getattr(self, field)
            if len({normalized(v) for v in values}) != len(values):
                raise ValueError('Hay nombres repetidos en ' + field)
        return self

    def identity(self):
        identity = ('pack:' + normalized(self.title)) if self.kind == 'pack' else self.url
        return sha256(identity.encode()).hexdigest()


class ResearchResult(StrictModel):
    opportunities: list[Opportunity] = Field(min_length=0, max_length=8)


class Focus(StrictModel):
    focus: str = Field(min_length=3, max_length=600)
    primary_tags: list[Name] = Field(min_length=1, max_length=15)
    related_tags: list[Name] = Field(default_factory=list, max_length=15)
    weekly_enabled: bool = False
    external_consent: bool = False


def defaults():
    return Focus(focus=DEFAULT_FOCUS, primary_tags=DEFAULT_TAGS, related_tags=DEFAULT_RELATED).model_dump()
