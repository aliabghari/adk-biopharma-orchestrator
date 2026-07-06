# Use offical Python slim base image
FROM python:3.14-slim

# Set environment variables to prevent Python writing pyc files and buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set container working directory
WORKDIR /app

# Copy dependency specifications first to leverage caching
COPY requirements.txt .

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all remaining source codes
COPY . .

# Expose port 8080 for GCP Cloud Run
EXPOSE 8080

# Expose Streamlit configurations and launch server
CMD ["python", "-m", "streamlit", "run", "dashboard.py", "--server.port=8080", "--server.address=0.0.0.0"]
