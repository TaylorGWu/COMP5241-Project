# Discussion reference screenshots — 2026-10-29

## Approved change

Replace the dense competitor/EvoClass/homepage-reference paragraphs in Course 7,
Chapter 13 with large, attributed reference screenshots and adjacent actual-product
comparisons. The user explicitly removed the three-page limit. The chapter now
contains 12 slides, including eight screenshot pages, while retaining its problem,
proposed-scope and teacher-agency positioning. References are discussion backup,
not a requirement to narrate twelve pages in two minutes.

## Actual captures

| Reference | Public source | Comparison in Coursework |
|---|---|---|
| Teachnow AI | https://www.teachnow.ai/docs/teach/create-a-course | Editable chapter workspace, review composer and applied-change records |
| EvoClass | https://evoclass.ai/courses?lang=en | Private teacher library with search, filters and draft states |
| Linear | https://linear.app/ | Product-led homepage composition |
| Notion | https://www.notion.com/product | Concrete workspace demonstration |
| Stripe | https://stripe.com/en-jp | Value statement and visible next actions |

All images were captured from actual browser pages on 29 October 2026. Crops
focus on relevant interface areas and avoid our account identity. The final
EvoClass capture uses the full viewport because the screenshot tool's initial
cropped output contained unwanted whitespace. No reference UI was reconstructed
with AI. The homepage reference set is documented in the 22 October public-entry
design records; current captures are not represented as exact historical copies.

GPTutor's homepage and public instructor guide both timed out in the browser.
Its existing desk-research comparison remains in speaker notes, explicitly
without a screenshot or private-tool usability claim. Coursera's next-step
recommendation insight also remains in notes. None of these captures is an
external interview or an independent product evaluation.

## Storage and rendering

Captures use the existing private raster-asset store and authorized chapter asset
route. Metadata records `provider=browser-capture`, `generated=false`, capture
date and source URL; new slides are teacher-authored. Assets remain ignored local
files, not remote image hotlinks or frontend credentials. Earlier assets, notes
and slides remain in version history; publication state and other chapters were
not changed.

`Visual.spec.display=full` enables a reusable image-led page for raster visuals.
The same IR renders a large contained image plus a short source/caption in the
web preview and fixed-layout PPTX export. Ordinary half-width illustrations are
unchanged. Screenshot alt text identifies screenshots rather than AI art.
Renderers/exporters do not make model calls. The new full-width export test
failed against the old narrow layout, then passed after implementation.

## Parallel-read defect found during visual verification

Loading eight thumbnails exposed a pre-existing guard defect: all scoped
requests competed for the chapter editing lock, so simultaneous image requests
received 409 and showed unavailable placeholders. Only the scoped PNG/SVG GET
handlers now read committed snapshots without that editing lock. Authentication,
course/chapter ownership and asset-reference checks still apply. No arbitrary
GET or mutation bypass was added. The regression tests concurrent private image
reads, denies another teacher and confirms manual edits still return 409 while
the editing lock is held. An initial synthetic test fixture needed its obsolete
animation target cleared after replacing its visuals; explicit IR validation
now prevents that fixture error from masquerading as a lock failure.

Local verification artifacts: `/private/tmp/coursework-background-screenshots.pptx`,
`/private/tmp/coursework-background-screenshots.pdf`, screenshot files and the
capture manifest. These are internal evidence, not a deployment or external
usability result. Font substitution in file viewers remains possible; the
contract is source/content consistency, not identical web/PPTX pixels.
