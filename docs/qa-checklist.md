# Atticus Browser QA Checklist

Run against the single-image build (`docker build -f Dockerfile.production -t atticus . &&
docker run -p 8000:8000 --env-file .env atticus`) or the dev servers, then check each item.
File an issue for anything broken.

## New Analysis
- [ ] Analyze by application number (`19531961`) — progress states appear
- [ ] Paste OA text — analysis completes
- [ ] Invalid application number — friendly error, no crash

## Analysis Overview
- [ ] All rejection cards render; verification badges show; expand/collapse works
- [ ] Claim table: **[View ↗]** opens the Source Viewer with the cited passage
- [ ] Source Viewer: **Esc**, outside-click, and **×** all close it

## Response Draft
- [ ] Generate with strategy = **Argue**; inline `[Source: ...]` citations are visible
- [ ] Edit text, **Save Draft**, reload the page — edits persisted
- [ ] **Export to Word** — the `.docx` opens in Word/Pages with correct formatting

## Export / Sidebar / Delete
- [ ] **Export Analysis** `.docx` opens correctly
- [ ] Sidebar: the recent-analyses list updates after a new analysis
- [ ] Delete an analysis — it disappears from the list; the direct URL then 404s

## Settings & Compliance guard
- [ ] Settings: provider, models, and configured status render
- [ ] Guard: with `LLM_TIER=free` on Gemini, analyzing **client** data returns the
      `PROVIDER_NOT_PERMITTED_FOR_CLIENT_DATA` message with a link to Settings
      (to test: temporarily submit an unpublished/unknown application so it is classified CLIENT)

## Notes
- Published applications are classified PUBLIC and run on any provider tier; the guard only
  blocks CLIENT/PRIVILEGED data on training-enabled tiers (see `docs/data-handling-policy.md`).
