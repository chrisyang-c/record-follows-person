.PHONY: db db-local migrate seed api web worker test lint eval codegen audit clean-records reset reset-docker

API_DIR=apps/api
WEB_DIR=apps/web
PGBIN=/opt/homebrew/opt/postgresql@17/bin

db:            ## start postgres via docker compose
	docker compose up -d postgres

db-local:      ## start postgres via Homebrew (no Docker on this machine)
	brew services start postgresql@17 || true
	@sleep 2
	-$(PGBIN)/createdb -h localhost record_follows_person 2>/dev/null || true
	$(PGBIN)/pg_isready -h localhost -p 5432

migrate:       ## PostgresSaver.setup() + thread registry table (only place setup() runs)
	cd $(API_DIR) && uv run python -m graphs.migrate

seed:          ## 3 residents × 14 days + 1 acute incident → records/{patient_id}
	cd $(API_DIR) && uv run python ../../data/seed/seed.py

api:           ## FastAPI dev server on :8000
	cd $(API_DIR) && uv run fastapi dev main.py --port 8000

worker:        ## timeout/escalation worker (also embedded in the API lifespan)
	cd $(API_DIR) && uv run python -m graphs.worker

web:           ## Next.js dev server on :3000
	cd $(WEB_DIR) && pnpm dev

test:          ## api unit + graph tests, web lint + tests
	cd $(API_DIR) && uv run ruff check . && uv run pytest -q
	cd $(WEB_DIR) && pnpm lint && pnpm test

lint:
	cd $(API_DIR) && uv run ruff check . && uv run ruff format --check .
	cd $(WEB_DIR) && pnpm lint

eval:          ## extraction eval on synthetic caregiver sentences → apps/api/eval/results.md
	cd $(API_DIR) && uv run python -m eval.run

codegen:       ## pydantic → TypeScript (packages/schema/ts/index.ts)
	cd $(API_DIR) && uv run python ../../packages/schema/codegen.py

audit:         ## web-design-guidelines audit of apps/web → docs/UI_AUDIT.md (see .claude/skills)
	@echo "Run: claude /web-design-guidelines apps/web/app  (results are pasted into the PR)"

clean-records:
	rm -rf records

reset:         ## drop + recreate the local DB, migrate, seed (clean demo state; brew postgres)
	-$(PGBIN)/psql -h localhost -d postgres -c "drop database if exists record_follows_person" -c "create database record_follows_person"
	$(MAKE) migrate
	$(MAKE) seed

reset-docker:  ## same for docker compose postgres
	docker compose exec -T postgres psql -U rfp -d postgres -c "drop database if exists record_follows_person" -c "create database record_follows_person"
	$(MAKE) migrate
	$(MAKE) seed
