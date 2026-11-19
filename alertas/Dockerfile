FROM python:3.12-alpine
WORKDIR /app
COPY detector.py semaforos.py ./
RUN mkdir -p /dados
CMD ["python", "-u", "detector.py"]
