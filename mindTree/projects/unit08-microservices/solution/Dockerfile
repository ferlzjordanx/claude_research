# One image, two services: docker-compose.yml picks the command.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY common ./common
COPY messaging ./messaging
COPY notifications ./notifications
COPY orders ./orders
COPY payments ./payments

RUN useradd --create-home --uid 10001 app
USER app
EXPOSE 8000 8001
CMD ["uvicorn", "orders.main:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000"]
