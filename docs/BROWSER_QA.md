# Browser QA and UX fixes

The browser suite runs against a real FastAPI service and Postgres database on dedicated test ports (5175 / 8001), using the separate `brief_browser` database. Crawl and model completions are deterministic fixtures; browser interactions, authentication, persistence, revision checks, and version history use the actual application. This avoids live-worker races and paid model calls.

Run from the repository root:

```sh
npm --prefix frontend run test:e2e
```

Postgres from `compose.yaml` must be running on port 55432. The suite creates/migrates its isolated database, starts/stops its own servers, and removes its fixture projects. It does not replace the development server or worker. Chrome must be installed.

## Coverage

The full creation-to-review flow is exercised at widths 320, 390, 768, and 1440 CSS pixels, including a 320×568 short viewport. A separate 200% CSS-scale stress case uses long questions, suggestions, rationale, and source URLs. Scaling is a reflow stress test, not a substitute for native browser zoom or testing with actual assistive technology.

| Area | Exercised controls and states |
|---|---|
| Start | Website input, creation, optional creation-key field, invalid URL, navigation home |
| Access | Private link exchanged for cookie, reload, missing credentials, invalid recovery link, restoring the current workspace |
| Reading | Pending crawl, failed crawl, retry, draft arrival |
| Questions | Every sample option, multiline custom answer, evidence disclosure, dismissal, asking for another question, no-more-questions response |
| Direction | Preference/fact selector, save, regenerate, failed generation and retry |
| Decisions | Edit/save, cancel edit, remove/keep confirmation, removed-items disclosure, restoration |
| Sources | Source links/URLs, long crawl-note disclosure |
| Document | Preview/Markdown/History, edits, discard, save, download, unsaved-change blocking |
| Sharing | Clipboard private-link output |
| Refresh | Daily-check toggle on/off, manual check, proposed version comparison |
| Versions | Open/close comparison, keep current, restore historical version |
| Feedback | Dismiss errors and notices, server-error recovery |
| Keyboard | Arrow-key tabs, modal focus containment, Escape, restoring focus to the triggering button |
| Accessibility | Axe WCAG A/AA checks at major states; page-width overflow checks; visual screenshot review |

The existing browser tests also check that Markdown preview does not execute embedded HTML or JavaScript URLs. These tests do not verify arbitrary external sites linked from a guide, live crawler/model quality, scheduled jobs over real time, Safari/Firefox, or full screen-reader interoperability.

## Fixes

- Private-link recovery on the same pathname now reloads authentication instead of only changing the URL fragment.
- Monitoring toggles respond immediately while saving; failures still reload authoritative server state.
- Native modal dialogs contain keyboard focus, close on Escape, restore focus, and prevent background scrolling. Long comparison panes can receive focus for keyboard scrolling.
- Workspace tabs have linked panels and roving keyboard navigation.
- Mobile refinement no longer traps readers in a nested scrolling panel. Jump links connect refinement and the document.
- Custom answers support multiple lines. Mobile inputs use readable sizing, controls have larger touch targets, and metadata no longer shrinks to 9px.
- Secondary text has stronger contrast. Long content wraps; the narrow header keeps the full hostname readable on its own row.
- Creation keeps a readable busy label. Retry/removal actions are disabled while requests are pending.
- Restoring a decision also resolves a repeated question from the same source snapshot; questions based on newer evidence remain open.
- The local origin allowlist includes the actual fallback frontend port (5174), fixing private-session creation after a server restart.
- The test environment is isolated from the live development worker.

Screenshots and failure traces are written to `frontend/test-results/`. They are local test artifacts and are not committed by default.

## Latest verification

- 12 browser tests passed in Chrome, including all four viewport flows and the 200% scale stress case.
- No Axe WCAG A/AA violations, page overflow, or clipped control/heading/paragraph text in the audited states.
- 130 backend tests passed; Ruff and the production frontend build passed.
- Desktop, mobile, and version-comparison screenshots were inspected visually.

A separate live smoke test passed against `example.com`: browser creation → real crawler → configured model → rendered draft → downloaded file content. Its temporary workspace was deleted afterward. This caught the development origin mismatch before the successful rerun.

## Change comparison refresh

The comparison modal now opens proposals on a colored unified diff, with added/removed line counts and the model's rationale. Website evidence is expandable and labels newly read pages explicitly. Full current/proposed documents are a separate view. Header and actions stay visible while the content scrolls; unresolved answer reviews explain disabled acceptance. Historical versions retain the full-document comparison.

Design references: [GitHub review diffs](https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/reviewing-proposed-changes-in-a-pull-request) for focused changes, and [Notion suggested edits](https://www.notion.com/help/suggested-edits) for reviewing before accepting. Acceptance remains whole-version; this UI does not imply per-line acceptance.
