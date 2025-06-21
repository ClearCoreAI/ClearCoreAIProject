# Base image: minimal Python 3.11
FROM python:3.11-slim

# --- Environment optimizations ---
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# --- Set working directory inside container ---
WORKDIR /app

# --- Install Python dependencies ---
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# --- Copy full source code into the container ---
COPY . .

# --- Create memory folders and set permissions (redundant with entrypoint but kept for safety) ---
RUN mkdir -p memory/short_term && chmod -R 755 memory

# --- Copy and prepare entrypoint script ---
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

# --- Expose FastAPI agent port (adjust per agent if needed) ---
EXPOSE 8600

# --- Default startup command: runs entrypoint script which prepares environment then launches app ---
ENTRYPOINT ["./entrypoint.sh"]