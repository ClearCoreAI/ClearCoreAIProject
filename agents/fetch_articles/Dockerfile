# Use official Python image
FROM python:3.11-slim

# Set workdir
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source files
COPY app.py /app/
COPY mood.json /app/
COPY license_keys.json.template /app/
COPY manifest.json /app/
COPY memory/ /app/memory/

# Expose port
EXPOSE 8500

# Start app
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8500"]