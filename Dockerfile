# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables to ensure output is logged
ENV PYTHONUNBUFFERED=1

# Install Poetry
RUN pip install poetry

# Set the working directory in the container
WORKDIR /AIEVAL_Backend

# Copy the pyproject.toml and poetry.lock files to the working directory
COPY pyproject.toml poetry.lock* /AIEVAL_Backend/

# Install the dependencies
RUN poetry install --no-root --no-interaction --no-ansi

# Copy the rest of the application code to the working directory
COPY . /AIEVAL_Backend

# Expose the port FastAPI will run on
EXPOSE 8000

# Command to run the FastAPI app with Uvicorn
CMD ["poetry", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
