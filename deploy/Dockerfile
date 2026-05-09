FROM python:3.12-slim

WORKDIR /app
COPY server/requirements.txt /app/server/requirements.txt
RUN pip install --no-cache-dir -r /app/server/requirements.txt

COPY . /app
ENV HEALTH_STORE=/data/events.jsonl
EXPOSE 8787

CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8787"]
