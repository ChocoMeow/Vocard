# Use an official Python runtime as a base image
FROM python:3.12-slim

# Install build dependencies and supervisor
RUN apt-get update -y && apt-get install -y gcc python3-dev supervisor

# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the supervisor configuration file
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Run supervisor to manage both processes main.py and webapp.py
CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]