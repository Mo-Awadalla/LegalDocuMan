.PHONY: test-backend lint-frontend build-frontend docker-check docker-build verify

test-backend:
	python -m pytest tests

lint-frontend:
	npm --prefix frontend run lint

build-frontend:
	npm --prefix frontend run build

docker-check:
	docker compose config

docker-build:
	docker build .

verify: test-backend lint-frontend build-frontend docker-check
