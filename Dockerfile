FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY app ./app
COPY scripts ./scripts
RUN pip install --no-cache-dir -e .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
