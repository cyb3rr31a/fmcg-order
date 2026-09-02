FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the base directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files into /app
COPY . /app

# MOVE working directory into src/ so Python finds your modules instantly
WORKDIR /app/src

EXPOSE 8080

# Run uvicorn directly on main:app
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}