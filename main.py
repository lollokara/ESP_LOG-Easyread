from nicegui import ui, app, Client
import asyncio
from serial_manager import SerialManager
from log_parser import LogEntry
import threading
import time
import random
import traceback
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
        self.filter_level = "ALL"
        self.filter_file = "ALL"
        self.filter_function = "ALL"
        self.auto_scroll = True
        self.auto_reconnect = False
        self.save_to_file = False
        self.mock_mode = False

app_state = AppState()

# We store all logs in a global list for persistence across page reloads
global_logs = []
unique_files = {"ALL"}
unique_functions = {"ALL"}

def handle_log(entry: LogEntry):
    """
    Callback from SerialManager.
    """
    global global_logs, unique_files, unique_functions
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
        self.html_logs = deque(maxlen=2000)

        # UI References
        self.log_html = None
        self.scroll_area = None
        self.file_select = None
        self.function_select = None
        self.level_select = None
        self.port_select = None
        self.baud_select = None
        self.connect_switch = None

    def matches_filter(self, entry: LogEntry) -> bool:
        if self.filter_level != "ALL" and entry.level != self.filter_level:
            return False
        if self.filter_file != "ALL" and entry.file != self.filter_file:
            return False
        if self.filter_function != "ALL" and entry.function != self.filter_function:
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
            # Simple keep-alive check. If accessing the container fails, we exit.
            if not self.log_html or not self.log_html.client.has_socket_connection:
                 return
        except Exception:
            return

        try:
            # If we have new logs
            if len(global_logs) > self.last_processed_index:
                new_entries = global_logs[self.last_processed_index:]
                self.last_processed_index = len(global_logs)

                # Update Dropdowns if needed
                try:
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
                except RuntimeError:
                    pass

                # Filter new entries
                matching_entries = [e for e in new_entries if self.matches_filter(e)]

                if matching_entries:
                    for entry in matching_entries:
                        html = self.format_log_html(entry)
                        self.html_logs.append(html)

                    # Update the HTML content
                    if self.log_html:
                        self.log_html.content = "".join(self.html_logs)

                    if self.auto_scroll and self.scroll_area:
                        self.scroll_area.scroll_to(percent=1.0)
        except Exception as e:
            print("Error in update_loop:")
            traceback.print_exc()

    def refresh_log_view(self):
        """Clears and rebuilds the log view based on current filters."""
        if not self.log_html:
            return

        self.html_logs.clear()

        # Filter all global logs
        matching = [l for l in global_logs if self.matches_filter(l)]

        # Apply rolling window (start with the last 2000)
        initial_load = matching[-2000:]

        for entry in initial_load:
            self.html_logs.append(self.format_log_html(entry))

        self.log_html.content = "".join(self.html_logs)

        # Important: Update index so we don't duplicate these logs in the next update loop
        self.last_processed_index = len(global_logs)

        if self.auto_scroll and self.scroll_area:
             self.scroll_area.scroll_to(percent=1.0)

    def format_log_html(self, entry: LogEntry) -> str:
        # Color coding
        color_class = "text-gray-800"
        if entry.level == "E": color_class = "text-red-600 font-bold"
        elif entry.level == "W": color_class = "text-yellow-600"
        elif entry.level == "I": color_class = "text-green-600"
        elif entry.level == "D": color_class = "text-blue-600"
        elif entry.level == "V": color_class = "text-gray-500"

        # Construct HTML string row
        # Using Tailwind classes similar to before
        # We use a div with flex/grid to mimic the layout

        file_str = f"[{entry.file}]" if entry.file != "UNDEFINED" else ""
        func_str = f"{entry.function}()" if entry.function != "UNDEFINED" else ""

        # Sanitize message for HTML (basic)
        safe_msg = entry.message.replace("<", "&lt;").replace(">", "&gt;")

        return f"""
        <div class="w-full flex gap-1 font-mono text-sm items-start no-wrap hover:bg-gray-100">
            <div class="text-gray-400 w-16 shrink-0">[{entry.timestamp}]</div>
            <div class="{color_class} w-8 shrink-0">[{entry.level}]</div>
            <div class="text-purple-600 w-48 shrink-0 truncate" title="{entry.file}">{file_str}</div>
            <div class="text-orange-600 w-40 shrink-0 truncate" title="{entry.function}">{func_str}</div>
            <div class="{color_class} grow break-all">{safe_msg}</div>
        </div>
        """

    def on_filter_change(self):
        self.filter_level = self.level_select.value
        self.filter_file = self.file_select.value
        self.filter_function = self.function_select.value

        # Save to app state
        app_state.filter_level = self.filter_level
        app_state.filter_file = self.filter_file
        app_state.filter_function = self.filter_function

        self.refresh_log_view()

    def on_autoscroll_change(self, e):
        self.auto_scroll = e.value
        app_state.auto_scroll = e.value
        if self.auto_scroll and self.scroll_area:
            self.scroll_area.scroll_to(percent=1.0)

    def on_clear_logs(self):
        global global_logs, unique_files, unique_functions
        global_logs.clear()

        self.html_logs.clear()
        if self.log_html:
             self.log_html.content = ""
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

            self.level_select = ui.select(
                options=["ALL", "V", "D", "I", "W", "E", "U"],
                value=app_state.filter_level,
                label="Level",
                on_change=self.on_filter_change
            ).classes('w-full')

            self.file_select = ui.select(
                options=sorted(list(unique_files)),
                value=app_state.filter_file,
                label="File",
                on_change=self.on_filter_change
            ).classes('w-full')

            self.function_select = ui.select(
                options=sorted(list(unique_functions)),
                value=app_state.filter_function,
                label="Function",
                on_change=self.on_filter_change
            ).classes('w-full')

            ui.separator().classes('my-4')
            ui.button("Clear Logs", on_click=self.on_clear_logs, color='red').classes('w-full')

        # Main Content
        with ui.column().classes('w-full h-screen p-0'):
            # Toolbar
            with ui.row().classes('w-full bg-white p-2 border-b items-center'):
                ui.button(icon='menu', on_click=drawer.toggle).props('flat round dense')
                ui.label("Log Output").classes('text-xl ml-2')
                ui.space()
                ui.switch("Auto-scroll", value=True, on_change=self.on_autoscroll_change)

            # Log Area
            self.scroll_area = ui.scroll_area().classes('w-full h-full bg-gray-50 p-4')
            with self.scroll_area:
                # We use a single HTML element for better performance
                # sanitize=False is required in newer/specific versions and better for performance
                # since we manually sanitize the input.
                self.log_html = ui.html('', sanitize=False).classes('w-full')

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
    ui.run(title="ESP32 Serial Monitor", port=8080, reload=False)
