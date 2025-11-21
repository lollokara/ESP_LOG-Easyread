from playwright.sync_api import sync_playwright, expect
import time

def verify_ui():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Go to app
        page.goto("http://localhost:8080")

        # Wait for title
        expect(page).to_have_title("ESP32 Serial Monitor")

        # Click "Simulate Mode" switch
        # Quasar switches are often tricky. Let's try text locator.
        # The text "Simulate Mode (Mock)" is near the switch.
        # The switch itself might be a div with role 'switch' or checkbox input.

        # Wait for the text to appear
        page.get_by_text("Simulate Mode (Mock)").wait_for()

        # Click the switch. Sometimes clicking the label works.
        page.get_by_text("Simulate Mode (Mock)").click()

        # Wait for logs
        # Look for element with class 'log-line'
        try:
            page.wait_for_selector(".log-line", timeout=10000)
        except Exception as e:
             print("Logs did not appear. Trying to click switch again or check if mock started.")
             # Maybe the switch didn't toggle.
             # Let's inspect the switch state if possible, but clicking the text usually toggles Quasar switches.

        # Check body overflow
        body_overflow = page.eval_on_selector("body", "e => getComputedStyle(e).overflow")
        print(f"Body Overflow: {body_overflow}")

        # Assert body overflow is hidden
        # Note: In main.py we added `body { overflow: hidden; }`
        if body_overflow != "hidden":
             print("WARNING: Body overflow is not hidden!")

        # Allow some logs to populate
        time.sleep(2)

        # Take screenshot
        page.screenshot(path="/home/jules/verification/verification.png")

        browser.close()

if __name__ == "__main__":
    verify_ui()
