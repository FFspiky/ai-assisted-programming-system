.PHONY: test check compile js-check

PYTHON ?= python3

compile:
	$(PYTHON) -m compileall -q app.py models.py config.py routes services tests migrations

test:
	$(PYTHON) -m unittest discover -s tests

js-check:
	@for f in static/js/*.js; do \
		node --check "$$f"; \
	done

check: compile test js-check
