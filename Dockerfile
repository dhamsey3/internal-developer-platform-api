FROM python:3.11-slim

# Create non-root user
RUN useradd -m appuser
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
	&& rm -rf /root/.cache

COPY . .

# Change ownership and permissions
RUN chown -R appuser:appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
