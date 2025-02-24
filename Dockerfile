# Use Python 3.9 slim image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY ["Team 1/Backend", "/app/"]

# Create necessary directories
RUN mkdir -p /app/PDF/Enterprise /app/PDF/Opensource /app/Web/Enterprise /app/Web/Opensource

# Expose port 8080 for Cloud Run
EXPOSE 8080

# Command to run the application
CMD ["uvicorn", "fast_api:app", "--host", "0.0.0.0", "--port", "8080"] 