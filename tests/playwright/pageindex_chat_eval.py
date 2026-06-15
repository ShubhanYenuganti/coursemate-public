#!/usr/bin/env python3
"""
Playwright functional test for the CS 118 page-index chat flow.

Navigates (visibly) to the CS 118 course, opens the Chat tab via the floating
toolbar, deselects all materials, then re-selects only the 3 indexed lecture
PDFs.  Asks 10 routing/networking questions and records:
  - full latency via CDP (Chrome requestWillBeSent → loadingFinished), in seconds
  - per-event SSE timeline (loop_start, sources_found, tool_call, text, etc.)
  - full text of the chatbot reply (from the DOM after streaming completes)
  - path to a screenshot taken immediately after each answer

Output:
  tests/pageindex_eval/playwright_chat_eval_<YYYYMMDD_HHMMSS>.json
  tests/pageindex_eval/screenshots/q01.png … q10.png

Run:
    cd /Users/shubhan/OneShotCourseMate
    python tests/playwright/pageindex_chat_eval.py
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tests.playwright.dev_context import dev_app

# ── Questions ─────────────────────────────────────────────────────────────────
QUESTIONS = [
    "What is the difference between link-state and distance-vector routing algorithms?",
    "Walk me through how Dijkstra's algorithm computes shortest paths in a network step by step.",
    "What is the count-to-infinity problem in distance-vector routing, and how does split horizon address it?",
    "How does OSPF use link-state advertisements to build a complete topology map of the network?",
    "What are the main differences between OSPF and RIP in terms of convergence speed and scalability?",
    "What is BGP and why does the internet need a dedicated protocol for inter-domain routing?",
    "Explain the difference between iBGP and eBGP sessions and when each type is used.",
    "What BGP path attributes are evaluated when selecting a best route, and in what priority order?",
    "What is hot potato routing and why do ISPs prefer it over cold potato routing?",
    "How do autonomous systems and the AS_PATH attribute work together to prevent routing loops in BGP?",
]

UPLOAD_NAMES = [
    "Lecture-14-RoutingAlgorithm (1).pdf",
    "Lecture-15-RoutingProtocol.pdf",
    "Lecture-16-BGP.pdf",
]

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "pageindex_eval"
SCREENSHOTS_DIR = OUTPUT_DIR / "screenshots"


def main() -> None:
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []

    with dev_app(headless=False, slow_mo=250) as page:


        # ── 1. Find the CS 118 course ──────────────────────────────────────────
        courses: list[dict] = page.evaluate(
            """
            async () => {
                const r = await fetch('/api/course', { credentials: 'include' });
                const d = await r.json();
                return d.courses || [];
            }
            """
        )
        course = next((c for c in courses if "118" in c.get("title", "")), None)
        if not course:
            titles = [c.get("title", "") for c in courses]
            raise RuntimeError(f"No CS 118 course found. Available: {titles}")
        print(f"Course: {course['title']}  (id={course['id']})")

        # ── 2. Navigate to course page ─────────────────────────────────────────
        page.goto(f"http://localhost:5173/course/{course['id']}", wait_until="networkidle")

        # ── 3. Open Chat tab ───────────────────────────────────────────────────
        page.get_by_role("button").filter(has_text="💬").click()
        page.wait_for_load_state("networkidle")

        # ── 4. Wait for materials sidebar ─────────────────────────────────────
        page.wait_for_selector(".border-l-2", timeout=15_000)
        page.wait_for_timeout(400)

        # ── 5. Clear all material selections ──────────────────────────────────
        clear_btn = page.get_by_text("Clear", exact=True)
        if clear_btn.is_visible():
            clear_btn.click()
            page.wait_for_timeout(400)

        # ── 6. Select only the 3 uploaded lecture PDFs ────────────────────────
        for name in UPLOAD_NAMES:
            page.get_by_text(name, exact=True).locator("xpath=following-sibling::button").first.click()
            page.wait_for_timeout(250)

        print("Material selection set. Starting Q&A...\n")

        # ── JS fetch interceptor for SSE timing ───────────────────────────────
        # Injected after all page navigations so it isn't wiped by page.goto().
        # Wraps window.fetch to timestamp every SSE data frame on /api/chat.
        page.evaluate("""
        (() => {
            const orig = window.fetch.bind(window);
            window.__sseLog = [];
            window.__sseCapturePromise = Promise.resolve([]);
            window.fetch = async function(input, init) {
                const url = typeof input === 'string' ? input : (input && input.url) || '';
                const method = (init && init.method) || 'GET';
                if (!url.includes('/api/chat') || method !== 'POST') {
                    return orig(input, init);
                }
                window.__sseLog = [];
                const t0 = performance.now();
                const resp = await orig(input, init);

                // Only intercept SSE responses (stream_send), not JSON (chat creation)
                if (!(resp.headers.get('content-type') || '').includes('event-stream')) {
                    return resp;
                }

                // Tee the body: one stream for React, one for capture
                const [reactStream, captureStream] = resp.body.tee();

                // Store the capture Promise so Python can await it via page.evaluate()
                window.__sseCapturePromise = (async () => {
                    const reader = captureStream.getReader();
                    const decoder = new TextDecoder();
                    let buf = '';
                    try {
                        while (true) {
                            const {done, value} = await reader.read();
                            if (done) break;
                            buf += decoder.decode(value, {stream: true});
                            const parts = buf.split('\\n\\n');
                            buf = parts.pop();
                            for (const part of parts) {
                                if (!part.startsWith('data: ')) continue;
                                try {
                                    const d = JSON.parse(part.slice(6));
                                    window.__sseLog.push({type: d.type || 'unknown', t: performance.now() - t0});
                                } catch(_) {}
                            }
                        }
                    } catch(_) {}
                    return window.__sseLog;
                })();

                return new Response(reactStream, {status: resp.status, headers: resp.headers});
            };
        })();
        """)


        # ── 7. Ask each question in a fresh chat thread ───────────────────────
        for i, question in enumerate(QUESTIONS, start=1):
            print(f"Q{i:02d}: {question}")

            try:
                page.get_by_text("New chat", exact=True).click()
                page.wait_for_timeout(500)

                textarea = page.get_by_placeholder("Reply…")
                send_btn = page.locator("button.w-6.h-6")

                # Switch to GPT provider → GPT-4o mini
                page.keyboard.press("Escape")
                page.wait_for_timeout(100)
                page.locator("button.text-gray-400.text-xs").first.click()
                page.wait_for_timeout(300)
                page.locator("div.bg-gray-900").get_by_text("GPT", exact=True).click()
                page.wait_for_timeout(300)
                page.locator("button.text-gray-400.text-xs").last.click()
                page.wait_for_timeout(300)
                page.locator("div.bg-gray-900").get_by_text("GPT-4o mini", exact=True).click()
                page.wait_for_timeout(300)

                textarea.fill(question)
                page.wait_for_selector("button.w-6.h-6:not([disabled])", timeout=10_000)

                # Python wall-clock reference (send click → SSE body complete)
                t0 = time.time()
                with page.expect_response(
                    lambda r: "/api/chat" in r.url
                              and r.request.method == "POST"
                              and "event-stream" in (r.headers.get("content-type") or ""),
                    timeout=120_000,
                ) as resp_info:
                    send_btn.click()

                resp_info.value.body()
                py_latency = time.time() - t0

                # Await the capture Promise — page.evaluate() auto-awaits Promises
                sse_log = page.evaluate("window.__sseCapturePromise")

                # Build timeline with elapsed_ms and gap_ms between events
                timeline = []
                prev_t = 0.0
                for ev in sse_log:
                    elapsed_ms = round(ev["t"], 1)
                    gap_ms = round(ev["t"] - prev_t, 1)
                    timeline.append({
                        "type": ev["type"],
                        "elapsed_ms": elapsed_ms,
                        "gap_ms": gap_ms,
                    })
                    prev_t = ev["t"]

                # JS latency = time from fetch() call to last SSE event (ms → s)
                js_latency = round(sse_log[-1]["t"] / 1000, 3) if sse_log else None
                latency = js_latency if js_latency is not None else py_latency

                # Wait for React to render the assistant reply
                page.wait_for_selector("div.text-gray-700.leading-relaxed", timeout=120_000)
                page.wait_for_timeout(400)

                assistant_div = page.locator("div.text-gray-700.leading-relaxed").last
                response_text = assistant_div.inner_text()

                screenshot_path = SCREENSHOTS_DIR / f"q{i:02d}.png"
                page.screenshot(path=str(screenshot_path))

                preview = response_text[:120].replace("\n", " ").strip()
                print(f"  Latency (JS)    : {latency:.3f}s")
                print(f"  Latency (Python): {py_latency:.3f}s")
                if timeline:
                    for ev in timeline:
                        print(f"    +{ev['elapsed_ms']:7.1f}ms  [{ev['type']}]  (gap {ev['gap_ms']:.1f}ms)")
                print(f"  Preview : {preview}...\n")

                results.append({
                    "question_num": i,
                    "question": question,
                    "model": "gpt-4o-mini",
                    "latency_js_s": latency,
                    "latency_python_s": round(py_latency, 3),
                    "sse_timeline": timeline,
                    "response": response_text,
                    "screenshot": str(screenshot_path),
                })

            except Exception as exc:
                print(f"  ERROR (skipping): {exc}\n")
                screenshot_path = SCREENSHOTS_DIR / f"q{i:02d}_error.png"
                page.screenshot(path=str(screenshot_path))
                results.append({
                    "question_num": i,
                    "question": question,
                    "model": "gpt-4o-mini",
                    "error": str(exc),
                    "screenshot": str(screenshot_path),
                })

        # ── 8. Write results JSON ──────────────────────────────────────────────
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = OUTPUT_DIR / f"playwright_chat_eval_{ts}.json"
        results_file.write_text(json.dumps(results, indent=2))

        print(f"Results   : {results_file}")
        print(f"Screenshots: {SCREENSHOTS_DIR}/")

        page.wait_for_timeout(4_000)


if __name__ == "__main__":
    main()
