# Implementation details
### Author: Lukas (Viridis) Dubsik

The application is split into the Python model and the React interface. Prepare and Review both work with the same study, so when a target or a decision changes, all the lists, details and counters using it change too. Export always takes the saved copy of the study, not the open one.

## Program structure

| Directory | Contents |
|-|-|
| `domain` | Data classes of the study, catalogue of references, checks of the input |
| `application` | Editing, import, save, undo and export |
| `adapters` | SQLite storage and the JSON file format |
| `api` | HTTP routes, bodies of the requests and error responses |
| `web/src/app` | Shared state, selectors and the controller |
| `web/src/features` | The Prepare, Review and Export views, each with its stylesheet |
| `web/src/shared` | HTTP helper, types, constants and the import preview |
| `web/src/styles` | Colours and styles shared by all the views |

All the limits (file sizes, number of targets, revisions, collections...) are in `domain/constants.py`. The generator copies them into `web/src/shared/constants.generated.ts`, so they are never written twice. `constants.ts` then picks the ones the views need and adds a few values used only by the browser (the API prefix, the session storage key).

A click in the GUI goes to the controller, which sends a request to FastAPI. The route passes it to a service in `application`, the service checks the data (using `domain`) and returns the changed study. The controller then gives the response to the reducer and every view using the study is drawn again. The page itself never reloads.

```text
React view -> controller -> fetch -> FastAPI -> application -> domain
                 |                                  |
            shared reducer                    repository / exchange
                                                   |
                                              SQLite / JSON
```

`domain` and `application` don't import FastAPI or SQLite. What they need from the storage and the file reading is described by protocols in `application/ports.py`, so the services can be called straight from Python, without a browser or a server (this is also handy for testing).

## Data classes

`Study` holds the request ID, the revisions, labels of the targets, the evidence and the review collections. `Revision` holds the reference, the profile, the coordinate system and the targets. Every change of the coordinates or of the reference creates a new revision, so the evidence imported earlier keeps the revision it was made for. Labels are stored apart from the revisions and can be renamed without creating a new one.

An evidence file has the candidates and the exact revision they were produced for. Candidate IDs are only unique inside one file (bundle), that's why `CandidateKey` is made of both the bundle ID and the candidate ID. `Membership` stores the decision about a candidate inside one collection, the candidate itself is never changed.

`TargetDraft` and `DecisionDraft` hold the text from the editors which isn't applied yet. For example an empty end coordinate stays an empty string in the draft, instead of becoming a broken target. The drafts are saved too (so nothing typed in the target or decision editor is lost), but they are never exported. Other inputs, like a new title not renamed yet or the fields of the reference change, are not drafts and are not saved.

`Session` holds the open study, its last saved copy and one previous copy for Undo. `WorkspaceService` keeps the sessions. `PrepareService` changes the targets and the reference, `ReviewService` the collections and decisions.

## Saving and errors

All operations go through one lock, as FastAPI runs the handlers in threads. Save writes the whole study in one SQLite transaction. A database the application doesn't recognize is never changed. The save counter only identifies the saved versions, it doesn't stop another tab from saving over it, so use one tab per study (the last save wins).

When an edit fails, the study stays as it was. When a save fails, the open study is still there and can be saved again. A lost response can mean the operation actually went through, so refresh before repeating it. Nothing is merged or reconciled automatically.

The client counts the changes of the editor text (`generation` in `state.ts`). If you keep typing while a save is running, the response updates the study but doesn't overwrite the newer text.

## HTTP interface

All the routes start with `/api/v1`. The bodies of the requests are in `api/requests.py`, the responses in `application/responses.py`. FastAPI checks every response against its model before sending it, and generates the full schema on `/openapi.json` (a readable version is on `/docs`). The file downloads are an exception - they send the prepared bytes as they are.

| Route | What it does |
|-|-|
| GET `/catalogue`, `/studies` | Supported references, or the list of saved studies |
| POST `/workspaces` | Opens a study, `source` is `new`, `saved`, `duplicate` or `request_import` |
| GET `/workspaces/{id}` | Returns the open study |
| DELETE `/workspaces/{id}` | `{discard: true}` closes it, the saved data stay |
| POST `/workspaces/{id}/commands` | `{draft_buffers, command}` applies one operation |
| POST `/workspaces/{id}/save` | `{draft_buffers}` saves the study and the unapplied edits |
| POST `/workspaces/{id}/undo` | Goes one unsaved change back |
| POST `/workspaces/{id}/validate` | `{revision_id, target_draft}` runs the local checks |
| POST `/imports` | Previews a request or evidence file (base64), evidence also says its study and revision |
| DELETE `/imports/{id}` | Cancels a preview |
| POST `/exports` | `{study_id, revision_id, kind, collection_ids}` prepares an export of the saved data |
| GET `/exports/{id}/file` | Downloads exactly the previewed file |
| GET `/examples/{name}` | One of the four example files |

Prepare has the commands `rename_study`, `apply_target`, `remove_target`, `rename_target` and `set_context`. Review has `attach_evidence`, creating/renaming/removing a collection, adding/removing a member and `set_decision`. They are all in `application/commands.py`.

Errors look like `{error: {code, message, diagnostics}}`. A diagnostic can point to the field it is about, so the GUI can jump to it. Import checks the schema, the request and revision, and the bundle ID. The same file twice is recognized as a duplicate, a different file with the same bundle ID is refused.

## Shared data definitions
The data are defined only once, in the Python models. `make contracts` generates from them the exchange schema, the TypeScript types of the client and the limits (see [Updating the format](../contracts/README.md#updating-the-format)). The generated files are committed, so the client can be built without Python.

The services return the models from `application/responses.py` instead of plain dictionaries. `StudyData` has the fields shared by the stored `Study` and by `StudyView` sent to the browser - the difference is that `StudyView` leaves out the evidence bytes. Each collection in it also carries `unresolved_count`, counted by the review rules in Python, so the client doesn't repeat that rule. `DecisionDraft` is a `Membership` with the ID of its collection added. The quick interval checks while typing stay in the browser, but only the domain checks decide.

## Connection to IRCOMP

The application works without IRCOMP. Its JSON schema is in `contracts`, the future mapping to the compiler and the F01-F10 checks are in the [integration notes](https://viridisquercusnova.atlassian.net/wiki/spaces/IRCOMP/pages/29392897). IRCOMP will own the specification language, goals, constraints, cartridge rules, the compiler and running the analysis. The GUI will only edit the supported input and show the output. Whatever the GUI can't represent has to be reported, not silently dropped.
