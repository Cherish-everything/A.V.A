import time
from tools.screen import screen_context

print("Switch to window")
time.sleep(5)
for src in ("auto", "window_text", "ocr", "clipboard"):
    t0 = time.perf_counter()
    r = screen_context(src)
    print(src, f"{time.perf_counter() - t0: .2f}s", {k: (v[:80] if isinstance(v, str) else v) for k, v in r.items()})