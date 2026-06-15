"""
Context manager for running Playwright tests against the CourseMate local dev stack.

Both servers are started if not already listening:
  - dev_server.py  on port 3001  (Python API, DEV_BYPASS_AUTH=true)
  - npm run dev    on port 5173  (Vite frontend)

Usage:
    from tests.playwright.dev_context import dev_app

    with dev_app() as page:
        assert '/dashboard' in page.url
        page.goto('http://localhost:5173/dashboard')
        # interact with the live app
"""

import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # project root

API_PORT = 3001
VITE_PORT = 5173
VITE_URL = f"http://localhost:{VITE_PORT}"


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("localhost", port)) == 0


def _wait_for_port(port: int, timeout: float = 20.0, label: str = ""):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _port_open(port):
            return
        time.sleep(0.4)
    raise TimeoutError(f"{label or f'port {port}'} did not open within {timeout}s")


@contextmanager
def dev_app(headless: bool = True, slow_mo: int = 0, devtools: bool = False):
    """
    Ensure both dev servers are running, open a Playwright browser, navigate to
    the app root, wait for the auth bypass to complete and the app to redirect to
    /dashboard, then yield the authenticated page.

    DEV_BYPASS_AUTH=true is injected into the API server environment so OAuth is
    skipped.  The user is identified by DEV_USER_GOOGLE_ID from .env.

    Servers started by this context manager are terminated on exit.  If they are
    already running they are left untouched.
    """
    from playwright.sync_api import sync_playwright

    procs: list[subprocess.Popen] = []
    env = {**os.environ, "DEV_BYPASS_AUTH": "true"}

    if not _port_open(API_PORT):
        proc = subprocess.Popen(
            [sys.executable, "dev_server.py"],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        procs.append(proc)
        _wait_for_port(API_PORT, label="API dev server (port 3001)")

    if not _port_open(VITE_PORT):
        proc = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        procs.append(proc)
        _wait_for_port(VITE_PORT, label="Vite dev server (port 5173)")
        time.sleep(1.0)  # let Vite finish initial transform

    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=headless, slow_mo=slow_mo, devtools=devtools)
    context = browser.new_context()
    page = context.new_page()

    try:
        page.goto(VITE_URL, wait_until="networkidle")
        page.wait_for_url("**/dashboard", timeout=12_000)
        yield page
    finally:
        context.close()
        browser.close()
        playwright.stop()
        for proc in reversed(procs):
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
