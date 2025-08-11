#!/bin/sh

# Ensure required memory folders exist
mkdir -p memory/short_term memory/long_term memory/output log

# Optional: set write permissions to avoid permission issues
chmod -R 777 memory log

# Start the FastAPI app on port 8700
exec uvicorn app:app --host 0.0.0.0 --port 8700