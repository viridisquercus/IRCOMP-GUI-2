# IRCOMP-GUI: preparing CRISPR requests and reviewing their results
### Author: Lukas (Viridis) Dubsik
#### Version: 0.1


## Table of Contents
- [IRCOMP-GUI: preparing CRISPR requests and reviewing their results](#ircomp-gui-preparing-crispr-requests-and-reviewing-their-results)
  - [Introduction](#introduction)
  - [Installation and execution](#installation-and-execution)
  - [Using the application](#using-the-application)
    - [Prepare](#prepare)
    - [Review](#review)
    - [Save and export](#save-and-export)
  - [Implementation](#implementation)
  - [Code checks](#code-checks)
  - [Testing](#testing)
  - [Known limitations](#known-limitations)
  - [Source archive](#source-archive)
  - [Libraries and sources](#libraries-and-sources)


## Introduction
IRCOMP-GUI is a local application for preparing CRISPR analysis requests and for going through the results that come back. It is the first GUI for **IRCOMP**, the part users actually see. The data and all the operations are in **Python** (FastAPI), the interface is **React** with **TypeScript**.

The application has three views: **Prepare**, **Review** and **Export**. In Prepare you choose the reference and set the target intervals. In Review you import the evidence (candidates found by some tool), put candidates into collections and write down your decision about each of them. Export then writes either the request or the review package from the saved study.

To be clear about it from the start - this application doesn't compute anything - it is just stuble for now. There is no CRISPR search, no off-target scoring, nothing like that. It only prepares the input for IRCOMP and shows what comes out.

## Installation and execution
Python 3.12 or newer and Node 20.19 or newer are needed. I've tested it with Python 3.14.6, Node 20.20.2 and npm 10.8.2 on Ubuntu 26.04, other versions and systems weren't tried.

From the root of the repository run:

```sh
make install
make build
make run
```

The first one creates `.venv`, installs the Python package and downloads the web dependencies. The second builds the web client. After `make run` the application is on [http://127.0.0.1:8000](http://127.0.0.1:8000). Another port can be chosen with `.venv/bin/ircomp-gui --port 8001`.

The same without Make:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install --no-build-isolation --no-deps -e .
npm --prefix web ci
npm --prefix web run build
.venv/bin/ircomp-gui
```

When working on the frontend, start the Python service on port 8000 and then `npm --prefix web run dev`. Vite runs on port 5173 and sends the API calls over to Python, so the page reloads on every change. FastAPI also generates the documentation of the HTTP interface, it is on `/docs` (and the schema on `/openapi.json`).

## Using the application

### Prepare
The quickest way to try it is **Open sample request** and then **Open request**. The sample is made up and already has one target. Otherwise create a new study under **New / Open / Rename / Duplicate**.

Click a target to edit it, or use **Add target** for a new one. The coordinates are 0-based and the end is not included, so start 100 and end 200 means 100 bases (same as in BED files). **Apply target** checks the input and changes the request. Changing the coordinates creates a new *revision* of the request, while changing only the label doesn't - the label is just for you.

**Check request** lists what is checked. Only the reference IDs and the chromosome lengths are checked here. Whether the FASTA file exists, or whether the target makes sense biologically, is not.

### Review
Review shows the evidence of the selected revision. Import an evidence file, or try the example with **Try the example evidence**. The file is first only previewed and attached after you confirm it. A file made for a different request or revision is refused.

Select a candidate and add it to a collection. The decision (disposition), its reason and the other candidates supporting it are stored in that collection. One candidate can be in more collections with a different decision in each of them. The imported scores never change. A score of 0 is a real value and is shown differently from a score that wasn't sent at all.

### Save and export
**Apply** changes the open study, **Save study** writes it into SQLite, including the edits in the target and decision editor you haven't applied yet (so they aren't lost). Other unfinished inputs, like a new title not renamed yet, aren't saved. **Undo** goes one change back. After a save there is nothing to undo.

Export only uses saved data. Choose the request or the review package, check the preview and download the JSON. If some decisions aren't finished, the review package is marked as a draft. The package contains the original evidence files together with their checksums. Unapplied edits are never exported.

## Implementation
The Python code is in `src/ircomp_gui`:

| Package | Contents |
|-|-|
| `domain` | Data classes, catalogue of references, checks, limits (`constants.py`) |
| `application` | Operations - editing, import, save, undo and export |
| `adapters` | SQLite storage and reading of the JSON files |
| `api` | HTTP routes and bodies of the requests (the responses are in `application/responses.py`) |

The React code is in `web/src`. There is one shared state (a reducer) and the views only dispatch changes to it, all the calls to Python go through `app/controller.ts`. Each view has its own stylesheet next to it, the shared styles are in `styles/base.css`.

The data are defined only once, in the Python models - the exchange schema, the TypeScript types and the limits for the client are generated from them by `scripts/generate_contracts.py`. After changing a model run `make contracts` and commit the generated files too (more in [Updating the format](contracts/README.md#updating-the-format)). The responses are checked by FastAPI against their models before they are sent.

More is written in [Architecture](docs/architecture.md) (classes and API), [File formats](contracts/README.md) (the JSON exchange) and [Design](docs/design/README.md) (wireframes). The plans for connecting it to IRCOMP are in the [IRCOMP integration notes](https://viridisquercusnova.atlassian.net/wiki/spaces/IRCOMP/pages/29392897).

## Code checks
The application itself is small, but I kept the checks strict (because I love strict typing and checking), it caught a lot of mistakes early. To install and run them:

```sh
make install-dev
make check
```

This first checks that the generated files are up to date, then runs *Ruff* (lint and formatting), *Pyright* in strict mode, the TypeScript compiler and *Prettier* (also over the Cypress tests and the test runner). `make format` fixes the formatting. Python uses typed functions, NumPy docstrings, four spaces and double quotes, TypeScript two spaces and double quotes. The settings are in `pyproject.toml`, `web/tsconfig.json` and `web/.prettierrc.json`.

## Testing
After installation run `make test`. It builds the client, runs the Python tests and then starts its own server for the 11 Cypress scenarios (all AI generated), against a temporary SQLite database, so your saved studies are never touched. Both the server and the database are removed at the end.

`make test-unit` runs only the Python tests. They call the routes directly, without a server, so they take about a second.

The tests go through editing, recovery of unapplied edits, Undo, imports, decisions in collections, downloading the review, and requests that fail or come back late. `npm --prefix web run test:e2e:open` opens the Cypress window instead (build the client first). The scenarios are described in [testing](docs/testing.md).

## Known limitations
- The studies are saved in `~/.local/share/ircomp-gui/workspace.sqlite3`. `IRCOMP_GUI_DATABASE` chooses another database file and `IRCOMP_GUI_WEB` another directory with a built client.
- The open studies (and import previews) live only in the memory of the service. Restarting it loses whatever wasn't saved. Reloading the page reconnects to the study while the service is still running, but text typed just before the reload may be lost.
- Use one tab per study. Operations are ordered by a lock and SQLite saves the whole study in one transaction, but two tabs aren't merged - the last save wins. After a connection error, press **Refresh working state** and check what was applied before trying again.
- YAML editing, the IRCOMP compiler, workflow graphs and running the analysis are all future work. The JSON format here is not the IRCOMP specification language.

## Source archive
`make pack` (run on a clean, committed checkout) creates `release/ircomp-gui-source.zip` and its SHA-256 file. The archive has the tracked source, configuration, contracts, examples and documentation. Installed dependencies, databases, build output and test output are left out.

## Libraries and sources
The application uses FastAPI, Pydantic, Uvicorn, jsonschema, React and Vite, Hatchling and editables are used for installing the Python package. All of them keep their own licences. The chromosome lengths in the catalogue come from the NCBI assembly report, which is kept in `contracts/references` together with its checksum.

The [contribution record](ai-audit.md) describes scope of AI use.
