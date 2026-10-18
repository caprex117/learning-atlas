"""Additive migration; the installed 001 migration is never rewritten."""
from pathlib import Path
from atlas.catalog_models import CATALOG_TABLES

ROOT = Path(__file__).resolve().parents[1]
FIELDS = {
'discovery_settings': """focus text not null, primary_tags jsonb not null check(jsonb_typeof(primary_tags)='array'),
 related_tags jsonb not null check(jsonb_typeof(related_tags)='array'), weekly_enabled boolean not null default false,
 external_consent boolean not null default false, check(id=user_id)""",
'discovery_runs': """status text not null check(status in ('running','completed','partial','failed')),
 origin text not null check(origin in ('manual','weekly','seed')), started_at timestamptz not null,
 finished_at timestamptz, model_id text, focus_snapshot jsonb not null default '{}',
 details jsonb not null default '{}', error_message text not null default ''""",
'opportunities': """identity_key text not null, title text not null, kind text not null
 check(kind in ('certification','course','resource','paper','project','lab','pack')),
 provider text not null, url text, description text not null, reason text not null, area text not null,
 tags jsonb not null check(jsonb_typeof(tags)='array'), topics jsonb not null check(jsonb_typeof(topics)='array'),
 skills jsonb not null check(jsonb_typeof(skills)='array'), language text not null check(language in ('en','es','en/es')),
 level text not null check(level in ('introductory','intermediate','advanced','mixed')), prerequisites text not null default '',
 syllabus_scope text not null check(syllabus_scope in ('summary','published_outline','custom_pack')),
 duration_minutes integer check(duration_minutes>0), price_kind text not null check(price_kind in ('free','one_time','subscription','mixed','unknown')),
 price_amount numeric check(price_amount>=0),
 currency text, price_note text not null, price_evidence text not null default '', provider_updated_on date,
 availability text not null check(availability in ('available','retired','uncertain')), checked_at timestamptz not null,
 content_hash text not null, origin text not null check(origin in ('curated','ai')), research_focus text not null,
 unique(user_id,identity_key), check(price_kind<>'free' or price_amount is null or price_amount=0),
 check(price_amount is null or price_kind='free' or currency ~ '^[A-Z]{3}$')""",
'opportunity_sources': """opportunity_id uuid not null, url text not null, title text not null, evidence text not null default '',
 checked_at timestamptz not null, unique(user_id,opportunity_id,url),
 foreign key(user_id,opportunity_id) references public.opportunities(user_id,id)""",
'opportunity_versions': """opportunity_id uuid not null, run_id uuid not null, content_hash text not null,
 payload jsonb not null check(jsonb_typeof(payload)='object'), changed_fields jsonb not null, checked_at timestamptz not null,
 foreign key(user_id,opportunity_id) references public.opportunities(user_id,id),
 foreign key(user_id,run_id) references public.discovery_runs(user_id,id)""",
'pack_components': """opportunity_id uuid not null, title text not null, url text not null, purpose text not null,
 sort_order integer not null check(sort_order>=0), unique(user_id,opportunity_id,sort_order),
 foreign key(user_id,opportunity_id) references public.opportunities(user_id,id)""",
'opportunity_choices': """opportunity_id uuid not null, favorite boolean not null default false,
 decision text not null default 'interested' check(decision in ('interested','dismissed','added')),
 track_id uuid, unique(user_id,opportunity_id),
 foreign key(user_id,opportunity_id) references public.opportunities(user_id,id),
 foreign key(user_id,track_id) references public.learning_tracks(user_id,id)""",
}


def build():
    sql = '-- 002: private discovery catalog, history and route adoption. Run once after 001.\nbegin;\n'
    for table, fields in FIELDS.items():
        sql += f"""
create table public.{table} (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), {fields}
);
alter table public.{table} enable row level security;
create policy owner_rows on public.{table} for all to authenticated
 using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.{table} from public,anon,authenticated;
grant select on public.{table} to authenticated;
create index {table}_owner_idx on public.{table}(user_id);
"""
    sql += """
create unique index discovery_one_running on public.discovery_runs(user_id) where status='running';
alter table public.learning_tracks drop constraint learning_tracks_kind_check;
alter table public.learning_tracks add constraint learning_tracks_kind_check
 check(kind in ('certification','course','topic','paper','project','lab','pack'));
"""
    base = (ROOT/'supabase/migrations/001_learning_atlas.sql').read_text(encoding='utf-8')
    functions = base[base.index('create function public.atlas_apply('):base.index('-- Private files:')]
    extra = ','.join("'"+t+"'" for t in CATALOG_TABLES)
    functions = functions.replace("'plan_blocks')", "'plan_blocks',"+extra+")")
    functions = functions.replace("'plan_blocks']", "'plan_blocks',"+extra+"]")
    functions = functions.replace("'track_units','phase_tracks')", "'track_units','phase_tracks','opportunity_sources','pack_components')")
    functions = functions.replace('create function public.', 'create or replace function public.')
    functions = functions.replace("if tab='profiles' and", "if tab in ('profiles','discovery_settings') and")
    return sql + functions + 'commit;\n'


if __name__ == '__main__':
    (ROOT/'supabase/migrations/002_discovery_catalog.sql').write_text(build(), encoding='utf-8')
