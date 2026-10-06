FROM python:3.12-slim

RUN pip install --no-cache-dir paho-mqtt==2.1.0

COPY simulador.py /app/simulador.py

ENTRYPOINT ["python", "-u", "/app/simulador.py"]
