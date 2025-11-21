from nicegui import ui, app, Client
import asyncio
from serial_manager import SerialManager
from log_parser import LogEntry
import threading
import time
import random
import traceback
import json
import datetime
from collections import deque

# Global backend state (shared across clients)
serial_manager = None
mock_mode = False
mock_thread = None

# Persistence State (Survives Reloads)
class AppState:
    def __init__(self):
        self.port = None
        self.baud = 115200
        # Level defaults to all specific levels selected (explicit list)
        self.filter_level = ["V", "D", "I", "W", "E", "U"]
        self.filter_file = ["ALL"]
        self.filter_function = ["ALL"] # Changed to list
        self.auto_scroll = True
        self.auto_reconnect = False
        self.save_to_file = False
        self.mock_mode = False
        self.realtime_timestamp = False

app_state = AppState()

# We store all logs in a global list for persistence across page reloads
global_lock = threading.Lock()
global_logs = []
unique_files = {"ALL"}
unique_functions = {"ALL"}

def handle_log(entry: LogEntry):
    """
    Callback from SerialManager.
    """
    global global_logs, unique_files, unique_functions
    with global_lock:
        global_logs.append(entry)

        if entry.file != "UNDEFINED":
            unique_files.add(entry.file)
        if entry.function != "UNDEFINED":
            unique_functions.add(entry.function)

# Mock Generator
def mock_log_generator():
    """Generates fake logs for testing."""
    files = ["main.cpp", "wifi.cpp", "sensor.cpp", "preferences.cpp", "display.cpp"]
    functions = ["setup", "loop", "connect", "read_data", "update_ui", "save_config", "init"]
    levels = ["V", "D", "I", "W", "E"]
    messages = [
        "Starting up...",
        "Connection failed",
        "Data received: 0xFE",
        "Battery level: 85%",
        "NVS Error: Key not found",
        "WiFi connected, IP: 192.168.1.123",
        "Rendering frame",
        "Watchdog reset"
    ]

    counter = 0
    while mock_mode:
        timestamp = str(int(time.time() * 1000) % 100000)
        level = random.choice(levels)
        file = random.choice(files)
        line = random.randint(10, 500)
        function = random.choice(functions)
        msg = random.choice(messages)

        # 10% chance of non-standard log
        if random.random() < 0.1:
            raw = f"Standard output message {counter}"
        else:
            raw = f"[{timestamp}][{level}][{file}:{line}] {function}(): {msg} {counter}"

        entry = LogEntry(
            timestamp=timestamp if raw.startswith("[") else "UNDEFINED",
            level=level if raw.startswith("[") else "U",
            file=file if raw.startswith("[") else "UNDEFINED",
            function=function if raw.startswith("[") else "UNDEFINED",
            message=msg if raw.startswith("[") else raw,
            original=raw
        )

        handle_log(entry)
        if serial_manager and serial_manager.save_to_file and serial_manager.file_handle:
             serial_manager.file_handle.write(entry.to_file_format() + "\n")
             serial_manager.file_handle.flush()

        counter += 1
        time.sleep(random.uniform(0.05, 0.5))

class LogViewer:
    def __init__(self):
        # Load initial state from global AppState
        self.filter_level = app_state.filter_level
        self.filter_file = app_state.filter_file
        self.filter_function = app_state.filter_function
        self.auto_scroll = app_state.auto_scroll

        self.last_processed_index = 0

        # Track HTML strings for rolling window
        # We keep this in sync with the DOM to handle refreshes
        self.html_logs = deque(maxlen=2000)

        # UI References
        self.log_container_id = f"log-container-{id(self)}" # Unique ID for this viewer
        self.log_container = None
        self.scroll_area = None
        self.file_select = None
        self.function_select = None
        self.level_select = None
        self.port_select = None
        self.baud_select = None
        self.connect_switch = None

    def matches_filter(self, entry: LogEntry) -> bool:
        # Level Logic: Standard multi-select (no ALL token needed as list is static)
        if entry.level not in self.filter_level:
            return False

        # File Logic: Dynamic list with "ALL" token
        if "ALL" not in self.filter_file:
            if entry.file not in self.filter_file:
                return False

        # Function Logic: Dynamic list with "ALL" token
        if "ALL" not in self.filter_function:
            if entry.function not in self.filter_function:
                return False

        return True

    async def update_loop(self):
        """
        Called periodically by ui.timer.
        Checks for new logs in global_logs and updates the UI.
        """
        global global_logs

        # Check if client is still connected to avoid RuntimeError
        try:
            # Simple keep-alive check.
            if not self.log_container or not self.log_container.client.has_socket_connection:
                 return
        except Exception:
            return

        try:
            # Thread-safe access to global logs
            with global_lock:
                current_len = len(global_logs)

                # If we have new logs
                if current_len > self.last_processed_index:
                    new_entries = global_logs[self.last_processed_index:current_len]
                    self.last_processed_index = current_len

                    # Update Dropdowns if needed
                    # Now protected by lock, so safe to iterate
                    if self.file_select:
                        current_opts = set(self.file_select.options)
                        if len(unique_files) > len(current_opts):
                            self.file_select.options = sorted(list(unique_files))
                            self.file_select.update()

                    if self.function_select:
                        current_opts = set(self.function_select.options)
                        if len(unique_functions) > len(current_opts):
                            self.function_select.options = sorted(list(unique_functions))
                            self.function_select.update()

            # Filter new entries (outside lock if possible, but we copied the list logic above)
            # Note: 'new_entries' is a slice (new list), so it's safe to use outside lock.
            if 'new_entries' in locals() and new_entries:
                matching_entries = [e for e in new_entries if self.matches_filter(e)]

                if matching_entries:
                    new_html_chunk = []
                    for entry in matching_entries:
                        html = self.format_log_html(entry)
                        self.html_logs.append(html)
                        new_html_chunk.append(html)

                    # JS Append
                    if new_html_chunk:
                        joined_html = "".join(new_html_chunk)
                        # Use json.dumps to safely escape the HTML string for JS
                        js_html = json.dumps(joined_html)
                        cmd = f'window.logManager.append("{self.log_container_id}", {js_html}, 2000, {str(self.auto_scroll).lower()})'
                        ui.run_javascript(cmd)

        except Exception as e:
            print("Error in update_loop:")
            traceback.print_exc()

    def refresh_log_view(self):
        """Clears and rebuilds the log view based on current filters."""
        if not self.log_container:
            return

        self.html_logs.clear()

        # Filter all global logs with lock
        with global_lock:
            current_len = len(global_logs)
            matching = [l for l in global_logs if self.matches_filter(l)]
            self.last_processed_index = current_len

        # Apply rolling window (start with the last 2000)
        initial_load = matching[-2000:]

        for entry in initial_load:
            self.html_logs.append(self.format_log_html(entry))

        joined_html = "".join(self.html_logs)
        js_html = json.dumps(joined_html)
        # For full refresh, we replace content
        cmd = f'window.logManager.setContent("{self.log_container_id}", {js_html})'
        ui.run_javascript(cmd)

        if self.auto_scroll and self.scroll_area:
             self.scroll_area.scroll_to(percent=1.0)

    def format_log_html(self, entry: LogEntry) -> str:
        # Timestamp logic
        if app_state.realtime_timestamp:
            # Format: MM:SS:mmm
            dt = datetime.datetime.fromtimestamp(entry.arrival_time)
            ts_str = dt.strftime("%M:%S:%f")[:-3]
        else:
            ts_str = entry.timestamp

        # Color coding
        color_class = "text-gray-800"
        if entry.level == "E": color_class = "text-red-600 font-bold"
        elif entry.level == "W": color_class = "text-yellow-600"
        elif entry.level == "I": color_class = "text-green-600"
        elif entry.level == "D": color_class = "text-blue-600"
        elif entry.level == "V": color_class = "text-gray-500"

        # Construct HTML string row
        file_str = f"[{entry.file}]" if entry.file != "UNDEFINED" else ""
        func_str = f"{entry.function}()" if entry.function != "UNDEFINED" else ""

        # Sanitize message for HTML (basic)
        safe_msg = entry.message.replace("<", "&lt;").replace(">", "&gt;")

        return f"""
        <div class="w-full flex gap-1 font-mono text-sm items-start no-wrap hover:bg-gray-100 select-text">
            <div class="text-gray-400 w-20 shrink-0">[{ts_str}]</div>
            <div class="{color_class} w-8 shrink-0">[{entry.level}]</div>
            <div class="text-purple-600 w-48 shrink-0 truncate" title="{entry.file}">{file_str}</div>
            <div class="text-orange-600 w-40 shrink-0 truncate" title="{entry.function}">{func_str}</div>
            <div class="{color_class} grow break-all select-text">{safe_msg}</div>
        </div>
        """

    def _handle_smart_all_selection(self, new_val, current_val, ui_element):
        """Helper for File/Function filters to manage 'ALL' vs Specifics."""
        result = new_val
        if not new_val:
            # Empty -> Default to ALL
            result = ["ALL"]
            ui_element.value = ["ALL"]
        else:
            # If "ALL" was present and we added something else, remove "ALL"
            if "ALL" in current_val and len(new_val) > len(current_val):
                result = [x for x in new_val if x != "ALL"]
                ui_element.value = result
            # If something else was present and we selected "ALL", remove others
            elif "ALL" not in current_val and "ALL" in new_val:
                result = ["ALL"]
                ui_element.value = result
        return result

    def on_file_filter_change(self, e):
        self.filter_file = self._handle_smart_all_selection(e.value, self.filter_file, self.file_select)
        app_state.filter_file = self.filter_file
        self.refresh_log_view()

    def on_function_filter_change(self, e):
        self.filter_function = self._handle_smart_all_selection(e.value, self.filter_function, self.function_select)
        app_state.filter_function = self.filter_function
        self.refresh_log_view()

    def on_level_filter_change(self, e):
        # Level is simple multi-select
        self.filter_level = e.value
        app_state.filter_level = self.filter_level
        self.refresh_log_view()

    def on_autoscroll_change(self, e):
        self.auto_scroll = e.value
        app_state.auto_scroll = e.value
        if self.auto_scroll and self.scroll_area:
            self.scroll_area.scroll_to(percent=1.0)

    def on_clear_logs(self):
        global global_logs, unique_files, unique_functions
        with global_lock:
            global_logs.clear()

        self.html_logs.clear()
        if self.log_container_id:
             cmd = f'window.logManager.setContent("{self.log_container_id}", "")'
             ui.run_javascript(cmd)
        self.last_processed_index = 0

    def on_connect_toggle(self, e):
        port = self.port_select.value
        baud = int(self.baud_select.value)
        if e.value: # Connecting
            app_state.port = port
            app_state.baud = baud
            if serial_manager.connect(port, baud):
                 ui.notify(f"Connected to {port}")
            else:
                 ui.notify(f"Failed to connect to {port}", type='negative')
                 self.connect_switch.value = False
        else: # Disconnecting
            serial_manager.disconnect()
            ui.notify("Disconnected")

    def on_refresh_ports(self):
        self.port_select.options = serial_manager.list_ports()
        self.port_select.update()
        ui.notify("Ports refreshed")

    def on_mock_toggle(self, e):
        global mock_mode, mock_thread
        mock_mode = e.value
        app_state.mock_mode = e.value
        if mock_mode:
            mock_thread = threading.Thread(target=mock_log_generator, daemon=True)
            mock_thread.start()
            ui.notify("Mock Mode Started")
            if self.connect_switch:
                self.connect_switch.disable()
        else:
            ui.notify("Mock Mode Stopped")
            if self.connect_switch:
                self.connect_switch.enable()

    def build_ui(self):
        # Header / Sidebar
        with ui.left_drawer(value=True).classes('bg-slate-100 q-pa-md') as drawer:
            ui.markdown("### ESP32 Serial Monitor")

            # Connection Controls
            ui.separator()
            ui.label("Connection").classes('text-lg font-bold mt-2')

            ports = serial_manager.list_ports()
            current_port = app_state.port if app_state.port in ports else (ports[0] if ports else None)

            with ui.row().classes('w-full'):
                self.port_select = ui.select(
                    options=ports,
                    value=current_port,
                    label="Port"
                ).classes('w-full')

            ui.button("Refresh Ports", on_click=self.on_refresh_ports).classes('w-full mb-2')

            self.baud_select = ui.select(
                options=[9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600],
                value=app_state.baud,
                label="Baud Rate"
            ).classes('w-full')

            # Check if backend is connected?
            is_connected = serial_manager.is_connected if serial_manager else False
            self.connect_switch = ui.switch("Connect", value=is_connected, on_change=self.on_connect_toggle).classes('w-full')
            if mock_mode: self.connect_switch.disable()

            # Sync these with serial_manager state ideally, but for now local
            ui.checkbox("Auto-reconnect", value=serial_manager.auto_reconnect if serial_manager else False, on_change=lambda e: serial_manager.set_auto_reconnect(e.value))

            # File Saving
            ui.separator().classes('my-2')
            ui.label("Logging").classes('text-lg font-bold')
            ui.checkbox("Save to File", value=serial_manager.save_to_file if serial_manager else False, on_change=lambda e: serial_manager.set_save_to_file(e.value))

            # Mock
            ui.separator().classes('my-2')
            ui.switch("Simulate Mode (Mock)", value=mock_mode, on_change=self.on_mock_toggle)

            # Filters
            ui.separator().classes('my-2')
            ui.label("Filters").classes('text-lg font-bold')

            # Level Filter with Clear/Select All
            with ui.row().classes('w-full items-center no-wrap'):
                self.level_select = ui.select(
                    options=["V", "D", "I", "W", "E", "U"],
                    value=app_state.filter_level,
                    label="Level",
                    multiple=True,
                    on_change=self.on_level_filter_change
                ).classes('grow').props('use-chips')
                # Helper buttons for Level
                with ui.button(icon='select_all', on_click=lambda: self.level_select.set_value(["V", "D", "I", "W", "E", "U"])).props('flat dense round').tooltip("Select All"):
                    pass
                with ui.button(icon='clear', on_click=lambda: self.level_select.set_value([])).props('flat dense round color=red').tooltip("Clear Selection"):
                    pass

            # File Filter
            self.file_select = ui.select(
                options=sorted(list(unique_files)),
                value=app_state.filter_file,
                label="File",
                multiple=True,
                on_change=self.on_file_filter_change
            ).classes('w-full').props('use-chips')

            # Function Filter
            self.function_select = ui.select(
                options=sorted(list(unique_functions)),
                value=app_state.filter_function,
                label="Function",
                multiple=True,
                on_change=self.on_function_filter_change
            ).classes('w-full').props('use-chips')

            ui.separator().classes('my-4')
            ui.button("Clear Logs", on_click=self.on_clear_logs, color='red').classes('w-full')

        # JS Injection for performance & Selection fix
        ui.add_head_html("""
        <style>
        .select-text {
            -webkit-user-select: text !important;
            user-select: text !important;
        }
        </style>
        <script>
        window.logManager = {
            append: function(id, html, maxLines, autoScroll) {
                const el = document.getElementById(id);
                if (!el) return;
                el.insertAdjacentHTML('beforeend', html);
                // Remove old children if needed
                // Note: childElementCount is fast.
                // Removing from start is O(N) in DOM, but for 2000 items it's instant.
                while (el.childElementCount > maxLines) {
                    el.firstElementChild.remove();
                }
                if (autoScroll) {
                    const scrollArea = el.closest('.q-scrollarea__container')
                                     || el.closest('.q-scrollarea__content')
                                     || el.parentElement;
                    // Find the scrolling element. NiceGUI q-scrollarea uses internal 'scroll' div.
                    // We can try to find the .q-scrollarea__container which has scrollTop.
                    // Actually, q-scrollarea manages scroll internally.
                    // But usually setting scrollTop on the content wrapper works if overflow is set.
                    // Let's try finding the scroll target that Quasar uses.
                    const scrollTarget = el.closest('.q-scrollarea').querySelector('.q-scrollarea__container');
                    if (scrollTarget) {
                        scrollTarget.scrollTop = scrollTarget.scrollHeight;
                    }
                }
            },
            setContent: function(id, html) {
                const el = document.getElementById(id);
                if (el) el.innerHTML = html;
            }
        }
        </script>
        """)

        # Main Content (Flex Column with constrained height)
        with ui.column().classes('w-full h-screen p-0 overflow-hidden no-wrap'):
            # Toolbar (Fixed height)
            with ui.row().classes('w-full bg-white p-2 border-b items-center shrink-0'):
                ui.button(icon='menu', on_click=drawer.toggle).props('flat round dense')
                ui.label("Log Output").classes('text-xl ml-2')
                ui.space()
                ui.switch("Time", value=app_state.realtime_timestamp, on_change=lambda e: setattr(app_state, 'realtime_timestamp', e.value)).tooltip("Real-time Timestamp")
                ui.switch("Scroll", value=app_state.auto_scroll, on_change=self.on_autoscroll_change).tooltip("Auto-scroll")

            # Log Area (Grow to fill remaining space)
            self.scroll_area = ui.scroll_area().classes('w-full grow bg-gray-50 p-4 select-text')
            with self.scroll_area:
                # We use a div container with a specific ID for JS manipulation
                self.log_container = ui.element('div').props(f'id="{self.log_container_id}"').classes('w-full flex flex-col select-text')

        # Start the update timer for this client (Slightly slower to batch updates)
        ui.timer(0.2, self.update_loop)

@ui.page('/')
def main_page(client: Client):
    global serial_manager
    if serial_manager is None:
        serial_manager = SerialManager(on_log_received=handle_log)

    viewer = LogViewer()
    viewer.build_ui()

if __name__ in {"__main__", "__mp_main__"}:
    # Check if running as a bundled app or script
    # If bundled (sys.frozen), run in native mode
    # native=True requires pywebview to be installed
    import sys
    is_bundled = getattr(sys, 'frozen', False)

    # We use native mode if bundled, or if explicitly requested via args (optional)
    # For development, reload=False is safer with native mode usually.

    # Note: On Mac M1, native=True uses the system's webview (WebKit).
    ui.run(
        title="ESP32 Serial Monitor",
        port=8080,
        reload=False,
        native=is_bundled  # Only use native window if packaged as an app
    )
