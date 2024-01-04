PIPENV = pipenv
PYTHON = $(PIPENV) run python
STREAMLIT = $(PYTHON) -m streamlit


.PHONY: help app show upgrade version


help:
	@echo "make app:     Run app.py script, piping stderr to Streamlit"
	@echo "make show:    Display currently-installed dependency graph information"
	@echo "make upgrade: Runs lock, then sync (pipenv)"
	@echo "make version: Upgrade cache version"

app:
	@$(STREAMLIT) run app.py

show:
	@$(PIPENV) graph

upgrade:
	@$(PIPENV) update --dev

version:
	@$(PYTHON) script/upgrade.py
