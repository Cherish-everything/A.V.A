import time
from tools.screen import screen_context

print("Switch to the window you want to test...")
time.sleep(5)

for src in ("auto", "window_text", "ocr", "clipboard"):
    print(f"\n--- Testing source: '{src}' ---")
    t0 = time.perf_counter()
    r = screen_context(src)
    elapsed = time.perf_counter() - t0
    
    print(f"Time taken: {elapsed:.2f}s")
    
    if "error" in r:
        print(f"❌ Error: {r['error']}")
    elif "note" in r and "text" not in r and "selection" not in r and "clipboard" not in r:
        print(f"⚠️ Note: {r['note']}")
    else:
        # Print metadata if available
        if "app" in r:
            print(f"   App: {r.get('app')}")
        if "title" in r:
            print(f"   Title: {r.get('title')}")
        if "via" in r:
            print(f"   Extracted via: {r.get('via')}")
            
        # Print the actual processed content found
        content = r.get("selection") or r.get("text") or r.get("clipboard") or ""
        if content:
            print(f"   Processed Content ({len(content)} chars):")
            print("   " + "-" * 40)
            # Indent the content for clear readability
            for line in content.splitlines():
                print(f"     {line}")
            print("   " + "-" * 40)
        else:
            print("   (No text content returned)")