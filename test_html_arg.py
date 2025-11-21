from nicegui import ui

try:
    t = ui.html('<div>Test</div>', sanitize=False)
    print("Success with sanitize=False")
except Exception as e:
    print(f"Failed: {e}")

try:
    t = ui.html('<div>Test</div>')
    print("Success without sanitize")
except Exception as e:
    print(f"Failed without sanitize: {e}")
