#!/bin/sh

# Ensure required memory folders exist
mkdir -p memory/short_term memory/long_term

# Optional: set write permissions to avoid permission issues
chmod -R 777 memory

# Create aiwaterdrops.json if it doesn't exist
if [ ! -f memory/short_term/aiwaterdrops.json ]; then
  echo '{"aiwaterdrops_consumed": 0.0}' > memory/short_term/aiwaterdrops.json
fi

# Start the FastAPI app
exec uvicorn main:app --host 0.0.0.0 --port 8000