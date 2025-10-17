# Start from the official Python base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy all project files
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port for Elastic Beanstalk health check
EXPOSE 80

# Set environment variables
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PORT=80

# Command to run the Flask app using Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:80", "app:app"]
