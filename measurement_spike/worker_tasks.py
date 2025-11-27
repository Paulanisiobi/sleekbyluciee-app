"""Deprecated Redis helper.

This file previously provided a Redis-backed wrapper. The project now uses
Postgres-backed jobs (`db.py` + `pg_worker.py`).
"""

if __name__ == '__main__':
    print('worker_tasks.py is deprecated. Use pg_worker.py / Postgres jobs instead.')
