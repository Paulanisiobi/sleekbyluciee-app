#!/usr/bin/env bash
# Wrapper to run the E2E test quickly using docker compose one-off container
set -euo pipefail

echo "Starting compose services (detached): db, app, worker"
docker compose up --build -d db app worker

echo "Running E2E one-off container"
docker compose run --rm e2e

EXIT_CODE=$?

echo "Tearing down compose environment"
docker compose down --volumes --remove-orphans

exit $EXIT_CODE
