# Base image: minimal Python 3.11
FROM python:3.11-slim

# --- Environment optimizations ---
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# --- Working directory inside container ---
WORKDIR /app

# --- Install Python dependencies ---
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# --- Copy full source code into container ---
COPY . .
RUN mkdir -p memory/short_term && chmod -R 755 memory

# --- Expose FastAPI agent port (customizable per agent) ---
EXPOSE 8500

# --- Default startup command for this agent ---
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8500"]