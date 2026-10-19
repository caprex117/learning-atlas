-- Optional credential identifiers and personal document links. Run once after 002.
-- Existing data, ownership rules and RPC allowlists are preserved.
begin;
alter table public.credentials
 add column program_code text not null default '' check(length(program_code)<=100),
 add column credential_code text not null default '' check(length(credential_code)<=200),
 add column document_url text check(document_url is null or document_url ~ '^https?://');
commit;
