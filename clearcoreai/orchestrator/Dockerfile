# Use official Python image
FROM python:3.11-slim

# Set workdir
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source files
COPY main.py /app/
COPY agent_manager.py /app/
COPY mood.json /app/
COPY manifest_template.json /app/
COPY models/ /app/models/
COPY tools /app/tools
COPY license_keys.json /app/license_keys.json
COPY memory/ /app/memory/
RUN mkdir -p memory/short_term && chmod -R 755 memory

# Expose port
EXPOSE 8000

# Start app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]