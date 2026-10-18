-- Learning Atlas 1.0. Run once in a NEW Supabase project. No data from Anime-App is accessed.
begin;

create table public.profiles (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), display_name text not null default 'Mi espacio', timezone text not null default 'America/La_Paz',
 weekly_minutes integer not null default 480 check(weekly_minutes between 10 and 10080),
 streak_minutes integer not null default 10 check(streak_minutes between 1 and 1440),
 revision bigint not null default 0, check(id=user_id)
);
alter table public.profiles enable row level security;
create policy owner_rows on public.profiles for all to authenticated using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.profiles from anon, authenticated;
grant select on public.profiles to authenticated;
create index profiles_owner_idx on public.profiles(user_id);

create table public.areas (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), name text not null check(length(trim(name)) between 1 and 180)
);
alter table public.areas enable row level security;
create policy owner_rows on public.areas for all to authenticated using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.areas from anon, authenticated;
grant select on public.areas to authenticated;
create index areas_owner_idx on public.areas(user_id);

create table public.learning_tracks (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), area_id uuid not null, title text not null check(length(trim(title)) between 1 and 180),
 kind text not null check(kind in ('certification','course','topic','paper','project','lab')),
 official_name text not null default '', platform text not null default '', issuer text not null default '', code text not null default '',
 source_url text, target_on date, estimated_minutes integer check(estimated_minutes>0),
 status text not null default 'planned' check(status in ('planned','active','paused','completed','archived')),
 favorite boolean not null default false, priority integer not null default 3 check(priority between 1 and 5),
 notes text not null default '', source_type text not null default 'manual', source_key text,
 completion_basis text not null default 'units' check(completion_basis in ('units','self_reported_credential')),
 foreign key(user_id,area_id) references public.areas(user_id,id)
);
alter table public.learning_tracks enable row level security;
create policy owner_rows on public.learning_tracks for all to authenticated using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.learning_tracks from anon, authenticated;
grant select on public.learning_tracks to authenticated;
create index learning_tracks_owner_idx on public.learning_tracks(user_id);

create table public.resources (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), title text not null, url text, kind text not null default 'document', notes text not null default ''
);
alter table public.resources enable row level security;
create policy owner_rows on public.resources for all to authenticated using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.resources from anon, authenticated;
grant select on public.resources to authenticated;
create index resources_owner_idx on public.resources(user_id);

create table public.track_resources (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), track_id uuid not null, resource_id uuid not null,
 unique(user_id,track_id,resource_id),
 foreign key(user_id,track_id) references public.learning_tracks(user_id,id),
 foreign key(user_id,resource_id) references public.resources(user_id,id)
);
alter table public.track_resources enable row level security;
create policy owner_rows on public.track_resources for all to authenticated using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.track_resources from anon, authenticated;
grant select on public.track_resources to authenticated;
create index track_resources_owner_idx on public.track_resources(user_id);

create table public.units (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), resource_id uuid not null, parent_id uuid, title text not null check(length(trim(title))>0),
 estimated_minutes integer check(estimated_minutes>0), sort_order integer not null default 0, archived boolean not null default false,
 unique(user_id,id,resource_id),
 foreign key(user_id,resource_id) references public.resources(user_id,id),
 foreign key(user_id,parent_id,resource_id) references public.units(user_id,id,resource_id) deferrable initially deferred
);
alter table public.units enable row level security;
create policy owner_rows on public.units for all to authenticated using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.units from anon, authenticated;
grant select on public.units to authenticated;
create index units_owner_idx on public.units(user_id);

create table public.track_units (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), track_id uuid not null, unit_id uuid not null, resource_id uuid not null,
 required boolean not null default true, weight numeric not null default 1 check(weight>0 and weight<=100),
 unique(user_id,track_id,unit_id),
 foreign key(user_id,track_id,resource_id) references public.track_resources(user_id,track_id,resource_id),
 foreign key(user_id,unit_id,resource_id) references public.units(user_id,id,resource_id)
);
alter table public.track_units enable row level security;
create policy owner_rows on public.track_units for all to authenticated using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.track_units from anon, authenticated;
grant select on public.track_units to authenticated;
create index track_units_owner_idx on public.track_units(user_id);

create table public.unit_progress (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), unit_id uuid not null, completed_on date not null, unique(user_id,unit_id),
 foreign key(user_id,unit_id) references public.units(user_id,id)
);
alter table public.unit_progress enable row level security;
create policy owner_rows on public.unit_progress for all to authenticated using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.unit_progress from anon, authenticated;
grant select on public.unit_progress to authenticated;
create index unit_progress_owner_idx on public.unit_progress(user_id);

create table public.topics (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), area_id uuid not null, name text not null check(length(trim(name))>0), description text not null default '',
 review_enabled boolean not null default true, foreign key(user_id,area_id) references public.areas(user_id,id)
);
alter table public.topics enable row level security;
create policy owner_rows on public.topics for all to authenticated using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.topics from anon, authenticated;
grant select on public.topics to authenticated;
create index topics_owner_idx on public.topics(user_id);

create table public.skills (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), name text not null check(length(trim(name))>0), definition text not null default '', area_id uuid not null,
 foreign key(user_id,area_id) references public.areas(user_id,id)
);
alter table public.skills enable row level security;
create policy owner_rows on public.skills for all to authenticated using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.skills from anon, authenticated;
grant select on public.skills to authenticated;
create index skills_owner_idx on public.skills(user_id);

create table public.resource_topics (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), resource_id uuid not null, topic_id uuid not null, origin text not null default 'manual',
 unique(user_id,resource_id,topic_id), foreign key(user_id,resource_id) references public.resources(user_id,id),
 foreign key(user_id,topic_id) references public.topics(user_id,id)
);
alter table public.resource_topics enable row level security;
create policy owner_rows on public.resource_topics for all to authenticated using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.resource_topics from anon, authenticated;
grant select on public.resource_topics to authenticated;
create index resource_topics_owner_idx on public.resource_topics(user_id);

create table public.track_topics (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), track_id uuid not null, topic_id uuid not null, origin text not null default 'manual',
 unique(user_id,track_id,topic_id), foreign key(user_id,track_id) references public.learning_tracks(user_id,id),
 foreign key(user_id,topic_id) references public.topics(user_id,id)
);
alter table public.track_topics enable row level security;
create policy owner_rows on public.track_topics for all to authenticated using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.track_topics from anon, authenticated;
grant select on public.track_topics to authenticated;
create index track_topics_owner_idx on public.track_topics(user_id);

create table public.topic_skills (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), topic_id uuid not null, skill_id uuid not null,
 unique(user_id,topic_id,skill_id), foreign key(user_id,topic_id) references public.topics(user_id,id),
 foreign key(user_id,skill_id) references public.skills(user_id,id)
);
alter table public.topic_skills enable row level security;
create policy owner_rows on public.topic_skills for all to authenticated using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.topic_skills from anon, authenticated;
grant select on public.topic_skills to authenticated;
create index topic_skills_owner_idx on public.topic_skills(user_id);

create table public.track_skills (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), track_id uuid not null, skill_id uuid not null,
 unique(user_id,track_id,skill_id), foreign key(user_id,track_id) references public.learning_tracks(user_id,id),
 foreign key(user_id,skill_id) references public.skills(user_id,id)
);
alter table public.track_skills enable row level security;
create policy owner_rows on public.track_skills for all to authenticated using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.track_skills from anon, authenticated;
grant select on public.track_skills to authenticated;
create index track_skills_owner_idx on public.track_skills(user_id);

create table public.learning_goals (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), title text not null, outcome text not null default '', weekly_minutes integer not null check(weekly_minutes between 10 and 10080),
 starts_on date not null, target_on date not null, version integer not null default 1, supersedes_id uuid,
 status text not null default 'active' check(status in ('active','archived')), check(target_on>=starts_on),
 foreign key(user_id,supersedes_id) references public.learning_goals(user_id,id)
);
alter table public.learning_goals enable row level security;
create policy owner_rows on public.learning_goals for all to authenticated using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.learning_goals from anon, authenticated;
grant select on public.learning_goals to authenticated;
create index learning_goals_owner_idx on public.learning_goals(user_id);

create table public.goal_phases (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), goal_id uuid not null, title text not null, starts_on date not null, ends_on date not null,
 budget_minutes integer not null check(budget_minutes>0), sort_order integer not null, topics text not null default '',
 is_buffer boolean not null default false, unique(user_id,goal_id,sort_order), check(ends_on>=starts_on),
 foreign key(user_id,goal_id) references public.learning_goals(user_id,id)
);
alter table public.goal_phases enable row level security;
create policy owner_rows on public.goal_phases for all to authenticated using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.goal_phases from anon, authenticated;
grant select on public.goal_phases to authenticated;
create index goal_phases_owner_idx on public.goal_phases(user_id);

create table public.phase_tracks (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), phase_id uuid not null, track_id uuid not null, role text not null default 'core',
 unique(user_id,phase_id,track_id), foreign key(user_id,phase_id) references public.goal_phases(user_id,id),
 foreign key(user_id,track_id) references public.learning_tracks(user_id,id)
);
alter table public.phase_tracks enable row level security;
create policy owner_rows on public.phase_tracks for all to authenticated using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.phase_tracks from anon, authenticated;
grant select on public.phase_tracks to authenticated;
create index phase_tracks_owner_idx on public.phase_tracks(user_id);

create table public.study_sessions (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), area_id uuid not null, track_id uuid, phase_id uuid, occurred_on date not null,
 timezone_at_entry text not null, duration_minutes integer not null check(duration_minutes between 1 and 1440),
 activity_type text not null check(activity_type in ('study','review','work_practice')), notes text not null default '',
 voided boolean not null default false, void_reason text not null default '',
 foreign key(user_id,area_id) references public.areas(user_id,id),
 foreign key(user_id,track_id) references public.learning_tracks(user_id,id),
 foreign key(user_id,phase_id) references public.goal_phases(user_id,id)
);
alter table public.study_sessions enable row level security;
create policy owner_rows on public.study_sessions for all to authenticated using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.study_sessions from anon, authenticated;
grant select on public.study_sessions to authenticated;
create index study_sessions_owner_idx on public.study_sessions(user_id);

create table public.session_skills (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), session_id uuid not null, skill_id uuid not null, allocated_minutes integer not null check(allocated_minutes>0),
 unique(user_id,session_id,skill_id), foreign key(user_id,session_id) references public.study_sessions(user_id,id),
 foreign key(user_id,skill_id) references public.skills(user_id,id)
);
alter table public.session_skills enable row level security;
create policy owner_rows on public.session_skills for all to authenticated using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.session_skills from anon, authenticated;
grant select on public.session_skills to authenticated;
create index session_skills_owner_idx on public.session_skills(user_id);

create table public.topic_events (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), topic_id uuid not null, session_id uuid, occurred_on date not null,
 event_type text not null check(event_type in ('learned','study','review','work_practice')),
 rating text check(rating in ('again','hard','good','easy')), notes text not null default '', voided boolean not null default false,
 unique(user_id,session_id,topic_id), foreign key(user_id,topic_id) references public.topics(user_id,id),
 foreign key(user_id,session_id) references public.study_sessions(user_id,id),
 check(rating is null or event_type in ('review','work_practice'))
);
alter table public.topic_events enable row level security;
create policy owner_rows on public.topic_events for all to authenticated using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.topic_events from anon, authenticated;
grant select on public.topic_events to authenticated;
create index topic_events_owner_idx on public.topic_events(user_id);

create table public.learning_evidence (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), session_id uuid, track_id uuid, title text not null, description text not null default '', url text,
 occurred_on date, period_label text not null default '', source_type text not null default 'self_report',
 validation_status text not null default 'unreviewed' check(validation_status in ('unreviewed','self_checked')),
 foreign key(user_id,session_id) references public.study_sessions(user_id,id),
 foreign key(user_id,track_id) references public.learning_tracks(user_id,id)
);
alter table public.learning_evidence enable row level security;
create policy owner_rows on public.learning_evidence for all to authenticated using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.learning_evidence from anon, authenticated;
grant select on public.learning_evidence to authenticated;
create index learning_evidence_owner_idx on public.learning_evidence(user_id);

create table public.evidence_skills (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), evidence_id uuid not null, skill_id uuid not null, unique(user_id,evidence_id,skill_id),
 foreign key(user_id,evidence_id) references public.learning_evidence(user_id,id),
 foreign key(user_id,skill_id) references public.skills(user_id,id)
);
alter table public.evidence_skills enable row level security;
create policy owner_rows on public.evidence_skills for all to authenticated using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.evidence_skills from anon, authenticated;
grant select on public.evidence_skills to authenticated;
create index evidence_skills_owner_idx on public.evidence_skills(user_id);

create table public.skill_rubrics (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), code text not null, version integer not null default 1, description text not null,
 unique(user_id,code,version)
);
alter table public.skill_rubrics enable row level security;
create policy owner_rows on public.skill_rubrics for all to authenticated using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.skill_rubrics from anon, authenticated;
grant select on public.skill_rubrics to authenticated;
create index skill_rubrics_owner_idx on public.skill_rubrics(user_id);

create table public.skill_assessments (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), skill_id uuid not null, rubric_id uuid not null, occurred_on date not null,
 level integer not null check(level between 0 and 3), method text not null default 'self' check(method='self'),
 context text not null check(length(trim(context))>0), evidence_url text, voided boolean not null default false,
 unique(user_id,skill_id,rubric_id,occurred_on), foreign key(user_id,skill_id) references public.skills(user_id,id),
 foreign key(user_id,rubric_id) references public.skill_rubrics(user_id,id)
);
alter table public.skill_assessments enable row level security;
create policy owner_rows on public.skill_assessments for all to authenticated using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.skill_assessments from anon, authenticated;
grant select on public.skill_assessments to authenticated;
create index skill_assessments_owner_idx on public.skill_assessments(user_id);

create table public.milestones (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), phase_id uuid not null, title text not null, criteria text not null, accepted_on date,
 evidence_id uuid, notes text not null default '', foreign key(user_id,phase_id) references public.goal_phases(user_id,id),
 foreign key(user_id,evidence_id) references public.learning_evidence(user_id,id)
);
alter table public.milestones enable row level security;
create policy owner_rows on public.milestones for all to authenticated using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.milestones from anon, authenticated;
grant select on public.milestones to authenticated;
create index milestones_owner_idx on public.milestones(user_id);

create table public.credentials (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), track_id uuid, official_name text not null, issuer text not null, credential_type text not null
 check(credential_type in ('professional','course','program','badge')), earned_on date, period_label text not null default '',
 expires_on date, never_expires boolean not null default false, verification_url text, notes text not null default '',
 verification_status text not null default 'self_reported' check(verification_status='self_reported'),
 check(not(never_expires and expires_on is not null)), check(expires_on is null or earned_on is null or expires_on>=earned_on),
 foreign key(user_id,track_id) references public.learning_tracks(user_id,id)
);
alter table public.credentials enable row level security;
create policy owner_rows on public.credentials for all to authenticated using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.credentials from anon, authenticated;
grant select on public.credentials to authenticated;
create index credentials_owner_idx on public.credentials(user_id);

create table public.import_jobs (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), filename text not null, sha256 text not null, storage_path text, mime_type text not null,
 proposal jsonb not null, proposal_hash text not null, status text not null default 'draft' check(status in ('draft','imported','cancelled')),
 result jsonb, extractor_version text not null default 'extract-v1', model_id text, prompt_version text
);
alter table public.import_jobs enable row level security;
create policy owner_rows on public.import_jobs for all to authenticated using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.import_jobs from anon, authenticated;
grant select on public.import_jobs to authenticated;
create index import_jobs_owner_idx on public.import_jobs(user_id);

create table public.attachments (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), resource_id uuid, credential_id uuid, evidence_id uuid, import_job_id uuid,
 storage_path text not null, original_name text not null, mime_type text not null, size_bytes bigint not null check(size_bytes>0),
 sha256 text not null, check(num_nonnulls(resource_id,credential_id,evidence_id)=1),
 foreign key(user_id,resource_id) references public.resources(user_id,id),
 foreign key(user_id,credential_id) references public.credentials(user_id,id),
 foreign key(user_id,evidence_id) references public.learning_evidence(user_id,id),
 foreign key(user_id,import_job_id) references public.import_jobs(user_id,id)
);
alter table public.attachments enable row level security;
create policy owner_rows on public.attachments for all to authenticated using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.attachments from anon, authenticated;
grant select on public.attachments to authenticated;
create index attachments_owner_idx on public.attachments(user_id);

create table public.daily_plans (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), plan_date date not null, budget_minutes integer not null check(budget_minutes>0), energy text not null, generator text not null default 'rules'
);
alter table public.daily_plans enable row level security;
create policy owner_rows on public.daily_plans for all to authenticated using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.daily_plans from anon, authenticated;
grant select on public.daily_plans to authenticated;
create index daily_plans_owner_idx on public.daily_plans(user_id);

create table public.plan_blocks (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), unique(user_id,id), plan_id uuid not null, track_id uuid, topic_id uuid, title text not null, reason text not null,
 planned_minutes integer not null check(planned_minutes between 10 and 40), sort_order integer not null, completed_session_id uuid,
 unique(user_id,plan_id,sort_order), unique(user_id,completed_session_id),
 foreign key(user_id,plan_id) references public.daily_plans(user_id,id),
 foreign key(user_id,track_id) references public.learning_tracks(user_id,id),
 foreign key(user_id,topic_id) references public.topics(user_id,id),
 foreign key(user_id,completed_session_id) references public.study_sessions(user_id,id)
);
alter table public.plan_blocks enable row level security;
create policy owner_rows on public.plan_blocks for all to authenticated using(user_id=auth.uid()) with check(user_id=auth.uid());
revoke all on public.plan_blocks from anon, authenticated;
grant select on public.plan_blocks to authenticated;
create index plan_blocks_owner_idx on public.plan_blocks(user_id);


create unique index areas_name_uq on public.areas(user_id,lower(trim(name)));
create unique index skills_name_uq on public.skills(user_id,lower(trim(name)));
create unique index topics_name_uq on public.topics(user_id,area_id,lower(trim(name)));
create unique index track_source_uq on public.learning_tracks(user_id,source_key) where source_key is not null;
create index sessions_day_idx on public.study_sessions(user_id,occurred_on) where not voided;
create index events_topic_date_idx on public.topic_events(user_id,topic_id,occurred_on) where not voided;
create table public.mutation_receipts (
 user_id uuid not null references auth.users(id) on delete cascade, request_id uuid not null,
 intent jsonb not null, result jsonb not null, created_at timestamptz not null default now(), primary key(user_id,request_id)
);
alter table public.mutation_receipts enable row level security;
create policy owner_receipts on public.mutation_receipts for select to authenticated using(user_id=auth.uid());
revoke all on public.mutation_receipts from anon,authenticated;
grant select on public.mutation_receipts to authenticated;

create function public.atlas_bootstrap() returns void language plpgsql security definer set search_path='' as $$
begin
 if auth.uid() is null then raise exception 'AUTH_REQUIRED'; end if;
 insert into public.profiles(id,user_id) values(auth.uid(),auth.uid()) on conflict(id) do nothing;
end $$;
revoke all on function public.atlas_bootstrap() from public,anon;
grant execute on function public.atlas_bootstrap() to authenticated;

create function public.atlas_integrity() returns trigger language plpgsql set search_path='' as $$
declare actor uuid:=coalesce(new.user_id,old.user_id); sid uuid; dur integer; tz text;
begin
 if tg_table_name in ('session_skills','study_sessions') then
  if tg_table_name='study_sessions' then sid:=coalesce(new.id,old.id); else sid:=coalesce(new.session_id,old.session_id); end if;
  select duration_minutes into dur from public.study_sessions where id=sid and user_id=actor for update;
  if coalesce((select sum(allocated_minutes) from public.session_skills where session_id=sid and user_id=actor),0)>dur then
   raise exception 'ALLOCATION_EXCEEDS_SESSION';
  end if;
 end if;
 if tg_table_name in ('units','track_units') then
  if exists(select 1 from public.track_units tu join public.units child on child.parent_id=tu.unit_id and child.user_id=tu.user_id
     where tu.user_id=actor and not child.archived) then raise exception 'ONLY_LEAF_UNITS_COUNT'; end if;
  if exists(with recursive walk as (
    select id,parent_id,array[id] as path,false as cycle from public.units where user_id=actor
    union all select w.id,u.parent_id,w.path||u.id,u.id=any(w.path) from walk w
    join public.units u on u.id=w.parent_id and u.user_id=actor where not w.cycle
   ) select 1 from walk where cycle) then raise exception 'UNIT_CYCLE'; end if;
 end if;
 if tg_table_name in ('goal_phases','learning_goals') then
  if exists(select 1 from public.goal_phases p join public.learning_goals g on g.id=p.goal_id and g.user_id=p.user_id
    where p.user_id=actor and (p.starts_on<g.starts_on or p.ends_on>g.target_on)) then raise exception 'PHASE_OUTSIDE_GOAL'; end if;
  if exists(select 1 from public.goal_phases a join public.goal_phases b on a.user_id=b.user_id and a.goal_id=b.goal_id and a.id<b.id
    where a.user_id=actor and daterange(a.starts_on,a.ends_on,'[]') && daterange(b.starts_on,b.ends_on,'[]')) then raise exception 'PHASE_OVERLAP'; end if;
 end if;
 if tg_table_name='topic_events' and to_jsonb(new)->>'session_id' is not null then
  if not exists(select 1 from public.study_sessions s where s.id=new.session_id and s.user_id=new.user_id and s.occurred_on=new.occurred_on) then
   raise exception 'EVENT_SESSION_DATE_MISMATCH'; end if;
 end if;
 return coalesce(new,old);
end $$;

create constraint trigger session_skills_integrity after insert or update or delete on public.session_skills deferrable initially deferred for each row execute function public.atlas_integrity();

create constraint trigger study_sessions_integrity after insert or update or delete on public.study_sessions deferrable initially deferred for each row execute function public.atlas_integrity();

create constraint trigger units_integrity after insert or update or delete on public.units deferrable initially deferred for each row execute function public.atlas_integrity();

create constraint trigger track_units_integrity after insert or update or delete on public.track_units deferrable initially deferred for each row execute function public.atlas_integrity();

create constraint trigger goal_phases_integrity after insert or update or delete on public.goal_phases deferrable initially deferred for each row execute function public.atlas_integrity();

create constraint trigger learning_goals_integrity after insert or update or delete on public.learning_goals deferrable initially deferred for each row execute function public.atlas_integrity();

create constraint trigger topic_events_integrity after insert or update or delete on public.topic_events deferrable initially deferred for each row execute function public.atlas_integrity();


create function public.atlas_dates() returns trigger language plpgsql set search_path='' as $$
declare tz text; d date;
begin
 select timezone into tz from public.profiles where user_id=new.user_id;
 if tg_table_name='profiles' then
  if not exists(select 1 from pg_timezone_names where name=new.timezone) then raise exception 'INVALID_TIMEZONE'; end if;
  return new;
 end if;
 d:=(to_jsonb(new)->>(case tg_table_name when 'unit_progress' then 'completed_on' else 'occurred_on' end))::date;
 if d>(now() at time zone coalesce(tz,'America/La_Paz'))::date then raise exception 'FUTURE_ACTIVITY'; end if;
 return new;
end $$;

create trigger profiles_dates before insert or update on public.profiles for each row execute function public.atlas_dates();

create trigger unit_progress_dates before insert or update on public.unit_progress for each row execute function public.atlas_dates();

create trigger study_sessions_dates before insert or update on public.study_sessions for each row execute function public.atlas_dates();

create trigger topic_events_dates before insert or update on public.topic_events for each row execute function public.atlas_dates();

create trigger skill_assessments_dates before insert or update on public.skill_assessments for each row execute function public.atlas_dates();


-- All writes use this transaction; auth.uid(), never client input, controls ownership.
create function public.atlas_apply(
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
  if tab is null or tab not in ('profiles','areas','learning_tracks','resources','track_resources','units','track_units','unit_progress','topics','skills','resource_topics','track_topics','topic_skills','track_skills','learning_goals','goal_phases','phase_tracks','study_sessions','session_skills','topic_events','learning_evidence','evidence_skills','skill_rubrics','skill_assessments','milestones','credentials','import_jobs','attachments','daily_plans','plan_blocks') then raise exception 'INVALID_TABLE'; end if;
  if change->>'op'='delete' then
   if tab not in ('track_topics','track_skills','topic_skills','resource_topics','session_skills','unit_progress','track_units','phase_tracks') then raise exception 'DELETE_NOT_ALLOWED'; end if;
   execute format('delete from public.%I where id=$1 and user_id=$2',tab) using (change->>'id')::uuid,actor;
  elsif change->>'op'='upsert' then
   row_data:=change->'row';
   if jsonb_typeof(row_data)<>'object' or row_data->>'id' is null then raise exception 'INVALID_ROW'; end if;
   if row_data ? 'user_id' and row_data->>'user_id'<>actor::text then raise exception 'WRONG_OWNER'; end if;
   row_data:=row_data||jsonb_build_object('user_id',actor);
   if row_data ? 'created_at' or row_data ? 'revision' then raise exception 'RESERVED_COLUMN'; end if;
   if tab='profiles' and row_data->>'id'<>actor::text then raise exception 'WRONG_PROFILE'; end if;
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

create function public.atlas_snapshot() returns jsonb language plpgsql security invoker set search_path='' as $$
declare answer jsonb:='{}'; tab text; rows jsonb;
begin
 if auth.uid() is null then raise exception 'AUTH_REQUIRED'; end if;
 foreach tab in array array['profiles','areas','learning_tracks','resources','track_resources','units','track_units','unit_progress','topics','skills','resource_topics','track_topics','topic_skills','track_skills','learning_goals','goal_phases','phase_tracks','study_sessions','session_skills','topic_events','learning_evidence','evidence_skills','skill_rubrics','skill_assessments','milestones','credentials','import_jobs','attachments','daily_plans','plan_blocks'] loop
  execute format('select coalesce(jsonb_agg(t order by t.created_at,t.id),''[]''::jsonb) from public.%I t where user_id=auth.uid()',tab) into rows;
  answer:=answer||jsonb_build_object(tab,rows);
 end loop;
 return answer;
end $$;
revoke all on function public.atlas_snapshot() from public,anon;
grant execute on function public.atlas_snapshot() to authenticated;

-- Private files: paths start with the authenticated user's UUID. No shared public bucket.
insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
 values('learning-documents','learning-documents',false,10485760,array['application/pdf','application/vnd.openxmlformats-officedocument.wordprocessingml.document','text/plain','text/markdown','application/json'])
 on conflict(id) do nothing;
create policy atlas_files_read on storage.objects for select to authenticated
 using(bucket_id='learning-documents' and (storage.foldername(name))[1]=auth.uid()::text);
create policy atlas_files_insert on storage.objects for insert to authenticated
 with check(bucket_id='learning-documents' and (storage.foldername(name))[1]=auth.uid()::text);
create policy atlas_files_delete on storage.objects for delete to authenticated
 using(bucket_id='learning-documents' and (storage.foldername(name))[1]=auth.uid()::text
 and not exists(select 1 from public.attachments a where a.storage_path=storage.objects.name)
 and not exists(select 1 from public.import_jobs j where j.storage_path=storage.objects.name and j.status<>'cancelled'));
commit;
