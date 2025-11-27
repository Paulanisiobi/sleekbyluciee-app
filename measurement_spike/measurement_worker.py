"""
"""Deprecated: Redis/RQ worker removed.

This file previously provided an RQ-based worker. The project now uses a
Postgres-backed job queue and `pg_worker.py`. Run `pg_worker.py` instead.
"""

if __name__ == '__main__':
    print('This worker is deprecated. Use pg_worker.py for Postgres-based jobs.')
*** End Patch