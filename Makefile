# IRCOMP-GUI - install, build, run, check, test and pack
# Author: Lukas (Viridis) Dubsik

PYTHON ?= python3

.PHONY: install install-dev build run contracts check format test test-unit pack

install:
	$(PYTHON) -m venv .venv
	.venv/bin/python -m pip install -r requirements.txt
	.venv/bin/python -m pip install --no-build-isolation --no-deps -e .
	npm --prefix web ci

install-dev: install
	.venv/bin/python -m pip install -r requirements-dev.txt

build:
	npm --prefix web run build

run:
	.venv/bin/ircomp-gui

contracts:
	PYTHONPATH=src .venv/bin/python scripts/generate_contracts.py

check:
	PYTHONPATH=src .venv/bin/python scripts/generate_contracts.py --check
	.venv/bin/ruff check src
	.venv/bin/ruff format --check src
	.venv/bin/pyright
	npm --prefix web run check

format:
	.venv/bin/ruff format src
	npm --prefix web run format

test-unit:
	PYTHONPATH=src .venv/bin/python -m unittest discover -s tests

test: build test-unit
	npm --prefix web run test:e2e

pack:
	git diff --quiet HEAD
	test -z "$$(git ls-files --others --exclude-standard)"
	mkdir -p release
	git archive --format=zip --prefix=IRCOMP-GUI/ --output=release/ircomp-gui-source.zip HEAD
	cd release && sha256sum ircomp-gui-source.zip > ircomp-gui-source.zip.sha256
