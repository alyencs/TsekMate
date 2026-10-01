# TsekMate API for Google Cloud Run (or any container host).
#   gcloud run deploy tsekmate-api --source apps/api --region asia-southeast1 --allow-unauthenticated \
#     --set-env-vars ANTHROPIC_MODEL=claude-sonnet-5-5,CORS_ORIGINS=https://<your-app>.vercel.app,PUBLIC_API_URL=https://<run-url> \
#     --set-secrets ANTHROPIC_API_KEY=anthropic-key:latest,SUPABASE_SERVICE_KEY=supabase-key:latest,SUPABASE_URL=supabase-url:latest
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY prompts ./prompts
COPY assets ./assets
# Cloud Run sets $PORT. Single worker: grading jobs run in background threads of this process.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1
