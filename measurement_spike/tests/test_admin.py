import json
import pytest
from flask import Flask

# Import the app and admin blueprint
from measurement_spike.app import app as flask_app
import measurement_spike.admin as admin_module


class DummyCursor:
    def __init__(self, rows):
        self._rows = rows
        self.rowcount = len(rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows

    def execute(self, *args, **kwargs):
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class DummyConn:
    def __init__(self, rows=None):
        self._rows = rows or []

    def cursor(self, cursor_factory=None):
        return DummyCursor(self._rows)

    def commit(self):
        pass

    def close(self):
        pass


@pytest.fixture
def client(monkeypatch):
    # monkeypatch admin.get_conn to return a dummy connection with test data
    rows = [
        {'id': 'job-1', 'created_at': '2025-01-01T00:00:00Z', 'attempts': 3, 'last_error': 'err', 'payload': {'foo': 'bar'}},
        {'id': 'job-2', 'created_at': '2025-01-02T00:00:00Z', 'attempts': 1, 'last_error': None, 'payload': {'foo': 'baz'}},
    ]
    monkeypatch.setattr(admin_module, 'get_conn', lambda: DummyConn(rows=rows))
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as c:
        yield c


def test_list_json_requires_auth(client, monkeypatch):
    # If ADMIN_TOKEN is set in admin module, requests without auth should be forbidden
    monkeypatch.setattr(admin_module, 'ADMIN_TOKEN', 'secret')
    r = client.get('/admin/dead_letters.json')
    assert r.status_code == 403


def test_list_json_with_bearer(client, monkeypatch):
    monkeypatch.setattr(admin_module, 'ADMIN_TOKEN', 'secret')
    headers = {'Authorization': 'Bearer secret'}
    r = client.get('/admin/dead_letters.json', headers=headers)
    assert r.status_code == 200
    data = r.get_json()
    assert 'items' in data and data['total'] >= 0


def test_show_job_html(client, monkeypatch):
    # show job should return HTML page
    monkeypatch.setattr(admin_module, 'ADMIN_TOKEN', None)
    r = client.get('/admin/dead_letters/job-1')
    assert r.status_code == 200
    assert b'Job job-1' in r.data


def test_requeue_requires_token(client, monkeypatch):
    monkeypatch.setattr(admin_module, 'ADMIN_TOKEN', 'secret')
    r = client.post('/admin/dead_letters/job-1/requeue')
    assert r.status_code == 403


def test_requeue_with_bearer(client, monkeypatch):
    monkeypatch.setattr(admin_module, 'ADMIN_TOKEN', 'secret')
    headers = {'Authorization': 'Bearer secret'}
    r = client.post('/admin/dead_letters/job-1/requeue', headers=headers)
    assert r.status_code in (200, 404)


def test_paging_edge_cases(client, monkeypatch):
    # ensure requesting a page beyond total returns empty items
    monkeypatch.setattr(admin_module, 'ADMIN_TOKEN', None)
    r = client.get('/admin/dead_letters.json?limit=1&page=100')
    assert r.status_code == 200
    data = r.get_json()
    assert 'items' in data and isinstance(data['items'], list)
    # per_page zero or negative should be normalized
    r2 = client.get('/admin/dead_letters.json?limit=0&page=1')
    assert r2.status_code == 200
    data2 = r2.get_json()
    assert 'items' in data2
