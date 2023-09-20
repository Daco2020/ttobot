run-server:
	uvicorn app:app --host 0.0.0.0 --port 8000

freeze:
	pip freeze > requirements.txt

install:
	pip install -r requirements.txt
