run-server:
	uvicorn app:api --reload

freeze:
	pip freeze > requirements.txt

install:
	pip install -r requirements.txt