.PHONY: up down logs ps clean backend frontend worker

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

ps:
	docker compose ps

clean:
	docker compose down -v

backend:
	cd backend && uvicorn app.main:app --reload --port 8000

worker:
	cd backend && python -m app.worker

frontend:
	cd frontend && npm run dev

bootstrap:
	cd backend && python -m app.bootstrap_db