# Browser tests
### Author: Lukas (Viridis) Dubsik
#### Date: 6.11.2026

## Running the tests
From the root of the repository, after `make install`, run:

```sh
make test
```

This builds the client and runs Cypress in headless Electron. The runner (`web/scripts/test.mjs`) starts the Python application on a free port with its own temporary SQLite database, so the normal database is never used. At the end the server is stopped and its database and log are deleted.

To watch the tests in the Cypress window, build the client first and then open it:

```sh
make build
npm --prefix web run test:e2e:open
```

The server keeps running while the window is open. Every scenario creates or imports its own study and Cypress clears the browser storage between them, so they can run in any order and one failing doesn't break the others.

Cypress is pinned to 15.21.1, as that version still runs on Node 20. The first `npm ci` also downloads its browser. On Linux it needs some [system libraries and Xvfb](https://docs.cypress.io/app/get-started/install-cypress#Linux-Prerequisites).

## Scenarios

| File | Scenario and expected result |
|-|-|
| `workspace.cy.ts` | An invalid interval can't be applied, the corrected one is. |
| `workspace.cy.ts` | Closing and reopening a saved study brings back the invalid unapplied edit, separately from the applied interval. |
| `workspace.cy.ts` | Undo brings back the applied interval and the edit from before Apply, discarding the edit shows the old value. Save clears Undo. |
| `workspace.cy.ts` | A broken request file is refused and the open study stays as it was. |
| `review.cy.ts` | Evidence for another request is blocked, the same file twice is recognized as a duplicate and 0 is shown differently from a missing score. |
| `review.cy.ts` | Decisions in different collections stay separate, removing one can be undone and the older evidence keeps its revision. |
| `review.cy.ts` | The downloaded draft review has the reason and the original evidence bytes, the checksums of both match. |
| `recovery.cy.ts` | A failed save keeps the work and a later save goes through. |
| `recovery.cy.ts` | A late save response doesn't overwrite newer typing. |
| `recovery.cy.ts` | When a response is lost, Refresh finds the applied change without creating a second target. |
| `recovery.cy.ts` | Export last saved uses the saved interval while a newer one is applied but not saved. |

The tests click through the real GUI against the real HTTP routes and SQLite, the application has no special routes for them. Some steps also read the study straight from the API, to check what was really applied and not only what is shown. The imports use the example files, each time with new IDs.

## How the failures are simulated
- **Failed save:** one HTTP 503 response is returned before the request reaches the storage, then the save is retried for real. This tests the recovery in the client, not an actual disk failure.
- **Late save:** a real response is held back for one second.
- **Lost response:** the real request finishes on the server, but the browser rejects it before the controller reads it. Refresh then has to find exactly one target.

There are no automatic retries and no fixed waits, the tests always wait for a request or for the expected state. When something fails, the screenshots are in `web/cypress/screenshots` and the downloaded files in `web/cypress/downloads` (both ignored by Git).

`make check` type-checks the test files, the Cypress configuration and the runner too. The last run passed all 11 scenarios (6.11.2026, Node 20.20.2, Cypress 15.21.1, Electron on Linux).

These tests only check that the features work and recover from errors. They don't test load, the biology, or whether the interface is easy to use - that would need real users.

## Data definitions and API responses

Run `make test-contracts` for the focused Python and client checks. The Python
suite calls the ASGI routes in process, with synchronous handlers run inline.
It checks response-model enforcement, the import/save/export path, source bytes,
published limits and exchange-file constraints. It does not test network or
worker-thread scheduling.

The client suite compiles the HTTP helper and generated definitions, then checks
valid responses, missing nested fields, invalid dictionary values, malformed
JSON and application errors. `make check` also regenerates the definitions in
check mode, so stale generated files fail the check.
