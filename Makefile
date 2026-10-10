.PHONY: all install build test studio dev-api dev-ui clean

# Default: install dependencies and build studio
all: install build

# Install all dependencies (Python backend via uv, React UI via npm)
install:
	cd vero-cli && uv sync
	cd vero-studio && npm install

# Build the React Studio directly into the Python package's static directory
build:
	cd vero-studio && npm run build

# Run automated test suites (pytest + oxlint)
test:
	cd vero-cli && uv run pytest
	cd vero-studio && npm run lint

# Launch the packaged Vero Studio on http://localhost:8000
studio:
	cd vero-cli && uv run vero studio

# Run backend API in hot-reload mode
dev-api:
	cd vero-cli && uv run uvicorn vero.server:app --reload --port 8000

# Run frontend Studio in Vite hot-reload mode
dev-ui:
	cd vero-studio && npm run dev

# Clean generated build artifacts
clean:
	rm -rf vero-cli/vero/static/assets
	rm -rf vero-cli/dist vero-cli/build vero-cli/*.egg-info

# Run via Docker Compose (includes central PostgreSQL metadata DB)
docker-up:
	docker compose up --build -d

# Stop Docker Compose
docker-down:
	docker compose down
