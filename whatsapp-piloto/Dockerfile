FROM python:3.12.12-slim@sha256:f3fa41d74a768c2fce8016b98c191ae8c1bacd8f1152870a3f9f87d350920b7c
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY relay.py /app/relay.py
RUN useradd --uid 10001 --create-home app && mkdir /data && chown app:app /data
USER 10001:10001
CMD ["python", "relay.py"]
