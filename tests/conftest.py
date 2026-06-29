"""
Test fixtures — shared setup for all tests.

Creates a fresh in-memory SQLite database per test to ensure isolation.
Uses httpx.AsyncClient for testing FastAPI without starting a real server.
Captures request/response details for HTML report visibility.
"""

import pytest
import pytest_asyncio
import os
import json
from httpx import AsyncClient, ASGITransport
from pytest_html import extras as pytest_html_extras

# Use in-memory database for tests
os.environ["DATABASE_PATH"] = ":memory:"

from backend.app.main import app
from backend.app.database import get_db, SCHEMA_SQL, SEED_SQL

# Global dict to store logs per test (keyed by node id)
_test_api_logs = {}


class LoggingClient:
    """
    Wrapper around AsyncClient that logs request/response pairs.
    Stores logs globally so the pytest hook can access them after test completes.
    """

    def __init__(self, client: AsyncClient, test_node_id: str):
        self._client = client
        self._test_node_id = test_node_id
        _test_api_logs[test_node_id] = []

    def _format_log(self, method, url, headers, body, response):
        """Format a request/response pair for report display."""
        try:
            resp_body = response.json()
        except Exception:
            resp_body = response.text

        entry = {
            "request": {
                "method": method,
                "url": str(url),
                "headers": {k: v for k, v in headers.items() if k.startswith("X-") or k == "Content-Type"},
                "body": body,
            },
            "response": {
                "status_code": response.status_code,
                "body": resp_body,
            },
        }
        _test_api_logs[self._test_node_id].append(entry)
        return response

    async def post(self, url, json=None, headers=None, **kwargs):
        headers = headers or {}
        response = await self._client.post(url, json=json, headers=headers, **kwargs)
        self._format_log("POST", url, headers, json, response)
        return response

    async def get(self, url, headers=None, **kwargs):
        headers = headers or {}
        response = await self._client.get(url, headers=headers, **kwargs)
        self._format_log("GET", url, headers, None, response)
        return response

    async def put(self, url, json=None, headers=None, **kwargs):
        headers = headers or {}
        response = await self._client.put(url, json=json, headers=headers, **kwargs)
        self._format_log("PUT", url, headers, json, response)
        return response

    async def delete(self, url, headers=None, **kwargs):
        headers = headers or {}
        response = await self._client.delete(url, headers=headers, **kwargs)
        self._format_log("DELETE", url, headers, None, response)
        return response


@pytest_asyncio.fixture
async def client(request):
    """
    Provide a test client with a fresh database.

    Each test gets its own database instance, ensuring complete isolation.
    Request/response pairs are captured and attached to the HTML report.
    """
    import aiosqlite

    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")
    await db.executescript(SCHEMA_SQL)
    await db.executescript(SEED_SQL)
    await db.commit()

    async def override_get_db():
        """Yield the shared test database connection."""
        yield db

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        logging_client = LoggingClient(ac, request.node.nodeid)
        yield logging_client

    await db.close()
    app.dependency_overrides.clear()


def _build_html_report(logs):
    """Build HTML snippet showing request/response pairs for the test report."""
    html = '<div style="font-family: monospace; font-size: 12px; margin-top: 10px;">'
    html += f'<p style="font-weight:bold; margin-bottom:8px;">API Calls ({len(logs)}):</p>'
    for i, log in enumerate(logs, 1):
        req = log["request"]
        res = log["response"]
        status_color = "#4caf50" if res["status_code"] < 400 else "#f44336"

        req_body_html = ""
        if req["body"]:
            req_body_html = f'<pre style="margin:4px 0;background:#fff;padding:6px;border:1px solid #ddd;border-radius:3px;white-space:pre-wrap;">{json.dumps(req["body"], indent=2)}</pre>'

        res_body_html = f'<pre style="margin:4px 0;background:#fff;padding:6px;border:1px solid #ddd;border-radius:3px;white-space:pre-wrap;max-height:200px;overflow:auto;">{json.dumps(res["body"], indent=2)}</pre>'

        html += f'''
        <details open style="margin-bottom: 10px; border: 1px solid #ccc; border-radius: 6px; padding: 10px; background: #fafafa;">
            <summary style="cursor: pointer; font-weight: bold; font-size: 13px;">
                #{i} <span style="color: #1565c0;">{req["method"]}</span> <code>{req["url"]}</code>
                &rarr; <span style="background:{status_color}; color:white; padding:2px 8px; border-radius:3px; font-size:11px;">{res["status_code"]}</span>
            </summary>
            <div style="margin-top: 10px;">
                <div style="background: #e3f2fd; padding: 10px; border-radius: 4px; margin-bottom: 8px;">
                    <strong>REQUEST</strong><br>
                    <span style="color:#555;">Headers:</span> <code>{json.dumps(req["headers"])}</code><br>
                    {f'<span style="color:#555;">Body:</span>{req_body_html}' if req["body"] else '<span style="color:#999;">Body: (none)</span>'}
                </div>
                <div style="background: {"#e8f5e9" if res["status_code"] < 400 else "#ffebee"}; padding: 10px; border-radius: 4px;">
                    <strong>RESPONSE <span style="color:{status_color};">({res["status_code"]})</span></strong>
                    {res_body_html}
                </div>
            </div>
        </details>
        '''
    html += '</div>'
    return html


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Hook to attach request/response logs to the HTML report after each test."""
    outcome = yield
    report = outcome.get_result()

    # Attach on "call" phase (the actual test execution, not setup/teardown)
    if report.when == "call":
        node_id = item.nodeid
        logs = _test_api_logs.get(node_id, [])
        if logs:
            if not hasattr(report, "extras"):
                report.extras = []
            html_content = _build_html_report(logs)
            report.extras.append(pytest_html_extras.html(html_content))
            # Clean up
            del _test_api_logs[node_id]
