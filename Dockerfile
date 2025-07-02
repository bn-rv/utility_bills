FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN pip install uv
RUN pip install --upgrade pip setuptools wheel importlib-metadata
RUN apt-get update
RUN apt-get install -y netcat-traditional

WORKDIR /app

COPY uv.lock pyproject.toml /app/

RUN uv sync

COPY . .

# Запускаем бота
CMD ["uv", "run", "python", "main.py"]
ENTRYPOINT ["sh", "fake_entrypoint.sh"]
