FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home atlas
COPY --chown=atlas:atlas app app
COPY --chown=atlas:atlas web web
COPY --chown=atlas:atlas data data
RUN mkdir -p /app/.data && chown atlas:atlas /app/.data
USER atlas
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
