run-server:
	uvicorn app:api --host 0.0.0.0 --port 8000 --reload

freeze:
	pip freeze > requirements.txt

install:
	pip install -r requirements.txt

type-check:
	mypy -p app