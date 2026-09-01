/* Non-technical view. Renders entirely from GET /analysis -- no figure in
   here is hardcoded. Where a dataset is too small to support a chart, the
   copy says so rather than drawing an empty one. */
import { C, F, SMALL_SAMPLE } from "../tokens.js";
import { money, num, pct, monthLabel, dateLabel, MONTHS, esc } from "../format.js";
import { lineChart, columnChart, barRow, heatGrid, stackedRail } from "../charts.js";

const NAV = ["Findings", "Customers", "Stores", "Promotions",
             "Who to call", "Transfers", "Coverage"];

const section = (id, eyebrow, title, sub, body) => `
  <section id="${id}" class="vm-section" style="border-bottom:1px solid ${C.hair}">
    <div style="margin-bottom:26px">
      <div style="font:500 10px/1 ${F.mono};letter-spacing:.2em;text-transform:uppercase;
                  color:${C.business}">${esc(eyebrow)}</div>
      <h2 style="margin:12px 0 0;font:300 34px/1.15 ${F.serif};letter-spacing:-.01em">${esc(title)}</h2>
      ${sub ? `<p style="margin:8px 0 0;font:400 13.5px/1.5 ${F.sans};color:${C.muted};
                          max-width:64ch">${esc(sub)}</p>` : ""}
    </div>
    ${body}
  </section>`;

const stat = (label, value, note = "") => `
  <div style="flex:1;min-width:0">
    <div style="font:400 11px/1 ${F.mono};letter-spacing:.06em;text-transform:uppercase;
                color:${C.faint};margin-bottom:10px">${esc(label)}</div>
    <div style="font:300 30px/1 ${F.serif};letter-spacing:-.01em">${value}</div>
    ${note ? `<div style="margin-top:7px;font:400 11.5px/1.4 ${F.sans};
                          color:${C.faint}">${esc(note)}</div>` : ""}
  </div>`;

const statRule = (cells) => `
  <div class="vm-stats" style="padding:22px 0;border-top:1px solid ${C.hairHard};
              border-bottom:1px solid ${C.hair};margin-bottom:30px">${cells.join("")}</div>`;

const tooLittle = (msg) => `
  <p style="margin:0;padding:18px 20px;background:${C.canvas};border-radius:2px;
            font:400 12.5px/1.5 ${F.sans};color:${C.muted}">${esc(msg)}</p>`;

/* ------------------------------------------------------------- findings */
function findings(r) {
  const cards = r.headlines.map((h) => `
    <div style="padding:20px 22px;background:${C.canvas};border-radius:2px">
      <div style="font:500 10px/1 ${F.mono};letter-spacing:.16em;text-transform:uppercase;
                  color:${C.business};margin-bottom:10px">${esc(h.title)}</div>
      <p style="margin:0;font:400 13.5px/1.55 ${F.sans};color:${C.ink}">${esc(h.text)}</p>
    </div>`).join("");
  return section("findings", "Findings",
    `${r.headlines.length} things the data says right now`,
    "Rewritten after every upload — these sentences are generated from the current numbers, not written by hand.",
    `<div class="vm-cards">${cards}</div>`);
}

/* ------------------------------------------------------------ customers */
function customers(c) {
  const maxCity = Math.max(...c.by_city.map((x) => x.clients), 0);
  const cities = c.by_city.map((x) =>
    barRow({ label: x.city, value: x.clients, display: num(x.clients),
             max: maxCity, note: x.country })).join("");
  const countries = c.by_country.map((x) =>
    barRow({ label: x.country, value: x.clients, display: num(x.clients),
             max: c.by_country[0].clients, note: pct(x.pct / 100, 0) })).join("");
  const devices = c.devices.map((x) =>
    barRow({ label: x.device, value: x.clients, display: num(x.clients),
             max: c.devices[0].clients, note: pct(x.pct / 100, 0) })).join("");

  const hist = c.age_histogram;
  return section("customers", "Customers", "Who the customer base is", null, `
    ${statRule([
      stat("Clients", num(c.summary.clients)),
      stat("Countries", num(c.summary.countries)),
      stat("Median age", num(c.summary.median_age, 0)),
    ])}
    <div class="vm-two">
      <div>
        <h3 style="margin:0 0 10px;font:500 12px/1 ${F.mono};letter-spacing:.1em;
                   text-transform:uppercase;color:${C.muted2}">Clients by country</h3>
        ${countries}
        <h3 style="margin:30px 0 10px;font:500 12px/1 ${F.mono};letter-spacing:.1em;
                   text-transform:uppercase;color:${C.muted2}">Devices in use</h3>
        <p style="margin:0 0 8px;font:400 11.5px/1.4 ${F.sans};color:${C.faint}">
          A client may own several, so these overlap and do not total 100%.</p>
        ${devices}
      </div>
      <div>
        <h3 style="margin:0 0 10px;font:500 12px/1 ${F.mono};letter-spacing:.1em;
                   text-transform:uppercase;color:${C.muted2}">Largest cities</h3>
        ${cities}
      </div>
    </div>
    <h3 style="margin:34px 0 10px;font:500 12px/1 ${F.mono};letter-spacing:.1em;
               text-transform:uppercase;color:${C.muted2}">Age distribution</h3>
    ${hist.length ? columnChart(hist.map((b) => b.clients), { height: 84 }) +
      `<div style="display:flex;justify-content:space-between;margin-top:8px;
                   font:400 10.5px/1 ${F.mono};color:${C.faint}">
         <span>${hist[0].age_from}</span><span>${hist[hist.length - 1].age_to} years</span></div>`
      : tooLittle("No dates of birth available.")}`);
}

/* --------------------------------------------------------------- stores */
function stores(s) {
  const maxRev = Math.max(...s.by_item.map((i) => i.revenue), 0);
  const items = s.by_item.map((i) =>
    barRow({ label: i.item, value: i.revenue, display: money(i.revenue),
             max: maxRev, note: `${num(i.units)} units` })).join("");
  const maxStore = Math.max(...s.by_store.map((i) => i.revenue), 0);
  const storeRows = s.by_store.map((i) =>
    barRow({ label: i.store, value: i.revenue, display: money(i.revenue),
             max: maxStore, note: `${money(i.avg_order_value, 2)} avg` })).join("");

  const months = s.monthly;
  const grid = heatGrid({
    rows: s.by_item.map((i) => i.item),
    cols: [...new Set(s.item_by_store.map((r) => r.store))],
    valueAt: (item, store) => {
      const hit = s.item_by_store.find((r) => r.item === item && r.store === store);
      return hit ? hit.revenue : 0;
    },
    format: (v) => Math.round(v),
  });

  const sc = s.spend_concentration;
  return section("stores", "Stores", "What sells, and where", s.measure_note, `
    ${statRule([
      stat("Best seller — revenue", esc(s.best_seller_by_revenue.item),
           money(s.best_seller_by_revenue.revenue)),
      stat("Best seller — units", esc(s.best_seller_by_units.item),
           `${num(s.best_seller_by_units.units)} units`),
      stat("Top store", esc(s.top_store_by_revenue.store),
           money(s.top_store_by_revenue.revenue)),
      stat("Best average order", esc(s.top_store_by_basket_value.store),
           money(s.top_store_by_basket_value.avg_order_value, 2)),
    ])}
    <p style="margin:-14px 0 26px;font:400 12.5px/1.5 ${F.sans};color:${C.muted};max-width:70ch">
      The two best sellers are different items — ${esc(s.best_seller_by_revenue.item)} leads on
      revenue, ${esc(s.best_seller_by_units.item)} on units. Which one is “best” depends on the
      measure, so both are shown.</p>
    <div class="vm-two">
      <div><h3 style="margin:0 0 10px;font:500 12px/1 ${F.mono};letter-spacing:.1em;
                      text-transform:uppercase;color:${C.muted2}">Items by revenue</h3>${items}</div>
      <div><h3 style="margin:0 0 10px;font:500 12px/1 ${F.mono};letter-spacing:.1em;
                      text-transform:uppercase;color:${C.muted2}">Stores by revenue</h3>${storeRows}</div>
    </div>
    <h3 style="margin:34px 0 12px;font:500 12px/1 ${F.mono};letter-spacing:.1em;
               text-transform:uppercase;color:${C.muted2}">Item by store</h3>
    ${grid}
    <h3 style="margin:34px 0 12px;font:500 12px/1 ${F.mono};letter-spacing:.1em;
               text-transform:uppercase;color:${C.muted2}">Revenue by month</h3>
    ${months.length > 1 ? lineChart(months.map((m) => m.revenue), { height: 120 }) +
      `<div style="display:flex;justify-content:space-between;margin-top:8px;
                   font:400 10.5px/1 ${F.mono};color:${C.faint}">
        <span>${monthLabel(months[0].month)}</span>
        <span>${monthLabel(months[months.length - 1].month)}</span></div>`
      : tooLittle("Not enough months to draw a trend.")}
    <div style="margin-top:34px;padding:20px 22px;background:${C.canvas};border-radius:2px">
      <h3 style="margin:0 0 8px;font:500 12px/1 ${F.mono};letter-spacing:.1em;
                 text-transform:uppercase;color:${C.muted2}">How spend is spread</h3>
      <p style="margin:0;font:400 13.5px/1.6 ${F.sans}">
        ${num(sc.buyers)} clients have bought something. ${num(sc.one_time_buyers)} of them
        bought exactly once and ${num(sc.repeat_buyers)} bought three times or more —
        too few repeat buyers to read a trend from. Median spend is
        ${money(sc.median_spend, 2)} against a mean of ${money(sc.mean_spend, 2)},
        so a small number of larger baskets pulls the average up.</p>
    </div>`);
}

/* ----------------------------------------------------------- promotions */
function promotions(p) {
  const maxSent = Math.max(...p.by_promotion.map((x) => x.sent), 0);
  const rows = p.by_promotion.map((x) => {
    const small = x.sent < SMALL_SAMPLE;
    return barRow({
      label: x.promotion, value: x.response_rate, display: pct(x.response_rate),
      max: 1, muted: small,
      note: `n = ${x.sent}${small ? " ⚠" : ""}`,
    });
  }).join("");

  const channels = p.by_channel.map((x) =>
    barRow({ label: x.channel, value: x.response_rate, display: pct(x.response_rate),
             max: 1, note: `n = ${x.sent}` })).join("");

  const byMonth = MONTHS.map((_, i) =>
    p.by_month.find((m) => m.month === i + 1) || { sent: 0, response_rate: 0 });

  const roster = p.client_roster.slice(0, 12).map((c) => `
    <tr style="border-top:1px solid ${C.hairSoft}">
      <td style="padding:9px 12px 9px 0;font:400 12.5px ${F.sans}">${esc(c.first_name)} ${esc(c.last_name)}</td>
      <td style="padding:9px 12px;font:400 12px ${F.sans};color:${C.muted}">${esc(c.country)}</td>
      <td style="padding:9px 12px;font:500 12px ${F.mono};text-align:right">${c.promotions}</td>
      <td style="padding:9px 12px;font:500 12px ${F.mono};text-align:right">${c.accepted}</td>
      <td style="padding:9px 0;font:400 12px ${F.sans};color:${C.muted}">${esc(c.promotion_list)}</td>
    </tr>`).join("");

  return section("promotions", "Promotions", "Which offers land",
    `Every rate carries the number of offers behind it. A high rate on a handful of offers is not the same as a high rate on thirty.`, `
    ${statRule([
      stat("Overall response", pct(p.overall.response_rate),
           `${num(p.overall.accepted)} of ${num(p.overall.sent)} offers`),
      stat("Clients targeted", num(p.overall.clients_targeted)),
      stat("Campaigns", num(p.by_promotion.length)),
    ])}
    <div style="display:grid;grid-template-columns:1.3fr 1fr;gap:52px">
      <div><h3 style="margin:0 0 10px;font:500 12px/1 ${F.mono};letter-spacing:.1em;
                      text-transform:uppercase;color:${C.muted2}">By campaign</h3>
        ${rows}
        <p style="margin:10px 0 0;font:400 11.5px/1.5 ${F.sans};color:${C.faint}">
          Campaigns under ${SMALL_SAMPLE} offers are drawn faded and marked ⚠ — the rate is real
          but the sample is too small to rank confidently.</p>
      </div>
      <div><h3 style="margin:0 0 10px;font:500 12px/1 ${F.mono};letter-spacing:.1em;
                      text-transform:uppercase;color:${C.muted2}">By channel</h3>
        ${channels}
        <h3 style="margin:30px 0 10px;font:500 12px/1 ${F.mono};letter-spacing:.1em;
                   text-transform:uppercase;color:${C.muted2}">By calendar month</h3>
        ${columnChart(byMonth.map((m) => m.response_rate), { height: 70 })}
        <div style="display:flex;justify-content:space-between;margin-top:6px;
                    font:400 10px/1 ${F.mono};color:${C.faint}">
          ${MONTHS.map((m) => `<span>${m[0]}</span>`).join("")}</div>
      </div>
    </div>
    <h3 style="margin:34px 0 4px;font:500 12px/1 ${F.mono};letter-spacing:.1em;
               text-transform:uppercase;color:${C.muted2}">Clients and their offers</h3>
    <p style="margin:0 0 10px;font:400 11.5px/1.4 ${F.sans};color:${C.faint}">
      Showing ${Math.min(12, p.client_roster.length)} of ${p.client_roster.length}.</p>
    <div class="vm-scroll"><table style="width:100%;border-collapse:collapse">
      <tr><th style="text-align:left;padding:0 12px 8px 0;font:500 10.5px ${F.mono};
                     letter-spacing:.1em;text-transform:uppercase;color:${C.faint};font-weight:500">Client</th>
          <th style="text-align:left;padding:0 12px 8px;font:500 10.5px ${F.mono};
                     letter-spacing:.1em;text-transform:uppercase;color:${C.faint};font-weight:500">Country</th>
          <th style="text-align:right;padding:0 12px 8px;font:500 10.5px ${F.mono};
                     letter-spacing:.1em;text-transform:uppercase;color:${C.faint};font-weight:500">Offers</th>
          <th style="text-align:right;padding:0 12px 8px;font:500 10.5px ${F.mono};
                     letter-spacing:.1em;text-transform:uppercase;color:${C.faint};font-weight:500">Accepted</th>
          <th style="text-align:left;padding:0 0 8px;font:500 10.5px ${F.mono};
                     letter-spacing:.1em;text-transform:uppercase;color:${C.faint};font-weight:500">Campaigns</th></tr>
      ${roster}
    </table></div>`);
}

/* ---------------------------------------------------------- who to call */
function whoToCall(t) {
  const bought = t.affinity.find((a) => a.segment === "has bought item") || { sent: 0, response_rate: 0 };
  const not = t.affinity.find((a) => a.segment === "never bought item") || { sent: 0, response_rate: 0 };
  const ratio = not.response_rate ? (bought.response_rate / not.response_rate) : null;

  const rows = t.retarget_list.map((c) => `
    <tr style="border-top:1px solid ${C.hairSoft}">
      <td style="padding:10px 12px 10px 0;font:400 12.5px ${F.sans}">${esc(c.first_name)} ${esc(c.last_name)}</td>
      <td style="padding:10px 12px;font:400 12px ${F.sans};color:${C.muted}">${esc(c.country)}</td>
      <td style="padding:10px 12px;font:400 12.5px ${F.sans}">${esc(c.promotion)}</td>
      <td style="padding:10px 12px;font:500 12px ${F.mono};text-align:right">${money(c.spend_on_item, 2)}</td>
      <td style="padding:10px 12px;font:400 11.5px ${F.mono};color:${C.faint}">${dateLabel(c.promotion_date)}</td>
      <td style="padding:10px 0;font:400 11.5px ${F.sans};color:${C.faint}">via ${esc(c.resolved_via)}</td>
    </tr>`).join("");

  const n = t.retarget_list.length;
  return section("who-to-call", "Recommended action",
    n ? `${n} people worth calling back` : "Nobody to call back right now",
    null, `
    <div class="vm-two" style="margin-bottom:28px">
      <div>
        <p style="margin:0 0 16px;font:400 13.5px/1.6 ${F.sans};max-width:56ch">
          These clients turned down an offer for something they already buy. The product is
          not the objection, so the offer or the way we reached them is worth another try.</p>
        <div style="display:flex;gap:34px">
          ${stat("Already buys it", pct(bought.response_rate), `accepted, of ${bought.sent} offers`)}
          ${stat("Does not buy it", pct(not.response_rate), `accepted, of ${not.sent} offers`)}
        </div>
        ${ratio ? `<p style="margin:16px 0 0;font:400 12.5px/1.5 ${F.sans};color:${C.muted}">
          Buyers accept about ${ratio.toFixed(2)}× as often. On ${bought.sent} offers that is
          suggestive rather than proven — worth acting on, not worth forecasting from.</p>` : ""}
      </div>
      <div style="padding:22px 24px;background:${C.canvas};border-radius:2px;align-self:start">
        <div style="font:400 11px/1 ${F.mono};letter-spacing:.06em;text-transform:uppercase;
                    color:${C.faint};margin-bottom:10px">Spend already going to these items</div>
        <div style="font:300 34px/1 ${F.serif}">${money(t.addressable_spend, 2)}</div>
        <p style="margin:12px 0 0;font:400 12.5px/1.5 ${F.sans};color:${C.muted}">
          Across ${n} declined ${n === 1 ? "offer" : "offers"} — an afternoon of phone calls,
          not a campaign.</p>
      </div>
    </div>
    ${n ? `<div class="vm-scroll"><table style="width:100%;border-collapse:collapse">
      <tr>${["Client","Country","Declined offer","Spend on item","Offer date","Reached"]
        .map((h, i) => `<th style="text-align:${i === 3 ? "right" : "left"};
          padding:0 12px 8px ${i === 0 ? "0" : ""};font:500 10.5px ${F.mono};letter-spacing:.1em;
          text-transform:uppercase;color:${C.faint};font-weight:500">${h}</th>`).join("")}</tr>
      ${rows}</table></div>
      <p style="margin:12px 0 0;font:400 11.5px/1.4 ${F.sans};color:${C.faint}">
        All ${n} shown — this is the whole list, not a page of it.</p>`
      : tooLittle("No client has yet declined an offer for an item they already buy.")}`);
}

/* ------------------------------------------------------------ transfers */
function transfers(t, outageMonths) {
  const s = t.summary;
  const m = t.monthly;
  const bands = m.map((x, i) => (x.null_rows > 0 ? i : -1)).filter((i) => i >= 0);

  const flow = (rows, colour) => rows.slice(0, 8).map((r) => barRow({
    label: `${r.first_name} ${r.last_name}`,
    value: Math.abs(r.net_flow),
    display: money(r.net_flow, 2),
    max: Math.max(...rows.map((x) => Math.abs(x.net_flow)), 0),
    colour, note: `${r.degree} transfers`, wide: true,
  })).join("");

  return section("transfers", "Transfers", "Money moving between clients", null, `
    ${statRule([
      stat("Transfers", num(s.clean_transfers)),
      stat("Value moved", money(s.value_moved)),
      stat("Median", money(s.median_amount, 2)),
      stat("Largest", money(s.max_amount, 2)),
      stat("Participation", pct(t.participation.participation_rate),
           `${num(t.participation.participants)} of ${num(t.participation.clients)} clients`),
    ])}
    <div style="padding:22px 24px;background:${C.canvas};border-radius:2px;margin-bottom:30px">
      <div style="font:400 11px/1 ${F.mono};letter-spacing:.06em;text-transform:uppercase;
                  color:${C.faint};margin-bottom:10px">Cross-sell audience</div>
      <div style="font:300 34px/1 ${F.serif}">${num(t.cross_sell_audience.audience_size)}</div>
      <p style="margin:12px 0 0;font:400 13px/1.55 ${F.sans};color:${C.muted};max-width:66ch">
        Clients who send or receive money but have never bought anything in a store. They are
        active and reachable, and none of the store campaigns have touched them.</p>
    </div>
    <div class="vm-two">
      <div><h3 style="margin:0 0 10px;font:500 12px/1 ${F.mono};letter-spacing:.1em;
                      text-transform:uppercase;color:${C.muted2}">Net receivers</h3>
        ${flow(t.top_net_receivers, C.ok)}</div>
      <div><h3 style="margin:0 0 10px;font:500 12px/1 ${F.mono};letter-spacing:.1em;
                      text-transform:uppercase;color:${C.muted2}">Net senders</h3>
        ${flow(t.top_net_senders, C.business)}</div>
    </div>
    <h3 style="margin:34px 0 12px;font:500 12px/1 ${F.mono};letter-spacing:.1em;
               text-transform:uppercase;color:${C.muted2}">Transfers by month</h3>
    ${m.length > 1 ? lineChart(m.map((x) => x.transfers), { height: 110, bands }) +
      `<div style="display:flex;justify-content:space-between;margin-top:8px;
                   font:400 10.5px/1 ${F.mono};color:${C.faint}">
        <span>${monthLabel(m[0].month)}</span>
        <span>${monthLabel(m[m.length - 1].month)}</span></div>` +
      (bands.length ? `<p style="margin:10px 0 0;font:400 11.5px/1.5 ${F.sans};color:${C.faint}">
        Shaded months are days where the source file arrived with empty rows —
        ${outageMonths} in total. Counts for those months are understated.</p>` : "")
      : tooLittle("Not enough months to draw a trend.")}`);
}

/* ------------------------------------------------------------- coverage */
function coverage(cv) {
  const total = cv.by_channel_count.reduce((s, x) => s + x.clients, 0);
  const colours = [C.faint2, C.business, C.warn, C.ok];
  return section("coverage", "Coverage", "How much we know about each client",
    "Each client can appear in three places: offers, store purchases, and transfers.", `
    ${stackedRail(cv.by_channel_count.map((x, i) => ({
      label: `${x.channels} of 3`, value: x.clients, colour: colours[x.channels] ?? C.faint2,
    })))}
    <div style="display:flex;gap:26px;margin-top:14px;flex-wrap:wrap">
      ${cv.by_channel_count.map((x) => `
        <span style="display:flex;align-items:center;gap:8px;font:400 12px ${F.sans}">
          <span style="width:10px;height:10px;border-radius:1px;
                       background:${colours[x.channels] ?? C.faint2}"></span>
          ${x.channels} of 3 — ${num(x.clients)} clients (${pct(x.pct / 100, 0)})</span>`).join("")}
    </div>
    <p style="margin:22px 0 0;font:400 13.5px/1.6 ${F.sans};max-width:70ch">
      ${num(cv.invisible_clients)} of ${num(total)} clients show no activity at all — no offer,
      no purchase, no transfer. They exist in the client list and nothing else, which is worth
      knowing before anyone reports on “active customers”.</p>`);
}

/* ---------------------------------------------------------------- shell */
export function renderInsights(r) {
  const outageMonths = r.data_quality.outages.length;
  return `
    <div class="vm-page" style="background:${C.surface};min-height:100vh">
      <div class="vm-pad" style="position:sticky;top:0;z-index:20;background:${C.surface};
                  border-bottom:1px solid ${C.hair};display:flex;
                  align-items:center;justify-content:space-between;height:64px">
        <div style="display:flex;align-items:baseline;gap:26px">
          <span style="font:500 12px/1 ${F.mono};letter-spacing:.18em;text-transform:uppercase">Venmito</span>
          <span style="font:400 12.5px/1 ${F.sans};color:${C.faint}">Insights</span>
        </div>
        <div style="display:flex;align-items:center;gap:20px">
          <span style="font:400 11.5px/1 ${F.mono};color:${C.faint}">
            ${num(r.clients.summary.clients)} clients · ${num(r.stores.monthly.length)} months</span>
          <button data-action="open-upload"
            style="padding:9px 15px;border:1px solid ${C.hairHard};border-radius:2px;
                   background:none;font:500 12px ${F.sans};cursor:pointer">Upload data</button>
          <button data-action="go-pipeline"
            style="padding:9px 15px;border:1px solid transparent;background:none;
                   font:400 12px ${F.sans};color:${C.technical};cursor:pointer">
            Switch to pipeline view →</button>
        </div>
      </div>
      <nav class="vm-pad" style="position:sticky;top:64px;z-index:19;border-bottom:1px solid ${C.hair};
                  background:${C.surface};display:flex;gap:26px;height:44px;
                  align-items:center;font:400 12px ${F.sans};color:${C.faint}">
        ${NAV.map((n, i) => `<a href="#${["findings","customers","stores","promotions",
          "who-to-call","transfers","coverage"][i]}"
          style="color:inherit;text-decoration:none;height:44px;display:flex;
                 align-items:center">${n}</a>`).join("")}
      </nav>
      ${findings(r)}
      ${customers(r.clients)}
      ${stores(r.stores)}
      ${promotions(r.promotions)}
      ${whoToCall(r.turn_no_into_yes)}
      ${transfers(r.transfers, outageMonths)}
      ${coverage(r.channel_coverage)}
      <footer class="vm-pad" style="padding-top:30px;padding-bottom:60px;
              font:400 11.5px/1.6 ${F.sans};color:${C.faint}">
        Every figure on this page is computed from the data currently in the database.
        A section with too little data says so rather than drawing an empty chart.
      </footer>
    </div>`;
}
