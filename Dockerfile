FROM python:3.12-slim

WORKDIR /app
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY steamprice steamprice
COPY api api

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
