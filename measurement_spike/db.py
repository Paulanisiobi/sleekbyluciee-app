"""Postgres helper functions for measurement jobs.

Provides a minimal API to create and update jobs in a `measurement_jobs` table.
"""
import os
import uuid
import json
import time
from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    # leave None — caller should handle absence
    DATABASE_URL = None


def get_conn():
    if not DATABASE_URL:
        raise RuntimeError('DATABASE_URL not set')
    return psycopg2.connect(DATABASE_URL)


def ensure_table():
    sql = """
    CREATE TABLE IF NOT EXISTS measurement_jobs (
      id UUID PRIMARY KEY,
      created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
      status TEXT NOT NULL DEFAULT 'queued',
      payload JSONB,
      result JSONB,
      attempts INT DEFAULT 0,
      last_error TEXT
    );
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            conn.commit()
    finally:
        conn.close()


def create_job(payload: dict, status: str = 'queued') -> str:
    job_id = str(uuid.uuid4())
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO measurement_jobs (id, payload, status) VALUES (%s, %s, %s)",
                        (job_id, json.dumps(payload), status))
            conn.commit()
    finally:
        conn.close()
    return job_id


def fetch_and_lock_job():
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("BEGIN;")
            cur.execute("SELECT * FROM measurement_jobs WHERE status='queued' ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1")
            job = cur.fetchone()
            if job:
                cur.execute("UPDATE measurement_jobs SET status='processing' WHERE id=%s", (job['id'],))
                conn.commit()
                return job
            conn.rollback()
            return None
    finally:
        conn.close()


def update_job_completed(job_id: str, result: dict):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE measurement_jobs SET status='completed', result=%s WHERE id=%s", (json.dumps(result), job_id))
            conn.commit()
    finally:
        conn.close()


def update_job_failed(job_id: str, error_text: str):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE measurement_jobs SET status='failed', last_error=%s WHERE id=%s", (error_text, job_id))
            conn.commit()
    finally:
        conn.close()


def increment_attempts(job_id: str):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE measurement_jobs SET attempts = attempts + 1 WHERE id=%s", (job_id,))
            conn.commit()
    finally:
        conn.close()


def mark_job_dead(job_id: str, reason: str = None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE measurement_jobs SET status='dead', last_error=%s WHERE id=%s", (reason, job_id))
            conn.commit()
    finally:
        conn.close()


def get_job(job_id: str):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM measurement_jobs WHERE id=%s", (job_id,))
            return cur.fetchone()
    finally:
        conn.close()


def wait_for_completion(job_id: str, timeout: int = 30, poll_interval: float = 0.5):
    start = time.time()
    while True:
        job = get_job(job_id)
        if not job:
            return None
        if job['status'] in ('completed', 'failed'):
            return job
        if time.time() - start > timeout:
            return job
        time.sleep(poll_interval)
