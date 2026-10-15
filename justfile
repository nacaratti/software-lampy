# Lampy / fibersim dev tasks.
# Install `just` from https://github.com/casey/just then run `just <task>`.

# Run both API and Web dev servers in parallel
dev:
    just dev-api &
    just dev-web

# Start the FastAPI backend with auto-reload
dev-api:
    uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000

# Start the Vite frontend dev server
dev-web:
    cd frontend && npm run dev

# Install Python deps including the [backend] extras
install-backend:
    pip install -e ".[backend,dev]"

# Install JS deps
install-web:
    cd frontend && npm install

# Install everything
install: install-backend install-web

# Run all pytest tests
test:
    pytest -q

# Run the local phase verification scripts (sanity check that solver output
# hasn't regressed). Note: verification/ is gitignored, so these only exist
# on machines that have the original scripts.
verify:
    python verification/verify_fibersim.py
    python verification/verify_phase1_2.py
    python verification/verify_phase2_3.py
    python verification/verify_phase4.py
    python verification/verify_phase5.py

# Lint/format
fmt:
    ruff format src backend
    ruff check --fix src backend

# Build the production frontend bundle
build-web:
    cd frontend && npm run build
