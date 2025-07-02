FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN pip install uv
RUN pip install --upgrade pip setuptools wheel importlib-metadata
RUN apt-get update && apt-get -y dist-upgrade
RUN apt-get -y install build-essential libssl-dev libffi-dev libblas3 libc6 liblapack3 gcc python3-dev python3-pip cython3
RUN apt-get -y install python3-numpy python3-scipy
RUN apt install -y netcat

WORKDIR /app

COPY uv.lock pyproject.toml /app/

RUN uv sync

COPY . .

# Запускаем бота
CMD ["uv", "run", "python", "main.py"]
ENTRYPOINT ["sh", "fake_entrypoint.sh"]
