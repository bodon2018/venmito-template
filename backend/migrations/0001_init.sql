-- ============================================================================
-- Venmito schema
--   raw    : files exactly as uploaded, never modified
--   clean  : conformed, constrained, what the API and frontend read
--   ops    : load bookkeeping, quarantine, data-quality notes
-- ============================================================================

create schema if not exists raw;
create schema if not exists clean;
create schema if not exists ops;

-- ---------------------------------------------------------------- ops
-- One row per uploaded file. Every clean row carries the load_id that
-- produced it, so any number can be traced back to a specific upload.
create table if not exists ops.loads (
    load_id           uuid primary key,
    filename          text        not null,
    file_format       text        not null check (file_format in ('json','yaml','csv','xml')),
    entity            text        not null check (entity in ('people','promotions','transactions','transfers')),
    content_sha256    text        not null,
    status            text        not null default 'running'
                      check (status in ('running','succeeded','failed')),
    rows_read         integer     not null default 0,
    rows_loaded       integer     not null default 0,
    rows_quarantined  integer     not null default 0,
    error             text,
    started_at        timestamptz not null default now(),
    finished_at       timestamptz
);

-- Re-uploading a byte-identical file is a no-op, not a duplicate load.
create unique index if not exists loads_content_uniq
    on ops.loads (entity, content_sha256) where status = 'succeeded';

-- Rows that could not be resolved to a person, or failed validation.
-- Kept as jsonb so nothing is ever silently dropped.
create table if not exists ops.quarantine (
    id          bigserial primary key,
    load_id     uuid not null references ops.loads(load_id) on delete cascade,
    entity      text not null,
    reason      text not null,
    source_row  integer,
    payload     jsonb not null,
    created_at  timestamptz not null default now()
);

-- Facts about the data worth surfacing that are not row-level defects,
-- e.g. the ingestion outage inferred from null transfer rows.
create table if not exists ops.data_quality_notes (
    id          bigserial primary key,
    load_id     uuid references ops.loads(load_id) on delete cascade,
    note_type   text not null,
    note_date   date,
    detail      text not null,
    created_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------- raw
-- Untouched source records. Lets a policy change be replayed without
-- re-reading the original file.
create table if not exists raw.records (
    id          bigserial primary key,
    load_id     uuid not null references ops.loads(load_id) on delete cascade,
    entity      text not null,
    source_row  integer,
    payload     jsonb not null
);
create index if not exists raw_records_load on raw.records (load_id);

-- ---------------------------------------------------------------- clean
create table if not exists clean.people (
    id            integer primary key,
    first_name    text not null,
    last_name     text not null,
    email         text not null,
    phone         text not null,
    city          text not null,
    country       text not null,
    dob           date,
    source        text not null,
    is_synthetic  boolean not null default false,
    -- Points at the surviving id when two ids are the same entity.
    -- Self-referencing for ordinary rows.
    canonical_id  integer not null references clean.people(id),
    load_id       uuid references ops.loads(load_id),
    updated_at    timestamptz not null default now(),
    constraint people_email_uniq unique (email),
    constraint people_phone_uniq unique (phone)
);
create index if not exists people_canonical on clean.people (canonical_id);
create index if not exists people_country on clean.people (country);

create table if not exists clean.person_devices (
    person_id  integer not null references clean.people(id) on delete cascade,
    device     text    not null check (device in ('Android','Desktop','Iphone')),
    primary key (person_id, device)
);

-- Natural keys resolve to a person. Retired keys (a merged duplicate's old
-- email/phone) stay here so historical files still join correctly.
create table if not exists clean.person_identifiers (
    id          bigserial primary key,
    person_id   integer not null references clean.people(id) on delete cascade,
    key_type    text    not null check (key_type in ('email','phone')),
    key_value   text    not null,
    is_retired  boolean not null default false,
    constraint identifier_uniq unique (key_type, key_value)
);
create index if not exists identifiers_person on clean.person_identifiers (person_id);

-- Surrogate PK: the source `id` column is not unique (200-212 repeat).
create table if not exists clean.promotions (
    promotion_key           bigserial primary key,
    person_id               integer references clean.people(id),
    promotion               text not null,
    responded               boolean,
    promotion_date          date,
    resolved_via            text check (resolved_via in ('email','phone','unresolved')),
    email                   text,
    phone                   text,
    source_id               text,
    source_id_is_ambiguous  boolean not null default false,
    source_file             text,
    source_row              integer,
    load_id                 uuid references ops.loads(load_id),
    constraint promotion_contact_present check (
        coalesce(email,'') <> '' or coalesce(phone,'') <> ''
    )
);
create index if not exists promotions_person on clean.promotions (person_id);
create index if not exists promotions_date on clean.promotions (promotion_date);

create table if not exists clean.transactions (
    transaction_id  bigint primary key,
    person_id       integer references clean.people(id),
    phone           text not null,
    store           text not null,
    txn_date        date not null,
    is_orphan       boolean not null default false,
    is_duplicate    boolean not null default false,
    duplicate_of    bigint references clean.transactions(transaction_id),
    load_id         uuid references ops.loads(load_id)
);
create index if not exists transactions_person on clean.transactions (person_id);
create index if not exists transactions_date on clean.transactions (txn_date);

create table if not exists clean.transaction_items (
    id               bigserial primary key,
    transaction_id   bigint  not null references clean.transactions(transaction_id) on delete cascade,
    line_no          integer not null,
    item             text    not null,
    quantity         numeric(12,2) not null check (quantity > 0),
    price_per_item   numeric(12,2) not null check (price_per_item >= 0),
    -- price is recomputed; price_reported keeps the source value for audit.
    price            numeric(12,2) not null,
    price_reported   numeric(12,2) not null,
    price_mismatch   boolean not null default false,
    price_zero       boolean not null default false,
    price_negative   boolean not null default false,
    needs_review     boolean not null default false,
    constraint item_line_uniq unique (transaction_id, line_no)
);
create index if not exists items_txn on clean.transaction_items (transaction_id);
create index if not exists items_item on clean.transaction_items (item);

-- sender/recipient are nullable: the null rows are an ingestion outage and
-- are kept as evidence rather than deleted.
create table if not exists clean.transfers (
    transfer_key        bigserial primary key,
    sender_id           integer references clean.people(id),
    recipient_id        integer references clean.people(id),
    amount              numeric(14,2) not null check (amount >= 0),
    transfer_date       date not null,
    is_null_row         boolean not null default false,
    is_self_transfer    boolean not null default false,
    is_amt_outlier      boolean not null default false,
    is_round_amount     boolean not null default false,
    is_reciprocal_pair  boolean not null default false,
    is_fanout           boolean not null default false,
    is_ambiguous_998    boolean not null default false,
    flags               text not null default '',
    is_clean            boolean not null default true,
    source_row          integer,
    load_id             uuid references ops.loads(load_id)
);
create index if not exists transfers_sender on clean.transfers (sender_id);
create index if not exists transfers_recipient on clean.transfers (recipient_id);
create index if not exists transfers_date on clean.transfers (transfer_date);
create index if not exists transfers_clean on clean.transfers (is_clean);

-- ---------------------------------------------------------------- views
-- Analysts get correct defaults without needing to know the flag columns.
create or replace view clean.vw_clean_transfers as
    select * from clean.transfers where is_clean;

create or replace view clean.vw_clean_items as
    select i.*, t.person_id, t.store, t.txn_date
    from clean.transaction_items i
    join clean.transactions t using (transaction_id)
    where not i.needs_review and not t.is_duplicate and not t.is_orphan;

create or replace view clean.vw_clients as
    select p.*, (select array_agg(d.device order by d.device)
                 from clean.person_devices d where d.person_id = p.id) as devices
    from clean.people p
    where not p.is_synthetic;
