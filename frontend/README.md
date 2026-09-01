# Venmito frontend

Plain JavaScript, no build step, no framework, no charting library. Open it with
any static server and point it at the backend.

```bash
python3 -m http.server 5173
```

Then http://localhost:5173 — with the backend running on port 8000.

## Layout

```
frontend/
  index.html          app shell; sets window.VENMITO_API
  styles.css          the only global CSS (fonts, body reset, two keyframes)
  js/
    api.js            every call to the backend; nothing else knows the URLs
    tokens.js         colours, fonts, flag hues, small-sample threshold
    format.js         money / percent / date formatting, HTML escaping
    charts.js         line, column, bar, heat grid, stacked rail — pure functions
    app.js            routing, data fetching, upload flow, events
    views/
      shell.js        entry, loading, empty, error screens
      insights.js     non-technical view
      pipeline.js     technical view
      upload.js       upload panel, in-progress, result
```

## Where the data comes from

Nothing is hardcoded. Every figure is rendered from `GET /analysis`, and the
pipeline view additionally reads `/loads` and `/loads/quarantine`.

There is no cache: after an upload the app re-fetches, so the figures always
reflect current database state.

## Charts

No chart library. The datasets are 5–28 points and the design specifies its own
marks, so `charts.js` computes SVG polyline coordinates and percentage widths
directly. Adding a library would introduce a dependency and its own opinions
about axes and colour.

## Responsive behaviour

Built for laptops, roughly **1024px to 1920px**. Not designed for tablet or phone.

| Width | What changes |
|---|---|
| above 1680 | Content caps at 1680px and centres, so bars and text lines stay readable |
| 1440 and below | Column gaps tighten |
| 1280 and below | Side padding 64 → 44px; flagged counters go 4 → 3 across |
| 1150 and below | Flagged counters go 3 → 2 across |
| 1040 and below | Side padding → 32px; two-column sections stack; API console and quarantine panels stack |

Media queries live in `styles.css`. Everything else is styled inline, so any
property that has to change with width was moved out of the markup into one of
the `.vm-*` classes — a media query cannot override an inline style.

Wide tables and the item-by-store grid scroll inside themselves (`.vm-scroll`)
rather than forcing the page horizontally wide.

## Behaviour worth knowing

- **Small samples are marked, not hidden.** Campaigns under 20 offers render
  faded with `n = N ⚠`, because a 58% on 13 offers is not a 52% on 31.
- **Unmatched rows are a headline figure** in the upload result, not a footnote:
  they change how the rest of the page should be read.
- **Empty state is a real state.** With no data the app says what to upload
  rather than drawing zeroed charts.
- **Both views read the same numbers**, so they cannot disagree.
- All values from the database pass through `esc()` before reaching innerHTML.

## Pointing at another backend

`index.html` reads `window.VENMITO_API`, falling back to `http://localhost:8000`.
To change it without editing source:

```js
localStorage.setItem("venmito_api", "https://your-api.example.com")
```

The backend's CORS list in `app/main.py` must include wherever this is served.
