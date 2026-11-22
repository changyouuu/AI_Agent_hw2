FROM docker.io/library/python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY agents.py app.py formulas.py sample.pdf ./
ENV PAPER_DATA_DIR=/data OLLAMA_URL=http://host.containers.internal:11434
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.maxUploadSize=30", "--browser.gatherUsageStats=false"]
