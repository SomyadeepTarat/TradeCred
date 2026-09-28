FROM api_image
USER root
COPY services/bank-simulator/server.py services/bank-simulator/signing.py /simulator/
ENV PYTHONPATH=/app:/simulator
WORKDIR /app
CMD ["/app/.venv/bin/uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8090"]
