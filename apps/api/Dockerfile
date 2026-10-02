# TsekMate API for Google Cloud Run (or any container host).
#   gcloud run deploy tsekmate-api --source apps/api --region asia-southeast1 --allow-unauthenticated \
#     --no-cpu-throttling --min-instances=1 --max-instances=1 \
#     --set-env-vars ANTHROPIC_MODEL=claude-haiku-4-5,CORS_ORIGINS=https://<your-app>.vercel.app,PUBLIC_API_URL=https://<run-url>,DEMO_TEACHER_EMAIL=<teacher-email> \
#     --set-secrets ANTHROPIC_API_KEY=anthropic-key:latest,SUPABASE_SERVICE_KEY=supabase-key:latest,SUPABASE_URL=supabase-url:latest,AUTH_SECRET=auth-secret:latest,IMAGE_SIGNING_SECRET=image-signing-secret:latest,DEMO_TEACHER_PASSWORD=teacher-password:latest
# --allow-unauthenticated only lets requests reach the container: the API itself requires the teacher sign-in on every
# data route. --no-cpu-throttling keeps background grading and the Saver batch poller running between requests;
# a single instance keeps grading progress and settings in one process (see README, "Deploying").
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_ENV=production
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY prompts ./prompts
COPY assets ./assets
# Run as an unprivileged user; it owns /app so the render cache and the demo cache can be written.
RUN useradd --create-home --uid 10001 tsekmate && chown -R tsekmate /app
USER tsekmate
# Cloud Run sets $PORT. Single worker: grading jobs run in background threads of this process.
# --proxy-headers: take the client address from Cloud Run's X-Forwarded-For (only Google's front end can reach the
# container), so sign-in throttling counts each client separately instead of the proxy.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --proxy-headers --forwarded-allow-ips="*"
