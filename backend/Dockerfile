FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY data ./data
EXPOSE 8000
# Talk to an Ollama daemon on the host by default; override OLLAMA_HOST or set
# RAG_EMBED_BACKEND=offline / RAG_LLM_BACKEND=offline to run without one.
ENV OLLAMA_HOST=http://host.docker.internal:11434
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
