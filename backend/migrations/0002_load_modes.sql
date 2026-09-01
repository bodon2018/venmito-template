-- Upload modes.
--
-- append (default) : add this file's rows to what is already there
-- replace          : this file becomes the entity's contents; prior loads are
--                    marked superseded and their clean rows removed
--
-- Superseded loads keep their raw records and their audit row -- nothing is
-- erased from history, only excluded from the current picture.

alter table ops.loads
    add column if not exists mode text not null default 'append'
        check (mode in ('append', 'replace')),
    add column if not exists superseded boolean not null default false,
    add column if not exists superseded_by uuid references ops.loads(load_id);

create index if not exists loads_entity_active
    on ops.loads (entity) where status = 'succeeded' and not superseded;

-- The duplicate-file guard must only match loads that are still active:
-- a superseded file should be loadable again.
drop index if exists ops.loads_content_uniq;
create unique index if not exists loads_content_uniq
    on ops.loads (entity, content_sha256)
    where status = 'succeeded' and not superseded;
