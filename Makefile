.PHONY: install test lint run dev dashboard demo eval docker-up

install:
	python -m pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check app tests

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev: run

dashboard:
	streamlit run dashboard/streamlit_app.py

demo:
	python scripts/demo_run.py

eval:
	python -m app.evals.run_eval

docker-up:
	docker compose up --build
