# Use an official Python runtime as a base image
FROM python:3.12-slim

# Install build dependencies
RUN apt-get update -y && apt-get install -y gcc python3-dev

# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Run main.py when the container launches
CMD ["python", "-u", "main.py"]
