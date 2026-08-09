FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY document_ai ./document_ai
COPY scripts ./scripts

EXPOSE 8000
CMD ["uvicorn", "document_ai.api:app", "--host", "0.0.0.0", "--port", "8000"]
