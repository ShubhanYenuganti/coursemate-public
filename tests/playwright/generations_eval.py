#!/usr/bin/env python3
"""
Playwright functional eval for Quiz, Flashcard, and Report generation.

Navigates (visibly) to the CS 118 course, opens the Generate tab (💡), and
selects the same 3 lecture PDFs used in the pageindex chat eval.  Triggers one
generation of each artifact type with the inputs below:

  Quiz:       topic "Routing Algorithms and BGP",  3 MCQ + 2 True/False
              → synchronous inline LLM call; full payload returned on confirm

  Flashcards: topic "BGP and Internet Routing",  10 cards, In-Depth depth
              → estimate creates draft; confirm queues to SQS.
                In dev mode (no FLASHCARDS_GENERATION_QUEUE_URL), the confirm
                call raises an error; the test falls back to invoking the lambda
                handler directly in-process so generation still completes.

  Report:     Study Guide template (default)
              → confirm spawns a background thread via _run_generation_locally
                (dev-mode fallback already baked into api/reports.py); poll
                get_generation_status until ready.

For each generation the test records:
  - wall-clock latency from confirm click to ready status
  - title + item count (questions / cards / sections)
  - a screenshot taken immediately after the viewer appears
  - pass/fail assertions

Output: tests/pageindex_eval/generations_eval_<YYYYMMDD_HHMMSS>.json

Run:
    cd /Users/shubhan/OneShotCourseMate
    python tests/playwright/generations_eval.py
"""

import importlib.util
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from tests.playwright.dev_context import dev_app  # noqa: E402

# ── Material names (same as pageindex chat eval) ──────────────────────────────

UPLOAD_NAMES = [
    "Lecture-14-RoutingAlgorithm (1).pdf",
    "Lecture-15-RoutingProtocol.pdf",
    "Lecture-16-BGP.pdf",
]

OUTPUT_DIR      = ROOT / "tests" / "pageindex_eval"
SCREENSHOTS_DIR = OUTPUT_DIR / "screenshots"

# ── Generation configs ────────────────────────────────────────────────────────

QUIZ_TOPIC = "Routing Algorithms and BGP"
QUIZ_MCQ   = 3   # number of MCQ questions
QUIZ_TF    = 2   # number of True/False questions

FLASHCARD_TOPIC = "BGP and Internet Routing"
FLASHCARD_COUNT = 10    # default in UI is 20; we click minus 10 times
FLASHCARD_DEPTH = "In-Depth"

REPORT_TEMPLATE = "Study Guide"   # already the default — click to ensure

POLL_INTERVAL = 4   # seconds between status polls
POLL_TIMEOUT  = 180 # max seconds to wait for async generation

# ── Low-level helpers ─────────────────────────────────────────────────────────

GENERATION_MODEL_PROVIDER = "openai"
GENERATION_MODEL_ID      = "gpt-4o-mini"

# Reports require multi-section nested JSON; gpt-4o-mini is unreliable for that format.
REPORT_MODEL_PROVIDER = "openai"
REPORT_MODEL_ID       = "gpt-4o"

# Button labels (lowercase substrings) whose click would navigate away — skip clicking.
SKIP_CLICK_LABELS = frozenset([
    "back to course", "materials", "chat", "generate",
])


def _fetch_json(page, url: str) -> dict:
    return page.evaluate(
        "async (u) => { const r = await fetch(u, {credentials:'include'}); return r.json(); }",
        url,
    )


def _set_model(page, prefix: str) -> None:
    """Force localStorage model selection to gpt-4o-mini before opening a generator tab."""
    page.evaluate(
        """([prefix, provider, modelId]) => {
            localStorage.setItem(prefix + '_selected_provider', provider);
            localStorage.setItem(prefix + '_selected_model_id', modelId);
        }""",
        [prefix, GENERATION_MODEL_PROVIDER, GENERATION_MODEL_ID],
    )


def _go_to_generate_tab(page, course_id: int) -> None:
    """Navigate to the course page and open the Generate (💡) tab."""
    page.goto(f"http://localhost:5173/course/{course_id}", wait_until="networkidle")
    page.get_by_role("button").filter(has_text="💡").click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)


def _audit_viewer(page, viewer_url: str, shot_path: Path) -> dict:
    """
    Navigate to a generation viewer, take a screenshot, then click every visible
    non-navigation button and classify it:
      ok       — triggered a network request or a DOM change
      stale    — no observable effect (no API call, no DOM change)
      disabled — button was disabled on page load
      error    — Playwright raised an exception while clicking
      navigation — skipped (would navigate away from the viewer)
    """
    page.goto(viewer_url, wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    page.screenshot(path=str(shot_path))

    # Snapshot button state before any clicking
    btn_snapshot = page.evaluate("""() =>
        Array.from(document.querySelectorAll('button')).map((b, idx) => {
            const text = (b.innerText || '').trim().replace(/\\s+/g, ' ');
            return {
                idx,
                text,
                ariaLabel: b.getAttribute('aria-label') || '',
                title:     b.getAttribute('title') || '',
                hasSvg:    b.querySelector('svg') !== null,
                disabled:  b.disabled,
                visible:   b.offsetWidth > 0 && b.offsetHeight > 0
                           && getComputedStyle(b).visibility !== 'hidden',
            };
        })
    """)

    js_errors: list[str] = []
    page.on("pageerror", lambda e: js_errors.append(str(e)))

    audit: list[dict] = []

    for btn in btn_snapshot:
        label = (btn["text"] or btn["ariaLabel"] or btn["title"]
                 or ("(icon-only)" if btn["hasSvg"] else "(unlabeled)"))
        lk = label.lower()
        is_nav = any(s in lk for s in SKIP_CLICK_LABELS)

        entry: dict = {"label": label, "disabled": btn["disabled"], "visible": btn["visible"]}

        if not btn["visible"]:
            entry["status"] = "hidden"
            audit.append(entry)
            continue

        if is_nav:
            entry["status"] = "navigation"
            audit.append(entry)
            continue

        if btn["disabled"]:
            entry["status"] = "disabled"
            audit.append(entry)
            continue

        # Restore fresh viewer state before each click test
        if not page.url.startswith(viewer_url.rstrip("/")):
            page.goto(viewer_url, wait_until="domcontentloaded")
            page.wait_for_timeout(800)

        reqs: list[str] = []
        rl = lambda r, _r=reqs: _r.append(r.url)
        page.on("request", rl)
        pre_len = page.evaluate("() => document.body.innerText.length")
        err_msg = None

        try:
            page.locator("button").nth(btn["idx"]).click(timeout=2000)
            page.wait_for_timeout(800)
        except Exception as exc:
            err_msg = str(exc)

        page.remove_listener("request", rl)

        if err_msg:
            entry.update({"status": "error", "error": err_msg})
        else:
            post_len = page.evaluate("() => document.body.innerText.length")
            api_reqs = [r for r in reqs if "/api/" in r]
            net = bool(api_reqs)
            dom = abs(post_len - pre_len) > 20
            entry.update({
                "status": "ok" if (net or dom) else "stale",
                "network_fired": net,
                "dom_changed": dom,
            })
            if api_reqs:
                entry["api_requests"] = api_reqs[:3]

        audit.append(entry)

        # Navigate back after any click that left the viewer
        if not page.url.startswith(viewer_url.rstrip("/")):
            page.goto(viewer_url, wait_until="domcontentloaded")
            page.wait_for_timeout(800)

    stale   = [b["label"] for b in audit if b.get("status") == "stale"]
    broken  = [b["label"] for b in audit if b.get("status") == "error"]
    visible = [b for b in audit if b.get("visible") and b.get("status") != "hidden"]

    print(f"  Viewer audit: {len(visible)} visible buttons  "
          f"{'⚠ stale: ' + str(stale) if stale else '✓ none stale'}  "
          f"{'✗ broken: ' + str(broken) if broken else ''}")

    return {
        "viewer_url":     viewer_url,
        "screenshot":     str(shot_path),
        "js_errors":      js_errors,
        "buttons":        audit,
        "stale_buttons":  stale,
        "broken_buttons": broken,
    }


def _select_materials(page) -> None:
    """Clear all source toggles then re-enable only the 3 lecture PDFs."""
    clear_btn = page.get_by_text("Clear", exact=True).first
    if clear_btn.is_visible():
        clear_btn.click()
        page.wait_for_timeout(400)
    for name in UPLOAD_NAMES:
        page.get_by_text(name, exact=True).locator("xpath=following-sibling::button").first.click()
        page.wait_for_timeout(250)


def _stepper(page, label_text: str, btn_idx: int, times: int = 1) -> None:
    """
    Click a Stepper +/- button adjacent to a <label> element.
    btn_idx 0 = minus (−), 1 = plus (+).
    Uses JS evaluate so it works regardless of Tailwind nesting depth.
    """
    for _ in range(times):
        page.locator("label").filter(has_text=label_text).evaluate(
            f"el => el.nextElementSibling.querySelectorAll('button')[{btn_idx}].click()"
        )
        page.wait_for_timeout(80)


def _list_generations(page, course_id: int, kind: str) -> list:
    data = _fetch_json(page, f"/api/{kind}?action=list_generations&course_id={course_id}")
    return data.get("generations") or []


def _get_gen_status(page, gen_id: int, kind: str, course_id: int) -> str | None:
    data = _fetch_json(
        page,
        f"/api/{kind}?action=get_generation_status&generation_id={gen_id}&course_id={course_id}",
    )
    return data.get("status")


def _poll_until_ready(page, gen_id: int, kind: str, course_id: int, timeout: int = POLL_TIMEOUT) -> dict:
    """Poll get_generation_status until 'ready', then fetch full payload."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = _get_gen_status(page, gen_id, kind, course_id)
        if status == "ready":
            return _fetch_json(
                page,
                f"/api/{kind}?action=get_generation&generation_id={gen_id}&course_id={course_id}",
            )
        if status == "failed":
            raise RuntimeError(f"{kind} generation {gen_id} failed")
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(f"{kind} generation {gen_id} not ready within {timeout}s")


_GENERATION_TABLES = {
    "quiz":       "quiz_generations",
    "flashcard":  "flashcard_generations",
    "flashcards": "flashcard_generations",
    "reports":    "report_generations",
}


def _reset_to_queued(kind: str, gen_id: int) -> None:
    """
    Reset a generation's status to 'queued' so the lambda handler will process it.

    Lambda handlers guard on `status == 'queued'` (or 'queued'/'generating' for
    reports) and refuse to re-process anything in another state.  When the API
    server marks the generation 'failed' (due to missing SQS queue URL), we must
    reset it before invoking the lambda.
    """
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
    from api.db import get_db as _main_get_db
    table = _GENERATION_TABLES[kind]
    with _main_get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE {table} SET status='queued', error=NULL WHERE id=%s", (gen_id,))
        cur.close()


def _invoke_lambda_sync(kind: str, gen_id: int) -> None:
    """
    Load and run the lambda handler's _process_generation in-process.
    Used as a dev-mode fallback when SQS is unavailable.

    Loads .env so DATABASE_URL and other secrets are available to the lambda's
    own db.py (the test process doesn't inherit them from dev_server.py).
    Pops 'db' from sys.modules after each call so successive invocations for
    different generator types don't share a cached db pool.
    """
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)  # don't clobber already-set vars

    lambda_dir = str(ROOT / "lambda" / f"{kind}_generate")
    # Prepend so `from db import get_db` inside the handler resolves to the
    # lambda-local db.py rather than any project-level db module.
    if lambda_dir not in sys.path:
        sys.path.insert(0, lambda_dir)
    try:
        # Force a fresh import of the lambda-local db.py; without this, a
        # previously cached 'db' module from a different lambda would be reused.
        sys.modules.pop("db", None)
        spec = importlib.util.spec_from_file_location(
            f"_lambda_handler_{kind}",
            ROOT / "lambda" / f"{kind}_generate" / "handler.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod._process_generation(gen_id)
    finally:
        sys.modules.pop("db", None)
        if lambda_dir in sys.path:
            sys.path.remove(lambda_dir)


# ── Per-generator eval functions ──────────────────────────────────────────────

def run_quiz(page, course_id: int) -> dict:
    """
    Inputs:
      Topic:  "Routing Algorithms and BGP"
      Counts: 3 MCQ + 2 True/False
    Strategy:
      action=estimate creates a draft + returns generation_id.
      Confirm fires action=generate which tries to enqueue to SQS; in dev (no
      QUIZ_GENERATION_QUEUE_URL) the server marks the generation 'failed'.
      We detect that and fall back to invoking the quiz lambda handler in-process.
    Expected output:
      5 questions (3 mcq, 2 tf) covering link-state vs distance-vector routing,
      OSPF vs RIP convergence, and BGP AS-path / path-attribute selection.
    """
    print("\n── Quiz ──────────────────────────────────────────────────────")

    _set_model(page, "quiz")
    _go_to_generate_tab(page, course_id)
    page.get_by_text("Custom Quizzes", exact=True).click()
    page.wait_for_timeout(400)

    _select_materials(page)

    # Topic
    page.get_by_placeholder("e.g. Reinforcement Learning, Neural Networks...").fill(QUIZ_TOPIC)
    page.wait_for_timeout(200)

    # Quiz.jsx initialises counts to mcq=10, tf=5, sa=3, la=2 — zero them out first.
    _stepper(page, "Multiple Choice (MCQ)",   0, times=15)  # minus → clamp at 0
    _stepper(page, "True / False Questions",  0, times=10)
    _stepper(page, "Short Answer Questions",  0, times=10)
    _stepper(page, "Long Answer Questions",   0, times=10)
    _stepper(page, "Multiple Choice (MCQ)",   1, times=QUIZ_MCQ)
    _stepper(page, "True / False Questions",  1, times=QUIZ_TF)

    # Intercept the estimate response to capture generation_id
    estimate_responses: list = []

    def _on_response(r):
        if "/api/quiz" in r.url and r.request.method == "POST":
            try:
                body = json.loads(r.request.post_data or "{}")
                if body.get("action") == "estimate":
                    estimate_responses.append(r)
            except Exception:
                pass

    page.on("response", _on_response)

    t_start = time.time()
    page.get_by_text("Generate Quiz", exact=True).click()
    page.wait_for_selector("text=Confirm generate", timeout=30_000)
    page.wait_for_timeout(400)
    page.remove_listener("response", _on_response)
    print(f"  Confirm modal open  (+{time.time()-t_start:.1f}s)")

    # Extract generation_id from estimate response
    gen_id = None
    for r in estimate_responses:
        try:
            data = r.json()
            if "generation_id" in data:
                gen_id = data["generation_id"]
                break
        except Exception:
            pass

    if gen_id is None:
        gens = _list_generations(page, course_id, "quiz")
        if gens:
            gen_id = gens[0]["generation_id"]

    assert gen_id, "quiz: could not capture draft generation_id"
    print(f"  Draft generation_id={gen_id}")

    # Confirm — queues to SQS in prod; fails in dev without queue URL
    page.get_by_text("Confirm generate", exact=True).click()
    page.wait_for_timeout(2_000)

    status = _get_gen_status(page, gen_id, "quiz", course_id)
    print(f"  Status after confirm: {status!r}")

    if status not in ("generating", "ready"):
        print("  → Reset to queued + invoking quiz lambda inline (dev fallback)")
        _reset_to_queued("quiz", gen_id)
        _invoke_lambda_sync("quiz", gen_id)

    gen_data = _poll_until_ready(page, gen_id, "quiz", course_id)
    latency  = time.time() - t_start

    title     = gen_data.get("title") or ""
    questions = gen_data.get("questions") or []
    q_counts: dict = {}
    for q in questions:
        q_counts[q["type"]] = q_counts.get(q["type"], 0) + 1

    print(f"  Done: {title!r}  {len(questions)} questions {q_counts}  ({latency:.1f}s)")

    shot = SCREENSHOTS_DIR / "gen_quiz.png"
    page.screenshot(path=str(shot))

    # Assertions
    assert gen_id,              "quiz: missing generation_id"
    assert title,               "quiz: missing title"
    assert len(questions) >= 3, f"quiz: too few questions ({len(questions)})"
    assert q_counts.get("mcq", 0) == QUIZ_MCQ, \
        f"quiz: expected {QUIZ_MCQ} MCQ, got {q_counts.get('mcq', 0)}"
    assert q_counts.get("tf",  0) == QUIZ_TF, \
        f"quiz: expected {QUIZ_TF} TF, got {q_counts.get('tf', 0)}"
    print("  ✓ assertions passed")

    viewer_url = f"http://localhost:5173/course/{course_id}/quiz/{gen_id}"
    viewer_shot = SCREENSHOTS_DIR / "viewer_quiz.png"
    viewer_audit = _audit_viewer(page, viewer_url, viewer_shot)

    return {
        "type":           "quiz",
        "generation_id":  gen_id,
        "title":          title,
        "model_id":       GENERATION_MODEL_ID,
        "question_count": len(questions),
        "question_types": q_counts,
        "latency_s":      round(latency, 2),
        "screenshot":     str(shot),
        "viewer_audit":   viewer_audit,
        "pass":           True,
    }


def run_flashcards(page, course_id: int) -> dict:
    """
    Inputs:
      Topic:      "BGP and Internet Routing"
      Card count: 10 (UI default is 20; click minus 10 times)
      Depth:      In-Depth
    Strategy:
      The estimate action creates a draft with a generation_id.
      We intercept the estimate response to capture that id.
      After confirm, if the generation stays at 'draft' (no SQS available in dev),
      we invoke the flashcards lambda handler directly in-process as a fallback.
    Expected output:
      10 cards with in-depth explanations on BGP attributes, iBGP/eBGP, AS paths.
    """
    print("\n── Flashcards ────────────────────────────────────────────────")

    _set_model(page, "flashcards")
    _go_to_generate_tab(page, course_id)
    page.get_by_text("Custom Flashcards", exact=True).click()
    page.wait_for_timeout(400)

    _select_materials(page)

    # Topic
    page.get_by_placeholder("e.g. Kinematics, Control Systems...").fill(FLASHCARD_TOPIC)
    page.wait_for_timeout(200)

    # Decrease card count from 20 → 10 (10 minus clicks)
    _stepper(page, "Number of Flashcards", 0, times=20 - FLASHCARD_COUNT)

    # Depth
    page.get_by_text(FLASHCARD_DEPTH, exact=True).click()
    page.wait_for_timeout(200)

    # Intercept the estimate response (fired when "Generate X Flashcards" is clicked).
    # The estimate action creates the draft record and returns generation_id.
    estimate_responses: list = []

    def _on_response(r):
        if "/api/flashcards" in r.url and r.request.method == "POST":
            try:
                body = json.loads(r.request.post_data or "{}")
                if body.get("action") == "estimate":
                    estimate_responses.append(r)
            except Exception:
                pass

    page.on("response", _on_response)

    t_start = time.time()
    page.get_by_text(f"Generate {FLASHCARD_COUNT} Flashcards", exact=True).click()
    page.wait_for_selector("text=Confirm generate", timeout=30_000)
    page.wait_for_timeout(400)
    page.remove_listener("response", _on_response)

    print(f"  Confirm modal open  (+{time.time()-t_start:.1f}s)")

    # Extract generation_id from the estimate response
    gen_id = None
    for r in estimate_responses:
        try:
            data = r.json()
            if "generation_id" in data:
                gen_id = data["generation_id"]
                break
        except Exception:
            pass

    if gen_id is None:
        # Fallback: find the newest draft in list_generations
        gens = _list_generations(page, course_id, "flashcards")
        if gens:
            gen_id = gens[0]["generation_id"]

    assert gen_id, "flashcards: could not capture draft generation_id"
    print(f"  Draft generation_id={gen_id}")

    # Click Confirm generate (queues to SQS in prod; may fail in dev without queue URL)
    page.get_by_text("Confirm generate", exact=True).click()
    page.wait_for_timeout(2_000)

    # Check whether the generation started processing
    status = _get_gen_status(page, gen_id, "flashcards", course_id)
    print(f"  Status after confirm: {status!r}")

    if status not in ("generating", "ready"):
        # Dev fallback: SQS not available — reset status then invoke lambda directly
        print("  → Reset to queued + invoking flashcards lambda inline (dev fallback)")
        _reset_to_queued("flashcards", gen_id)
        _invoke_lambda_sync("flashcards", gen_id)

    gen_data = _poll_until_ready(page, gen_id, "flashcards", course_id)
    latency  = time.time() - t_start

    title = gen_data.get("title") or ""
    cards = gen_data.get("cards") or []
    print(f"  Done: {title!r}  {len(cards)} cards  ({latency:.1f}s)")

    shot = SCREENSHOTS_DIR / "gen_flashcards.png"
    page.screenshot(path=str(shot))

    assert title,             "flashcards: missing title"
    assert len(cards) >= 5,   f"flashcards: too few cards ({len(cards)})"
    # API viewer payload uses "front"/"back" (not the DB column names front_text/back_text)
    assert all(c.get("front") and c.get("back") for c in cards), \
        "flashcards: some cards missing front/back text"
    print("  ✓ assertions passed")

    viewer_url = f"http://localhost:5173/course/{course_id}/flashcards/{gen_id}"
    viewer_shot = SCREENSHOTS_DIR / "viewer_flashcards.png"
    viewer_audit = _audit_viewer(page, viewer_url, viewer_shot)

    return {
        "type":          "flashcards",
        "generation_id": gen_id,
        "title":         title,
        "model_id":      GENERATION_MODEL_ID,
        "card_count":    len(cards),
        "latency_s":     round(latency, 2),
        "screenshot":    str(shot),
        "viewer_audit":  viewer_audit,
        "pass":          True,
    }


def run_report(page, course_id: int) -> dict:
    """
    Inputs:
      Template: Study Guide (default — selected explicitly for reliability)
    Strategy:
      action=estimate creates a draft + returns generation_id.
      Confirm fires action=confirm which tries to enqueue to SQS; in dev (no
      REPORTS_GENERATION_QUEUE_URL) it falls back to _run_generation_locally which
      starts a background thread — but that thread can be unreliable in dev.
      We detect a non-generating status and fall back to invoking the reports
      lambda handler directly in-process for reliability.
    Expected output:
      A study guide with 3–8 sections covering link-state routing, BGP path
      selection, hot potato routing, and AS-path loop prevention.
    """
    print("\n── Report ────────────────────────────────────────────────────")

    # Use gpt-4o for reports: gpt-4o-mini produces invalid JSON for the nested
    # multi-section study guide format without response_format=json_object.
    page.evaluate(
        """([prefix, provider, modelId]) => {
            localStorage.setItem(prefix + '_selected_provider', provider);
            localStorage.setItem(prefix + '_selected_model_id', modelId);
        }""",
        ["reports", REPORT_MODEL_PROVIDER, REPORT_MODEL_ID],
    )
    _go_to_generate_tab(page, course_id)
    page.get_by_text("Custom Reports", exact=True).click()
    page.wait_for_timeout(400)

    _select_materials(page)

    # Click "Study Guide" to ensure it's selected (it's the default but click anyway)
    page.get_by_text(REPORT_TEMPLATE, exact=True).first.click()
    page.wait_for_timeout(200)

    # Intercept estimate response to capture generation_id
    estimate_responses: list = []

    def _on_response(r):
        if "/api/reports" in r.url and r.request.method == "POST":
            try:
                body = json.loads(r.request.post_data or "{}")
                if body.get("action") == "estimate":
                    estimate_responses.append(r)
            except Exception:
                pass

    page.on("response", _on_response)

    t_start = time.time()
    page.get_by_text(f"Generate {REPORT_TEMPLATE}", exact=True).click()
    page.wait_for_selector("text=Confirm generate", timeout=30_000)
    page.wait_for_timeout(400)
    page.remove_listener("response", _on_response)

    print(f"  Confirm modal open  (+{time.time()-t_start:.1f}s)")

    gen_id = None
    for r in estimate_responses:
        try:
            data = r.json()
            if "generation_id" in data:
                gen_id = data["generation_id"]
                break
        except Exception:
            pass

    if gen_id is None:
        gens = _list_generations(page, course_id, "reports")
        if gens:
            gen_id = gens[0]["generation_id"]

    assert gen_id, "reports: could not capture draft generation_id"
    print(f"  Draft generation_id={gen_id}")

    # In dev, _run_generation_locally starts a background thread that acquires a
    # PostgreSQL advisory lock for the duration of the LLM call.  If that call
    # takes a long time, our test-side lambda invocation can't claim the lock and
    # silently skips the generation.  Fix: invoke the lambda synchronously HERE,
    # before clicking Confirm, so the background thread that follows will see
    # status='ready' and exit immediately without competing.
    print("  → Invoking reports lambda inline before confirm (dev fallback)")
    _reset_to_queued("reports", gen_id)
    _invoke_lambda_sync("reports", gen_id)

    # Confirm — background thread will start but immediately see status='ready' and skip.
    page.get_by_text("Confirm generate", exact=True).click()
    page.wait_for_timeout(1_000)

    print("  Polling for ready status…")
    gen_data = _poll_until_ready(page, gen_id, "reports", course_id)
    latency  = time.time() - t_start

    title    = gen_data.get("title") or ""
    sections = gen_data.get("sections") or []
    print(f"  Done: {title!r}  {len(sections)} sections  ({latency:.1f}s)")

    shot = SCREENSHOTS_DIR / "gen_report.png"
    page.screenshot(path=str(shot))

    assert title,               "report: missing title"
    assert len(sections) >= 2,  f"report: too few sections ({len(sections)})"
    print("  ✓ assertions passed")

    viewer_url = f"http://localhost:5173/course/{course_id}/reports/{gen_id}"
    viewer_shot = SCREENSHOTS_DIR / "viewer_report.png"
    viewer_audit = _audit_viewer(page, viewer_url, viewer_shot)

    return {
        "type":          "report",
        "generation_id": gen_id,
        "title":         title,
        "model_id":      REPORT_MODEL_ID,
        "section_count": len(sections),
        "latency_s":     round(latency, 2),
        "screenshot":    str(shot),
        "viewer_audit":  viewer_audit,
        "pass":          True,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []

    with dev_app(headless=True) as page:

        # ── 1. Find CS 118 course ──────────────────────────────────────────
        raw    = _fetch_json(page, "/api/course")
        courses = raw if isinstance(raw, list) else raw.get("courses", [])
        course  = next((c for c in courses if "118" in c.get("title", "")), None)
        if not course:
            raise RuntimeError(
                f"CS 118 course not found. Available: {[c['title'] for c in courses]}"
            )
        print(f"Course: {course['title']}  (id={course['id']})")

        course_id = course["id"]

        # ── 4. Run each generator eval ─────────────────────────────────────
        for fn in [run_quiz, run_flashcards, run_report]:
            label = fn.__name__.replace("run_", "")
            try:
                result = fn(page, course_id)
                results.append(result)
            except Exception as exc:
                import traceback
                traceback.print_exc()
                results.append({"type": label, "pass": False, "error": str(exc)})
                print(f"  ERROR in {label}: {exc}")

    # ── 5. Write output ────────────────────────────────────────────────────
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUTPUT_DIR / f"generations_eval_{ts}.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nResults → {out_path}")

    # ── 6. Summary ─────────────────────────────────────────────────────────
    print("\n── Summary ───────────────────────────────────────────────────────")
    all_pass = True
    for r in results:
        t = r.get("type", "?")
        if r.get("pass"):
            print(f"  {t:12s} PASS  {r.get('title', '')!r}  {r.get('latency_s', '?')}s")
        else:
            all_pass = False
            print(f"  {t:12s} FAIL  {r.get('error', '')}")

    print("\n── Viewer button audit ───────────────────────────────────────────")
    any_issues = False
    for r in results:
        audit = r.get("viewer_audit")
        if not audit:
            continue
        t = r.get("type", "?")
        stale   = audit.get("stale_buttons", [])
        broken  = audit.get("broken_buttons", [])
        js_errs = audit.get("js_errors", [])
        if stale or broken or js_errs:
            any_issues = True
            print(f"  {t:12s}  stale={stale}  broken={broken}  js_errors={js_errs}")
        else:
            visible_ok = [b for b in audit.get("buttons", []) if b.get("status") == "ok"]
            print(f"  {t:12s}  ✓ all {len(visible_ok)} action buttons ok")
    if not any_issues:
        print("  No stale or broken buttons found.")

    if all_pass:
        print("\nAll generators passed.")
    else:
        print("\nSome generators failed — see output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
