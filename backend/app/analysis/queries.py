"""SQL for the analysis module.

Aggregation runs in Postgres rather than in Python: the data already lives
there, and pushing the work down keeps the API response small.

Conventions applied consistently:
  * synthetic entities are excluded from client-facing metrics
  * `canonical_id` is used, so a merged duplicate counts once
  * flagged rows are excluded from revenue/behaviour and reported separately
"""

# ------------------------------------------------------------------ clients
CLIENT_BASE = """
select count(*)                                          as clients,
       count(distinct country)                           as countries,
       round(avg(extract(year from age(dob)))::numeric, 1) as median_age_proxy,
       percentile_cont(0.5) within group (order by extract(year from age(dob)))
                                                         as median_age
  from clean.people
 where not is_synthetic and id = canonical_id
"""

CLIENTS_BY_COUNTRY = """
select country, count(*) as clients,
       round(100.0 * count(*) / sum(count(*)) over (), 1) as pct
  from clean.people
 where not is_synthetic and id = canonical_id
 group by country order by clients desc
"""

CLIENTS_BY_CITY = """
select city, country, count(*) as clients
  from clean.people
 where not is_synthetic and id = canonical_id
 group by city, country order by clients desc
"""

DEVICE_ADOPTION = """
select d.device, count(*) as clients,
       round(100.0 * count(*) / (select count(*) from clean.people
                                  where not is_synthetic and id = canonical_id), 1) as pct
  from clean.person_devices d
  join clean.people p on p.id = d.person_id
 where not p.is_synthetic and p.id = p.canonical_id
 group by d.device order by clients desc
"""

AGE_HISTOGRAM = """
select width_bucket(extract(year from age(dob))::int, 20, 80, 12) as bucket,
       min(extract(year from age(dob))::int) as age_from,
       max(extract(year from age(dob))::int) as age_to,
       count(*) as clients
  from clean.people
 where not is_synthetic and id = canonical_id and dob is not null
 group by bucket order by bucket
"""

# --------------------------------------------------------------- promotions
PROMOTION_PERFORMANCE = """
select pr.promotion,
       count(*)                                   as sent,
       count(*) filter (where pr.responded)       as accepted,
       round(avg(case when pr.responded then 1.0 else 0.0 end), 4) as response_rate
  from clean.promotions pr
  join clean.people p on p.id = pr.person_id
 where not p.is_synthetic
 group by pr.promotion order by response_rate desc
"""

PROMOTION_OVERALL = """
select count(*) as sent,
       count(*) filter (where pr.responded) as accepted,
       round(avg(case when pr.responded then 1.0 else 0.0 end), 4) as response_rate,
       count(distinct pr.person_id) as clients_targeted
  from clean.promotions pr
  join clean.people p on p.id = pr.person_id
 where not p.is_synthetic
"""

# Who holds what -- the roster, one row per client.
CLIENT_PROMOTION_ROSTER = """
select p.id as person_id, p.first_name, p.last_name, p.country,
       count(*)                             as promotions,
       count(*) filter (where pr.responded) as accepted,
       string_agg(distinct pr.promotion, ', ' order by pr.promotion) as promotion_list
  from clean.promotions pr
  join clean.people p on p.id = pr.person_id
 where not p.is_synthetic
 group by p.id, p.first_name, p.last_name, p.country
 order by promotions desc, accepted desc
 limit :limit
"""

# Response split by whether the client already buys the promoted item.
PROMOTION_AFFINITY = """
with buyers as (
    select distinct person_id, item from clean.vw_clean_items where person_id is not null
)
select case when b.person_id is null then 'never bought item' else 'has bought item' end as segment,
       count(*)                                   as sent,
       count(*) filter (where pr.responded)       as accepted,
       round(avg(case when pr.responded then 1.0 else 0.0 end), 4) as response_rate
  from clean.promotions pr
  join clean.people p on p.id = pr.person_id
  left join buyers b on b.person_id = pr.person_id and b.item = pr.promotion
 where not p.is_synthetic
 group by segment order by response_rate desc
"""

# The actionable output: declined an offer for something they demonstrably buy.
RETARGET_LIST = """
with buyers as (
    select person_id, item, sum(price) as spend_on_item
      from clean.vw_clean_items where person_id is not null
     group by person_id, item
)
select p.id as person_id, p.first_name, p.last_name, p.country,
       pr.promotion, b.spend_on_item, pr.resolved_via, pr.promotion_date
  from clean.promotions pr
  join clean.people p on p.id = pr.person_id
  join buyers b on b.person_id = pr.person_id and b.item = pr.promotion
 where not p.is_synthetic and pr.responded is false
 order by b.spend_on_item desc
"""

PROMOTION_BY_MONTH = """
select extract(month from pr.promotion_date)::int as month,
       count(*)                                   as sent,
       count(*) filter (where pr.responded)       as accepted,
       round(avg(case when pr.responded then 1.0 else 0.0 end), 4) as response_rate
  from clean.promotions pr
  join clean.people p on p.id = pr.person_id
 where not p.is_synthetic and pr.promotion_date is not null
 group by month order by month
"""

PROMOTION_BY_CHANNEL = """
select pr.resolved_via as channel,
       count(*)                                   as sent,
       count(*) filter (where pr.responded)       as accepted,
       round(avg(case when pr.responded then 1.0 else 0.0 end), 4) as response_rate
  from clean.promotions pr
  join clean.people p on p.id = pr.person_id
 where not p.is_synthetic
 group by channel order by response_rate desc
"""

# --------------------------------------------------------- stores and items
ITEM_PERFORMANCE = """
select item,
       sum(quantity)                  as units,
       sum(price)                     as revenue,
       count(distinct transaction_id) as orders,
       round(sum(price) / nullif(sum(quantity), 0), 2) as avg_unit_price
  from clean.vw_clean_items
 group by item order by revenue desc
"""

STORE_PERFORMANCE = """
select store,
       sum(price)                     as revenue,
       count(distinct transaction_id) as orders,
       sum(quantity)                  as units,
       count(distinct person_id)      as customers,
       round(sum(price) / nullif(count(distinct transaction_id), 0), 2) as avg_order_value,
       round(sum(quantity) / nullif(count(distinct transaction_id), 0), 2) as avg_basket_size
  from clean.vw_clean_items
 group by store order by revenue desc
"""

ITEM_BY_STORE = """
select item, store, sum(price) as revenue
  from clean.vw_clean_items
 group by item, store order by item, store
"""

MONTHLY_SALES = """
select date_trunc('month', txn_date)::date       as month,
       count(distinct transaction_id)            as transactions,
       sum(price)                                as revenue
  from clean.vw_clean_items
 group by month order by month
"""

SPEND_CONCENTRATION = """
with per_client as (
    select person_id, sum(price) as spend, count(distinct transaction_id) as orders
      from clean.vw_clean_items where person_id is not null group by person_id
)
select count(*)                                        as buyers,
       round(avg(spend), 2)                            as mean_spend,
       percentile_cont(0.5) within group (order by spend) as median_spend,
       max(spend)                                      as max_spend,
       count(*) filter (where orders = 1)              as one_time_buyers,
       count(*) filter (where orders >= 3)             as repeat_buyers
  from per_client
"""

# ----------------------------------------------------------------- transfers
TRANSFER_SUMMARY = """
select count(*)                              as clean_transfers,
       sum(amount)                           as value_moved,
       round(avg(amount), 2)                 as mean_amount,
       percentile_cont(0.5) within group (order by amount) as median_amount,
       max(amount)                           as max_amount
  from clean.vw_clean_transfers
"""

TRANSFER_NET_FLOW = """
with flow as (
    select sender_id as person_id, -amount as delta, 1 as sent, 0 as received
      from clean.vw_clean_transfers where sender_id is not null
    union all
    select recipient_id, amount, 0, 1
      from clean.vw_clean_transfers where recipient_id is not null
)
select p.id as person_id, p.first_name, p.last_name, p.country,
       sum(delta)            as net_flow,
       sum(sent)             as transfers_sent,
       sum(received)         as transfers_received,
       sum(sent + received)  as degree
  from flow join clean.people p on p.id = flow.person_id
 where not p.is_synthetic
 group by p.id, p.first_name, p.last_name, p.country
"""

TRANSFER_PARTICIPATION = """
with participants as (
    select sender_id as person_id from clean.vw_clean_transfers where sender_id is not null
    union
    select recipient_id from clean.vw_clean_transfers where recipient_id is not null
)
select (select count(*) from participants)                    as participants,
       (select count(*) from clean.people
         where not is_synthetic and id = canonical_id)         as clients
"""

# Transfer-active clients who never buy in a store: a cross-sell audience.
CROSS_SELL_AUDIENCE = """
with participants as (
    select sender_id as person_id from clean.vw_clean_transfers where sender_id is not null
    union
    select recipient_id from clean.vw_clean_transfers where recipient_id is not null
),
buyers as (select distinct person_id from clean.vw_clean_items where person_id is not null)
select count(*) as audience_size
  from participants pa
  join clean.people p on p.id = pa.person_id
 where not p.is_synthetic and pa.person_id not in (select person_id from buyers)
"""

TRANSFER_MONTHLY = """
select date_trunc('month', transfer_date)::date as month,
       count(*) filter (where not is_null_row)  as transfers,
       sum(amount) filter (where is_clean)      as value_moved,
       count(*) filter (where is_null_row)      as null_rows
  from clean.transfers
 group by month order by month
"""

RISK_TAGS = """
select 'self_transfer' as tag, count(*) as transfers from clean.transfers where is_self_transfer
 union all select 'amount_outlier', count(*) from clean.transfers where is_amt_outlier
 union all select 'round_amount', count(*) from clean.transfers where is_round_amount
 union all select 'reciprocal_pair', count(*) from clean.transfers where is_reciprocal_pair
 union all select 'fan_out', count(*) from clean.transfers where is_fanout
 union all select 'null_row', count(*) from clean.transfers where is_null_row
 order by transfers desc
"""

FLAGGED_TRANSFERS = """
select transfer_key, sender_id, recipient_id, amount, transfer_date, flags
  from clean.transfers
 where not is_clean and not is_null_row
 order by amount desc limit :limit
"""

# ------------------------------------------------------------- cross-channel
CHANNEL_COVERAGE = """
with promo as (select distinct person_id from clean.promotions where person_id is not null),
     buy   as (select distinct person_id from clean.vw_clean_items where person_id is not null),
     move  as (
        select sender_id as person_id from clean.vw_clean_transfers where sender_id is not null
        union select recipient_id from clean.vw_clean_transfers where recipient_id is not null)
select (case when pr.person_id is not null then 1 else 0 end
      + case when b.person_id  is not null then 1 else 0 end
      + case when m.person_id  is not null then 1 else 0 end) as channels,
       count(*) as clients
  from clean.people p
  left join promo pr on pr.person_id = p.id
  left join buy   b  on b.person_id  = p.id
  left join move  m  on m.person_id  = p.id
 where not p.is_synthetic and p.id = p.canonical_id
 group by channels order by channels
"""

DATA_QUALITY = """
select (select count(*) from clean.transactions where is_orphan)          as orphan_transactions,
       (select count(*) from clean.transactions where is_duplicate)       as duplicate_transactions,
       (select count(*) from clean.transaction_items where needs_review)  as items_needing_review,
       (select count(*) from clean.transfers where is_null_row)           as null_transfers,
       (select count(*) from clean.transfers where not is_clean)          as flagged_transfers,
       (select count(*) from clean.people where is_synthetic)             as synthetic_people,
       (select count(*) from ops.quarantine)                              as quarantined_rows
"""

OUTAGE_DATES = """
select note_date, detail from ops.data_quality_notes
 where note_type = 'ingestion_outage' order by note_date
"""
