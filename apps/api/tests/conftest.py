import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "scripts"))

# Tests always run in development mode on the in-memory store with no live AI, whatever a local .env says.
# Values set here win because load_dotenv never overrides variables that already exist.
os.environ["APP_ENV"] = "development"
os.environ["SUPABASE_URL"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["DEMO_TEACHER_EMAIL"] = "areyes@university.edu.ph"
os.environ["DEMO_TEACHER_PASSWORD"] = "tsekmate"
os.environ["AUTH_SECRET"] = ""
os.environ["IMAGE_SIGNING_SECRET"] = ""
