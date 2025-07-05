FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN pip install uv

WORKDIR /app

COPY uv.lock pyproject.toml /app/

RUN uv sync

COPY . .

CMD ["uv", "run", "python", "main.py"]
