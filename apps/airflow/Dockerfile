# Optimized Airflow image with ML dependencies
FROM apache/airflow:2.10.2

# Switch to root for system packages
USER root

# Install system dependencies for ML libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    libgomp1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Switch back to airflow user
USER airflow

# Copy and install Python dependencies
COPY --chown=airflow:root requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV AIRFLOW__CORE__LOAD_EXAMPLES=False
