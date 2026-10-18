.PHONY: test check compile js-check lint format-check audit smoke

PYTHON ?= python3

compile:
	$(PYTHON) -m compileall -q app.py models.py config.py routes services modules tests migrations

test:
	$(PYTHON) -m unittest discover -s tests

js-check:
	@for f in static/js/*.js modules/task_room/static/*.js modules/co_create/static/*.js; do \
		node --check "$$f"; \
	done

lint:
	$(PYTHON) -m ruff check .

format-check:
	$(PYTHON) -m black --check .

audit:
	$(PYTHON) -m pip_audit -r requirements.txt --cache-dir /tmp/pip-audit-cache

smoke:
	npm run smoke

check: compile test js-check
