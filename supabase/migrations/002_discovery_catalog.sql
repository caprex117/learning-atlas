-- 002: private discovery catalog, history and route adoption. Run once after 001.
begin;

create table public.discovery_settings (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), focus text not null, primary_tags jsonb not null check(jsonb_typeof(primary_tags)='array'),
 related_tags jsonb not null check(jsonb_typeof(related_tags)='array'), weekly_enabled boolean not null default false,
 external_consent boolean not null default false, check(id=user_id)
);
alter table public.discovery_settings enable row level security;
create policy owner_rows on public.discovery_settings for all to authenticated
 using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.discovery_settings from public,anon,authenticated;
grant select on public.discovery_settings to authenticated;
create index discovery_settings_owner_idx on public.discovery_settings(user_id);

create table public.discovery_runs (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), status text not null check(status in ('running','completed','partial','failed')),
 origin text not null check(origin in ('manual','weekly','seed')), started_at timestamptz not null,
 finished_at timestamptz, model_id text, focus_snapshot jsonb not null default '{}',
 details jsonb not null default '{}', error_message text not null default ''
);
alter table public.discovery_runs enable row level security;
create policy owner_rows on public.discovery_runs for all to authenticated
 using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.discovery_runs from public,anon,authenticated;
grant select on public.discovery_runs to authenticated;
create index discovery_runs_owner_idx on public.discovery_runs(user_id);

create table public.opportunities (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), identity_key text not null, title text not null, kind text not null
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
 check(price_amount is null or price_kind='free' or currency ~ '^[A-Z]{3}$')
);
alter table public.opportunities enable row level security;
create policy owner_rows on public.opportunities for all to authenticated
 using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.opportunities from public,anon,authenticated;
grant select on public.opportunities to authenticated;
create index opportunities_owner_idx on public.opportunities(user_id);

create table public.opportunity_sources (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), opportunity_id uuid not null, url text not null, title text not null, evidence text not null default '',
 checked_at timestamptz not null, unique(user_id,opportunity_id,url),
 foreign key(user_id,opportunity_id) references public.opportunities(user_id,id)
);
alter table public.opportunity_sources enable row level security;
create policy owner_rows on public.opportunity_sources for all to authenticated
 using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.opportunity_sources from public,anon,authenticated;
grant select on public.opportunity_sources to authenticated;
create index opportunity_sources_owner_idx on public.opportunity_sources(user_id);

create table public.opportunity_versions (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), opportunity_id uuid not null, run_id uuid not null, content_hash text not null,
 payload jsonb not null check(jsonb_typeof(payload)='object'), changed_fields jsonb not null, checked_at timestamptz not null,
 foreign key(user_id,opportunity_id) references public.opportunities(user_id,id),
 foreign key(user_id,run_id) references public.discovery_runs(user_id,id)
);
alter table public.opportunity_versions enable row level security;
create policy owner_rows on public.opportunity_versions for all to authenticated
 using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.opportunity_versions from public,anon,authenticated;
grant select on public.opportunity_versions to authenticated;
create index opportunity_versions_owner_idx on public.opportunity_versions(user_id);

create table public.pack_components (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), opportunity_id uuid not null, title text not null, url text not null, purpose text not null,
 sort_order integer not null check(sort_order>=0), unique(user_id,opportunity_id,sort_order),
 foreign key(user_id,opportunity_id) references public.opportunities(user_id,id)
);
alter table public.pack_components enable row level security;
create policy owner_rows on public.pack_components for all to authenticated
 using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.pack_components from public,anon,authenticated;
grant select on public.pack_components to authenticated;
create index pack_components_owner_idx on public.pack_components(user_id);

create table public.opportunity_choices (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), opportunity_id uuid not null, favorite boolean not null default false,
 decision text not null default 'interested' check(decision in ('interested','dismissed','added')),
 track_id uuid, unique(user_id,opportunity_id),
 foreign key(user_id,opportunity_id) references public.opportunities(user_id,id),
 foreign key(user_id,track_id) references public.learning_tracks(user_id,id)
);
alter table public.opportunity_choices enable row level security;
create policy owner_rows on public.opportunity_choices for all to authenticated
 using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.opportunity_choices from public,anon,authenticated;
grant select on public.opportunity_choices to authenticated;
create index opportunity_choices_owner_idx on public.opportunity_choices(user_id);

create unique index discovery_one_running on public.discovery_runs(user_id) where status='running';
alter table public.learning_tracks drop constraint learning_tracks_kind_check;
alter table public.learning_tracks add constraint learning_tracks_kind_check
 check(kind in ('certification','course','topic','paper','project','lab','pack'));
create or replace function public.atlas_apply(
 p_request_id uuid, p_expected_revision bigint, p_intent jsonb, p_changes jsonb,
 p_result jsonb default '{}'::jsonb, p_import_approval jsonb default null
) returns jsonb language plpgsql security definer set search_path='' as $$
declare actor uuid:=auth.uid(); rev bigint; receipt public.mutation_receipts; change jsonb; row_data jsonb;
 tab text; col text; cols text; assignments text; affected integer; answer jsonb; jid uuid; job public.import_jobs;
begin
 if actor is null then raise exception 'AUTH_REQUIRED'; end if;
 if p_request_id is null or p_expected_revision is null or p_intent is null or jsonb_typeof(p_intent)<>'object'
    or p_changes is null or jsonb_typeof(p_changes)<>'array' or jsonb_array_length(p_changes)>2500 then raise exception 'INVALID_BATCH'; end if;
 select revision into rev from public.profiles where user_id=actor for update;
 if not found then raise exception 'BOOTSTRAP_REQUIRED'; end if;
 select * into receipt from public.mutation_receipts where user_id=actor and request_id=p_request_id;
 if found then
  if receipt.intent<>p_intent then raise exception 'REQUEST_ID_REUSED'; end if;
  return receipt.result;
 end if;
 if rev<>p_expected_revision then raise exception 'STALE_REVISION'; end if;
 if p_import_approval is not null then
  jid:=(p_import_approval->>'job_id')::uuid;
  select * into job from public.import_jobs where id=jid and user_id=actor for update;
  if not found or job.status<>'draft' or job.proposal<>p_import_approval->'proposal' then raise exception 'IMPORT_REVIEW_CHANGED'; end if;
 end if;
 for change in select value from jsonb_array_elements(p_changes) loop
  tab:=change->>'table';
  if tab is null or tab not in ('profiles','areas','learning_tracks','resources','track_resources','units','track_units','unit_progress','topics','skills','resource_topics','track_topics','topic_skills','track_skills','learning_goals','goal_phases','phase_tracks','study_sessions','session_skills','topic_events','learning_evidence','evidence_skills','skill_rubrics','skill_assessments','milestones','credentials','import_jobs','attachments','daily_plans','plan_blocks','discovery_settings','discovery_runs','opportunities','opportunity_sources','opportunity_versions','pack_components','opportunity_choices') then raise exception 'INVALID_TABLE'; end if;
  if change->>'op'='delete' then
   if tab not in ('track_topics','track_skills','topic_skills','resource_topics','session_skills','unit_progress','track_units','phase_tracks','opportunity_sources','pack_components') then raise exception 'DELETE_NOT_ALLOWED'; end if;
   execute format('delete from public.%I where id=$1 and user_id=$2',tab) using (change->>'id')::uuid,actor;
  elsif change->>'op'='upsert' then
   row_data:=change->'row';
   if jsonb_typeof(row_data)<>'object' or row_data->>'id' is null then raise exception 'INVALID_ROW'; end if;
   if row_data ? 'user_id' and row_data->>'user_id'<>actor::text then raise exception 'WRONG_OWNER'; end if;
   row_data:=row_data||jsonb_build_object('user_id',actor);
   if row_data ? 'created_at' or row_data ? 'revision' then raise exception 'RESERVED_COLUMN'; end if;
   if tab in ('profiles','discovery_settings') and row_data->>'id'<>actor::text then raise exception 'WRONG_PROFILE'; end if;
   if tab='import_jobs' and row_data->>'status'='imported' and (jid is null or row_data->>'id'<>jid::text) then raise exception 'REVIEW_REQUIRED'; end if;
   if tab in ('attachments','import_jobs') and row_data->>'storage_path' is not null then
    if split_part(row_data->>'storage_path','/',1)<>actor::text or not exists(
      select 1 from storage.objects where bucket_id='learning-documents' and name=row_data->>'storage_path'
    ) then raise exception 'PRIVATE_FILE_NOT_FOUND'; end if;
   end if;
   for col in select jsonb_object_keys(row_data) loop
    if not exists(select 1 from information_schema.columns where table_schema='public' and table_name=tab and column_name=col) then raise exception 'INVALID_COLUMN'; end if;
   end loop;
   select string_agg(format('%I',k),',' order by k),
    string_agg(format('%I=excluded.%I',k,k),',' order by k) filter(where k not in ('id','user_id'))
   into cols,assignments from jsonb_object_keys(row_data) as keys(k);
   execute format('insert into public.%1$I(%2$s) select %2$s from jsonb_populate_record(null::public.%1$I,$1) on conflict(id) do update set %3$s where %1$I.user_id=$2',
     tab,cols,coalesce(assignments,'id=excluded.id')) using row_data,actor;
   get diagnostics affected=row_count;
   if affected<>1 then raise exception 'ROW_NOT_OWNED'; end if;
  else raise exception 'INVALID_OPERATION'; end if;
 end loop;
 -- Force deferred checks before saving the receipt. Any failure rolls back the entire request.
 set constraints all immediate;
 update public.profiles set revision=revision+1 where user_id=actor returning revision into rev;
 answer:=jsonb_build_object('revision',rev,'result',p_result);
 insert into public.mutation_receipts(user_id,request_id,intent,result) values(actor,p_request_id,p_intent,answer);
 return answer;
end $$;
revoke all on function public.atlas_apply(uuid,bigint,jsonb,jsonb,jsonb,jsonb) from public,anon;
grant execute on function public.atlas_apply(uuid,bigint,jsonb,jsonb,jsonb,jsonb) to authenticated;

create or replace function public.atlas_snapshot() returns jsonb language plpgsql security invoker set search_path='' as $$
declare answer jsonb:='{}'; tab text; rows jsonb;
begin
 if auth.uid() is null then raise exception 'AUTH_REQUIRED'; end if;
 foreach tab in array array['profiles','areas','learning_tracks','resources','track_resources','units','track_units','unit_progress','topics','skills','resource_topics','track_topics','topic_skills','track_skills','learning_goals','goal_phases','phase_tracks','study_sessions','session_skills','topic_events','learning_evidence','evidence_skills','skill_rubrics','skill_assessments','milestones','credentials','import_jobs','attachments','daily_plans','plan_blocks','discovery_settings','discovery_runs','opportunities','opportunity_sources','opportunity_versions','pack_components','opportunity_choices'] loop
  execute format('select coalesce(jsonb_agg(t order by t.created_at,t.id),''[]''::jsonb) from public.%I t where user_id=auth.uid()',tab) into rows;
  answer:=answer||jsonb_build_object(tab,rows);
 end loop;
 return answer;
end $$;
revoke all on function public.atlas_snapshot() from public,anon;
grant execute on function public.atlas_snapshot() to authenticated;

commit;
