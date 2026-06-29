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


class LoggingClient:
    """
    Wrapper around AsyncClient that logs request/response pairs.
    Attaches logs to the current test's extras for HTML report rendering.
    """

    def __init__(self, client: AsyncClient):
        self._client = client
        self.logs = []

    def _format_log(self, method, url, headers, body, response):
        """Format a request/response pair for report display."""
        entry = {
            "request": {
                "method": method,
                "url": str(url),
                "headers": {k: v for k, v in headers.items() if k.startswith("X-") or k == "Content-Type"},
                "body": body,
            },
            "response": {
                "status_code": response.status_code,
                "body": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
            },
        }
        self.logs.append(entry)
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
        logging_client = LoggingClient(ac)
        yield logging_client

        # After test completes, attach logs to the HTML report
        if logging_client.logs:
            if not hasattr(request.node, "api_logs"):
                request.node.api_logs = []
            request.node.api_logs = logging_client.logs

    await db.close()
    app.dependency_overrides.clear()


def _build_html_report(logs):
    """Build HTML snippet showing request/response pairs for the test report."""
    html = '<div style="font-family: monospace; font-size: 12px;">'
    for i, log in enumerate(logs, 1):
        req = log["request"]
        res = log["response"]
        status_color = "#4caf50" if res["status_code"] < 400 else "#f44336" if res["status_code"] >= 400 else "#ff9800"

        html += f'''
        <details {"open" if len(logs) <= 5 else ""} style="margin-bottom: 8px; border: 1px solid #ddd; border-radius: 4px; padding: 8px;">
            <summary style="cursor: pointer; font-weight: bold;">
                <span style="color: #1565c0;">{req["method"]}</span> {req["url"]}
                &rarr; <span style="color: {status_color}; font-weight: bold;">{res["status_code"]}</span>
            </summary>
            <div style="margin-top: 8px;">
                <div style="background: #e3f2fd; padding: 8px; border-radius: 4px; margin-bottom: 4px;">
                    <strong>Request:</strong><br>
                    Headers: {json.dumps(req["headers"])}<br>
                    {"Body: <pre style='margin:4px 0;background:#fff;padding:4px;'>" + json.dumps(req["body"], indent=2) + "</pre>" if req["body"] else "Body: (none)"}
                </div>
                <div style="background: #{"e8f5e9" if res["status_code"] < 400 else "ffebee"}; padding: 8px; border-radius: 4px;">
                    <strong>Response ({res["status_code"]}):</strong>
                    <pre style="margin:4px 0;background:#fff;padding:4px;overflow-x:auto;">{json.dumps(res["body"], indent=2)}</pre>
                </div>
            </div>
        </details>
        '''
    html += '</div>'
    return html


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Hook to attach request/response logs to the HTML report."""
    outcome = yield
    report = outcome.get_result()

    # Only attach on the "call" phase (not setup/teardown)
    if call.when == "call" and hasattr(item, "api_logs") and item.api_logs:
        if not hasattr(report, "extras"):
            report.extras = []
        html_content = _build_html_report(item.api_logs)
        report.extras.append(pytest_html_extras.html(html_content))
