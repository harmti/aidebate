FROM python:3.12-slim

WORKDIR /app

# Copy requirements
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN pip install --no-cache-dir pip-tools && \
    pip-compile pyproject.toml --output-file=requirements.txt && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install -e .

# Copy application code
COPY app/ ./app/
COPY run.py ./
COPY start.py ./

# Create logs directory
RUN mkdir -p logs && chmod 777 logs

# Expose the port the app runs on
EXPOSE 8000

# Set environment variable for Railway
ENV PORT=8000

# Command to run the application - use the start script
CMD ["python", "start.py"]
