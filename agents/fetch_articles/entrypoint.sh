#!/bin/sh

# Ensure required memory folders exist
mkdir -p memory/short_term memory/long_term

# Optional: set write permissions to avoid permission issues
chmod -R 777 memory

# Create aiwaterdrops.json if it doesn't exist
if [ ! -f memory/short_term/aiwaterdrops.json ]; then
  echo '{"aiwaterdrops_consumed": 0.0}' > memory/short_term/aiwaterdrops.json
fi

# Copy example articles to long-term memory if not already present
for file in input_examples/*.txt; do
  target="memory/long_term/$(basename "$file")"
  if [ ! -f "$target" ]; then
    cp "$file" "$target"
    echo "✔ Copied $(basename "$file") to memory/long_term/"
  fi
done

# Start the FastAPI app
exec uvicorn app:app --host 0.0.0.0 --port 8500