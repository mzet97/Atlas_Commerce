FROM python:3.14-slim
WORKDIR /srv
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir .
ENV PYTHONPATH=/srv/src
EXPOSE 8000
CMD ["uvicorn", "atlas_control.main:app", "--host", "0.0.0.0", "--port", "8000"]
