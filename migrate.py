import os
from dotenv import load_dotenv
import psycopg2

load_dotenv("backend/.env")

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL.startswith("postgresql+psycopg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")

conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True
cur = conn.cursor()

print("Adding columns to endpoints table...")
try:
    cur.execute("ALTER TABLE endpoints ADD COLUMN monitoring_enabled BOOLEAN NOT NULL DEFAULT FALSE;")
    cur.execute("ALTER TABLE endpoints ADD COLUMN monitoring_interval INTEGER NOT NULL DEFAULT 30;")
    cur.execute("ALTER TABLE endpoints ADD COLUMN last_check_at TIMESTAMP;")
    cur.execute("ALTER TABLE endpoints ADD COLUMN last_status_code INTEGER;")
    cur.execute("ALTER TABLE endpoints ADD COLUMN last_response_time DOUBLE PRECISION;")
    print("Endpoints table altered successfully.")
except Exception as e:
    print(f"Endpoints table already has these columns, or error: {e}")

print("Adding columns to metrics table...")
try:
    cur.execute("ALTER TABLE metrics ADD COLUMN source VARCHAR NOT NULL DEFAULT 'demo';")
    print("Metrics table altered successfully.")
except Exception as e:
    print(f"Metrics table already has these columns, or error: {e}")

cur.close()
conn.close()
