prod:
	nohup uvicorn app:app --host 0.0.0.0 --port 3389 &

dev:
	ENV=dev uvicorn app:app --host 0.0.0.0 --port 8000 --reload

run-server:
	ENV=prod uvicorn app:app --host 0.0.0.0

freeze:
	pip freeze > requirements.txt

install:
	pip install -r requirements.txt

kill-server:
	@PID=$$(ps -ef | grep "ttobot" | grep -v "grep" | awk '{print $$2}'); \
	if [ -z "$$PID" ]; then \
		echo "또봇 서버를 찾을 수 없어요."; \
	else \
		echo "또봇 서버를 종료합니다. PID: $$PID"; \
		kill $$PID; \
	fi