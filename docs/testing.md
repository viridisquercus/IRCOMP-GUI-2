# Browser tests

### Name: Lukas (Viridis) Dubsik

## Running the tests

From the repository root, after `make install`, run:

```sh
make test
```

This builds the client and runs Cypress in headless Electron. The runner starts
the Python application on an available loopback port and uses a temporary SQLite
database. It overrides the normal database and web-directory settings for that
process. At the end, it stops the server and removes its database and log.

For an interactive run, first build the client, then open Cypress:

```sh
make build
npm --prefix web run test:e2e:open
```

The same runner keeps the temporary server alive while the Cypress window is open.
Each scenario creates or imports a separate study. Browser storage is cleared
between scenarios by Cypress. The scenarios can run independently and do not
require an earlier scenario to succeed.

Cypress 15.21.1 is pinned because it supports the Node 20 environment.
The first npm installation also downloads its browser binary. On Linux, Cypress
needs its documented [system libraries and Xvfb](https://docs.cypress.io/app/get-started/install-cypress#Linux-Prerequisites).

## Scenarios

| File | Scenario and expected result |
| --- | --- |
| `workspace.cy.ts` | An invalid interval cannot be applied; correction changes the accepted target. |
| `workspace.cy.ts` | Closing and reopening a saved study restores an invalid draft separately from its accepted interval. |
| `workspace.cy.ts` | Undo restores the accepted interval and pre-Apply draft; discarding the draft shows the restored value. Save clears Undo. |
| `workspace.cy.ts` | A malformed request file leaves the existing study unchanged. |
| `review.cy.ts` | Mismatching evidence is blocked, identical evidence is recognised as a duplicate, and zero remains different from an absent metric. |
| `review.cy.ts` | Collection decisions stay separate; removal can be undone and older evidence keeps its request revision. |
| `review.cy.ts` | A downloaded draft review contains the rationale and exact original evidence bytes. Both source and download checksums match. |
| `recovery.cy.ts` | A failed Save preserves accepted work and a later real Save succeeds. |
| `recovery.cy.ts` | A delayed Save response cannot overwrite newer editor text. |
| `recovery.cy.ts` | Refresh recovers an accepted command after its response is lost, without creating a second target. |
| `recovery.cy.ts` | Export last saved uses the stored interval while a newer accepted interval remains unsaved. |

The tests use the actual GUI, HTTP routes and SQLite storage. API reads check the
accepted state behind the visible controls. Imports use the existing synthetic
examples with new study, request, revision and bundle IDs. The tests do not add
special routes to the application.

## Failure simulation and limits

The failed-Save scenario substitutes one HTTP 503 response before the request
reaches storage, then retries against the real backend. It checks client recovery,
not a physical disk failure. The delayed-Save scenario delays a real response by
one second. The lost-response scenario lets the browser's real fetch finish and
then rejects it before the controller reads the result. The command has already
reached the backend; Refresh must find exactly one accepted target.

The suite has no automatic retries and does not use fixed waits to synchronise
steps. It waits for requests or checks the expected state. On failure, screenshots
are written under `web/cypress/screenshots`; downloaded JSON files are under
`web/cypress/downloads`. These files are ignored by Git and formatting checks.

`make check` also checks the TypeScript test files, Cypress configuration and Node
runner. The suite passed all 11 scenarios on 6 November 2026, using Node 20.20.2,
Cypress 15.21.1 and headless Electron on Linux. The production build and strict
source checks passed on the same revision.

These are functional regression and recovery checks. They do not measure
concurrent load, prove biological correctness or replace real-user usability
evaluation. Cypress is used directly; there is no Cucumber adapter or
second browser-testing framework.
