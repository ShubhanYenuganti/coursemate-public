"""
Verify that _ReplyStreamFilter strips <REPLY>/<META> tags from the SSE text stream.

Sends one question, captures every `text` chunk from the SSE response, and asserts
none of the chunks contain raw <REPLY>, </REPLY>, <META>, or </META> fragments.
"""
import sys
from playwright.sync_api import sync_playwright

URL = "http://localhost:5173"
QUESTION = "What is the difference between link-state and distance-vector routing?"

FORBIDDEN = ["<REPLY>", "</REPLY>", "<META>", "</META>"]


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=150)
        page = browser.new_page()
        page.goto(URL, wait_until="networkidle")

        # Select CS 118 course
        try:
            page.get_by_text("Com Sci 118", exact=False).first.click()
            page.wait_for_timeout(800)
        except Exception:
            print("Could not auto-select course — please select CS 118 manually.")
            page.wait_for_timeout(4000)

        # Inject fetch interceptor that captures full chunk text for text events
        page.evaluate("""
        (() => {
            const orig = window.fetch.bind(window);
            window.__chunks = [];
            window.__sseCapturePromise = Promise.resolve([]);
            window.fetch = async function(input, init) {
                const url = typeof input === 'string' ? input : (input && input.url) || '';
                const method = (init && init.method) || 'GET';
                if (!url.includes('/api/chat') || method !== 'POST') {
                    return orig(input, init);
                }
                window.__chunks = [];
                const resp = await orig(input, init);
                if (!(resp.headers.get('content-type') || '').includes('event-stream')) {
                    return resp;
                }
                const [reactStream, captureStream] = resp.body.tee();
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
                                    if (d.type === 'text' && d.chunk) {
                                        window.__chunks.push(d.chunk);
                                    }
                                } catch(_) {}
                            }
                        }
                    } catch(_) {}
                    return window.__chunks;
                })();
                return new Response(reactStream, {status: resp.status, headers: resp.headers});
            };
        })();
        """)

        # Select all 3 CS 118 materials
        for label in [
            "Lecture-14-RoutingAlgorithm",
            "Lecture-15-RoutingProtocol",
            "Lecture-16-BGP",
        ]:
            try:
                page.get_by_text(label, exact=False).first.click()
                page.wait_for_timeout(200)
            except Exception:
                pass

        # New chat thread
        try:
            page.get_by_text("New chat", exact=True).click()
            page.wait_for_timeout(500)
        except Exception:
            pass

        # Switch to GPT-4o mini
        try:
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
        except Exception as e:
            print(f"Model selector: {e} — continuing with default model")

        textarea = page.get_by_placeholder("Reply…")
        send_btn = page.locator("button.w-6.h-6")
        textarea.fill(QUESTION)
        page.wait_for_selector("button.w-6.h-6:not([disabled])", timeout=10_000)

        print(f"\nSending: {QUESTION}\nWaiting for response...\n")

        with page.expect_response(
            lambda r: "/api/chat" in r.url
                      and r.request.method == "POST"
                      and "event-stream" in (r.headers.get("content-type") or ""),
            timeout=120_000,
        ) as resp_info:
            send_btn.click()

        resp_info.value.body()
        chunks = page.evaluate("window.__sseCapturePromise")

        full_stream = "".join(chunks)
        print(f"Total text chunks received : {len(chunks)}")
        print(f"Total streamed characters  : {len(full_stream)}")
        print(f"First 200 chars of stream  : {repr(full_stream[:200])}")
        print()

        failures = [tag for tag in FORBIDDEN if tag in full_stream]
        if failures:
            print(f"FAIL — forbidden tags found in stream: {failures}")
            print("Offending context:")
            for tag in failures:
                idx = full_stream.find(tag)
                print(f"  {tag!r} at position {idx}: ...{full_stream[max(0,idx-20):idx+40]!r}...")
            browser.close()
            sys.exit(1)
        else:
            print("PASS — no <REPLY>, </REPLY>, <META>, or </META> tags in streamed chunks")

        browser.close()


if __name__ == "__main__":
    main()
