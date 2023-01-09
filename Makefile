run-server:
	uvicorn app:app --reload
	
freeze:
	pip freeze > requirements.txt

install:
	pip install -r requirements.txt