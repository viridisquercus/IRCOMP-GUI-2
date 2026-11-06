# Implementation details

The application has a Python model and a React interface. The same study is used
by Prepare and Review, so changing a target or a decision updates the related
lists, details and counts. Export uses the saved copy of that study.

## Program structure

| Directory | What it contains |
| --- | --- |
| `domain` | Study data classes, reference metadata and input checks |
| `application` | Functions for editing, importing, saving and exporting |
| `adapters` | SQLite storage and the local JSON file format |
| `api` | HTTP request classes, routes and error responses |
| `web/src/app` | Shared state, selectors and controller |
| `web/src/features` | Prepare, Review and Export views |
| `web/src/shared` | HTTP helper, shared types and import preview |

All limits (file sizes, number of targets, revisions, collections and so on) are
kept in `domain/constants.py`. The few the client needs for earlier messages are
repeated in `web/src/shared/constants.ts`; the service checks all of them again.

The GUI calls the controller, which sends a fetch request to FastAPI. The route
passes the operation to an application service. That service checks the data and
returns the changed study. The controller then sends the response to the reducer,
which updates all views using it. The page does not reload.

```text
React view -> controller -> fetch -> FastAPI -> application -> domain
                 |                                  |
            shared reducer                    repository / exchange
                                                   |
                                              SQLite / JSON
```

The domain and application code do not import FastAPI or a concrete SQLite
adapter. Storage and file handling are described by Python protocols in
`application/ports.py`. This allows the services to be called directly from
Python, without starting a browser.

## Data classes

`Study` contains the request ID, revisions, target labels, evidence and review
collections. `Revision` contains the reference, profile, coordinate convention
and targets. Analytical changes create another revision so that earlier evidence
keeps its original context. Labels are stored separately and can be renamed
without changing the request context.

An evidence file contains candidates and the context in which they were produced.
Candidate IDs are only unique inside their bundle, so `CandidateKey` uses both
bundle ID and candidate ID. `Membership` stores a decision inside a collection;
it does not modify the candidate itself.

`TargetDraft` and `DecisionDraft` hold unapplied editor text. For example, an empty
coordinate remains a string in the draft rather than becoming an invalid accepted
interval. The draft can be saved for recovery. Export includes accepted data only.

`Session` keeps the working study, the last saved copy and one previous copy for
Undo. `WorkspaceService` manages these sessions. `PrepareService` changes targets
and request context; `ReviewService` changes collections and decisions.

## Saving and error handling

A process-local lock orders service operations. Save writes the complete study
using one SQLite transaction. The existing database layout is retained. Its save
counter identifies snapshots; it does not prevent another tab from saving.
Use one tab per study because the latest explicit Save replaces the stored copy.

After a failed edit, the accepted data stays unchanged. After a failed Save, the
working data remains available. A lost response may mean the operation already
succeeded; refresh the working state before repeating it. There is no automatic
merge or response reconciliation.

The client keeps a small editor counter. If the user types while Save is running,
the earlier response updates accepted data without replacing the newer text.
The accepted model is never reconstructed from DOM attributes.

## HTTP interface

All routes below use the `/api/v1` prefix. Request classes are in `api/requests.py`.
The complete runtime schema is generated at `/openapi.json`, with a readable
version at `/docs`.

| Route | Input and operation |
| --- | --- |
| GET `/catalogue`, `/studies` | Read supported metadata or saved study summaries |
| POST `/workspaces` | Open source `new`, `saved`, `duplicate` or `request_import` |
| GET `/workspaces/{id}` | Read the working study |
| DELETE `/workspaces/{id}` | `{discard: true}` closes a working copy, keeping saved data |
| POST `/workspaces/{id}/commands` | `{draft_buffers, command}` applies a typed operation |
| POST `/workspaces/{id}/save` | `{draft_buffers}` saves accepted data and editor text |
| POST `/workspaces/{id}/undo` | Restore one unsaved accepted change |
| POST `/workspaces/{id}/validate` | `{revision_id, target_draft}` runs local checks |
| POST `/imports` | Inspect base64 request/evidence bytes; evidence names its workspace and revision |
| DELETE `/imports/{id}` | Remove an import preview |
| POST `/exports` | `{study_id, revision_id, kind, collection_ids}` prepares saved data |
| GET `/exports/{id}/file` | Download the exact previewed bytes |
| GET `/examples/{name}` | Read one of four synthetic examples |

Prepare supports `rename_study`, `apply_target`, `remove_target`, `rename_target`
and `set_context`. Review supports `attach_evidence`, collection creation/rename/
removal, membership addition/removal and `set_decision`. The operation classes are
in `application/commands.py`.

Errors use `{error: {code, message, diagnostics}}`. A diagnostic can name an input
location so the GUI can focus the corresponding field. Import checks the schema,
request context and bundle identity. Matching bytes under the same bundle ID are
a duplicate; different bytes under that ID are rejected.

## Connection to IRCOMP

The application can run without IRCOMP. Its JSON schema stays in `contracts`;
future compiler mapping and the F01-F10 checks are kept in the
[integration notes](https://viridisquercusnova.atlassian.net/wiki/spaces/IRCOMP/pages/29392897).
IRCOMP will own the specification language, goals, constraints, cartridge rules,
compiler and execution policy. The GUI will edit supported input and display
identified output. An adapter must report missing or unsupported meaning rather
than quietly discarding it.
