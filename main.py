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
import fnmatch
import os

# Try importing pyi_splash (only available in bundled app)
try:
    import pyi_splash
except ImportError:
    pyi_splash = None

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

        # New Features
        self.search_term = ""
        self.cli_history = []
        self.cli_line_ending = "LF" # LF, CR, CRLF
        self.font_size = 14
        self.visible_columns = {
            "timestamp": True,
            "level": True,
            "file": True,
            "function": True,
            "message": True
        }

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

        # Local copies for fast access, synced with AppState
        self.search_term = app_state.search_term
        self.font_size = app_state.font_size
        self.visible_columns = app_state.visible_columns.copy()

        self.last_processed_index = 0

        # Track HTML strings for rolling window
        # We keep this in sync with the DOM to handle refreshes
        # Now we have two lists: Primary (Matched) and Secondary (Dimmed)
        # Wait, rolling window logic gets complicated with two lists.
        # If we append to bottom of page, we are essentially just appending.
        # But the requirement is "outside current filters ... appear at the bottom greyed out".
        # This implies a separate section.
        # Let's maintain ONE main list for the rolling window, but rendering might differ?
        # No, "appear at the bottom" suggests a separate container if we want them grouped.
        # However, strictly chronologically, they are interspersed.
        # "appear at the bottom" is a spatial instruction.
        # Interpretation:
        # Top Section: [Filter MATCH] + [Search MATCH]
        # Bottom Section: [Filter FAIL] + [Search MATCH] (Dimmed)

        self.html_logs_primary = deque(maxlen=2000)
        self.html_logs_secondary = deque(maxlen=500) # Keep fewer of these maybe?

        # UI References
        self.log_container_id_primary = f"log-container-primary-{id(self)}"
        self.log_container_id_secondary = f"log-container-secondary-{id(self)}"
        self.log_container_primary = None
        self.log_container_secondary = None

        self.scroll_area = None
        self.file_select = None
        self.function_select = None
        self.level_select = None
        self.port_select = None
        self.baud_select = None
        self.connect_switch = None
        self.cli_input = None

    def check_match(self, entry: LogEntry):
        """
        Returns:
        0: HIDDEN (No match anywhere)
        1: PRIMARY (Matches Filters AND Search)
        2: SECONDARY (Matches Search BUT Fails Filters)
        """

        # 1. Check Search (Base requirement for visibility)
        matches_search = True
        if self.search_term:
            # Case insensitive search on the full original string or message?
            # "search the entire logs" -> usually implies original raw line
            text_to_search = entry.original.lower()
            pattern = self.search_term.lower()

            if '*' in pattern or '?' in pattern:
                 if not fnmatch.fnmatch(text_to_search, f"*{pattern}*"): # Add wildcards for 'contains' logic
                      matches_search = False
            else:
                 if pattern not in text_to_search:
                      matches_search = False

        if not matches_search:
            return 0

        # 2. Check Filters
        matches_filters = True

        # Level
        if entry.level not in self.filter_level:
            matches_filters = False

        # File
        if "ALL" not in self.filter_file:
            if entry.file not in self.filter_file:
                matches_filters = False

        # Function
        if "ALL" not in self.filter_function:
            if entry.function not in self.filter_function:
                matches_filters = False

        if matches_filters:
            return 1
        else:
            return 2

    async def update_loop(self):
        """
        Called periodically by ui.timer.
        Checks for new logs in global_logs and updates the UI.
        """
        global global_logs

        # Check if client is still connected to avoid RuntimeError
        try:
            # Simple keep-alive check.
            if not self.log_container_primary or not self.log_container_primary.client.has_socket_connection:
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

            # Filter new entries
            if 'new_entries' in locals() and new_entries:
                primary_chunk = []
                secondary_chunk = []

                for entry in new_entries:
                    match_status = self.check_match(entry)
                    if match_status == 1:
                        html = self.format_log_html(entry, dimmed=False)
                        self.html_logs_primary.append(html)
                        primary_chunk.append(html)
                    elif match_status == 2:
                        html = self.format_log_html(entry, dimmed=True)
                        self.html_logs_secondary.append(html)
                        secondary_chunk.append(html)

                    # Handle Auto-complete population for search? (optional, maybe later)

                # JS Append Primary
                if primary_chunk:
                    joined_html = "".join(primary_chunk)
                    js_html = json.dumps(joined_html)
                    # We only autoscroll if we added to primary
                    cmd = f'window.logManager.append("{self.log_container_id_primary}", {js_html}, 2000, {str(self.auto_scroll).lower()})'
                    ui.run_javascript(cmd)

                # JS Append Secondary
                if secondary_chunk:
                    joined_html = "".join(secondary_chunk)
                    js_html = json.dumps(joined_html)
                    # Secondary area generally doesn't autoscroll the main window, but it sits at the bottom.
                    # If we are auto-scrolling, the secondary container is at the bottom of the scroll area anyway.
                    cmd = f'window.logManager.append("{self.log_container_id_secondary}", {js_html}, 500, false)' # Less buffer for secondary
                    ui.run_javascript(cmd)

                    # If autoscroll is ON, we need to scroll the parent scroll_area to bottom
                    if self.auto_scroll and self.scroll_area:
                        # We do this via JS in the append function usually, but since we have two containers,
                        # the JS function targets the container's parent.
                        # Calling it for primary usually handles it, but if only secondary added?
                        pass

        except Exception as e:
            print("Error in update_loop:")
            traceback.print_exc()

    def refresh_log_view(self):
        """Clears and rebuilds the log view based on current filters."""
        if not self.log_container_primary:
            return

        self.html_logs_primary.clear()
        self.html_logs_secondary.clear()

        # Filter all global logs with lock
        with global_lock:
            current_len = len(global_logs)

            # Re-process all logs
            # Optimization: If list is huge, this might be slow. But strictly needed for search/filter changes.
            # Limit to last 3000?
            scan_start = max(0, current_len - 5000)
            entries_to_scan = global_logs[scan_start:]
            self.last_processed_index = current_len

        # Bucket them
        for entry in entries_to_scan:
            match_status = self.check_match(entry)
            if match_status == 1:
                self.html_logs_primary.append(self.format_log_html(entry, dimmed=False))
            elif match_status == 2:
                self.html_logs_secondary.append(self.format_log_html(entry, dimmed=True))

        # Trim to window size
        while len(self.html_logs_primary) > 2000:
             self.html_logs_primary.popleft()
        while len(self.html_logs_secondary) > 500:
             self.html_logs_secondary.popleft()

        # Render Primary
        joined_html_p = "".join(self.html_logs_primary)
        js_html_p = json.dumps(joined_html_p)
        cmd_p = f'window.logManager.setContent("{self.log_container_id_primary}", {js_html_p})'
        ui.run_javascript(cmd_p)

        # Render Secondary
        joined_html_s = "".join(self.html_logs_secondary)
        js_html_s = json.dumps(joined_html_s)
        cmd_s = f'window.logManager.setContent("{self.log_container_id_secondary}", {js_html_s})'
        ui.run_javascript(cmd_s)

        if self.auto_scroll and self.scroll_area:
             self.scroll_area.scroll_to(percent=1.0)

    def format_log_html(self, entry: LogEntry, dimmed: bool = False) -> str:
        # Timestamp logic
        if app_state.realtime_timestamp:
            dt = datetime.datetime.fromtimestamp(entry.arrival_time)
            ts_str = dt.strftime("%M:%S:%f")[:-3]
        else:
            ts_str = entry.timestamp

        # Styles
        base_opacity = "opacity-50 grayscale" if dimmed else ""
        # Font size class is handled by parent container class or we inject inline style?
        # Tailwind arbitrary values for font size: text-[14px]
        font_style = f"font-size: {self.font_size}px;"

        color_class = "text-gray-800"
        if entry.level == "E": color_class = "text-red-600 font-bold"
        elif entry.level == "W": color_class = "text-yellow-600"
        elif entry.level == "I": color_class = "text-green-600"
        elif entry.level == "D": color_class = "text-blue-600"
        elif entry.level == "V": color_class = "text-gray-500"

        # Sanitize message
        safe_msg = entry.message.replace("<", "&lt;").replace(">", "&gt;")

        # Columns Construction
        cols = []

        if self.visible_columns.get("timestamp", True):
            cols.append(f'<div class="text-gray-400 w-24 shrink-0">[{ts_str}]</div>')

        if self.visible_columns.get("level", True):
            cols.append(f'<div class="{color_class} w-8 shrink-0">[{entry.level}]</div>')

        if self.visible_columns.get("file", True):
            file_str = f"[{entry.file}]" if entry.file != "UNDEFINED" else ""
            cols.append(f'<div class="text-purple-600 w-48 shrink-0 truncate" title="{entry.file}">{file_str}</div>')

        if self.visible_columns.get("function", True):
            func_str = f"{entry.function}()" if entry.function != "UNDEFINED" else ""
            cols.append(f'<div class="text-orange-600 w-40 shrink-0 truncate" title="{entry.function}">{func_str}</div>')

        if self.visible_columns.get("message", True):
            cols.append(f'<div class="{color_class} grow break-all select-text">{safe_msg}</div>')

        inner_html = "".join(cols)

        return f"""
        <div class="log-line w-full flex gap-1 font-mono items-start no-wrap hover:bg-gray-100 select-text {base_opacity}" style="{font_style}">
            {inner_html}
        </div>
        """

    def _handle_smart_all_selection(self, new_val, current_val, ui_element):
        result = new_val
        if not new_val:
            result = ["ALL"]
            ui_element.value = ["ALL"]
        else:
            if "ALL" in current_val and len(new_val) > len(current_val):
                result = [x for x in new_val if x != "ALL"]
                ui_element.value = result
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
        self.filter_level = e.value
        app_state.filter_level = self.filter_level
        self.refresh_log_view()

    def on_autoscroll_change(self, e):
        self.auto_scroll = e.value
        app_state.auto_scroll = e.value
        if self.auto_scroll and self.scroll_area:
            self.scroll_area.scroll_to(percent=1.0)

    def on_search_change(self, e):
        self.search_term = e.value
        app_state.search_term = e.value
        self.refresh_log_view()

    def on_font_size_change(self, delta):
        self.font_size = max(8, min(30, self.font_size + delta))
        app_state.font_size = self.font_size
        self.refresh_log_view() # Need to re-render to apply inline styles

    def on_column_toggle(self, col_name, value):
        self.visible_columns[col_name] = value
        app_state.visible_columns = self.visible_columns
        self.refresh_log_view()

    def on_clear_logs(self):
        global global_logs
        with global_lock:
            global_logs.clear()

        self.html_logs_primary.clear()
        self.html_logs_secondary.clear()
        if self.log_container_primary:
             ui.run_javascript(f'window.logManager.setContent("{self.log_container_id_primary}", "")')
        if self.log_container_secondary:
             ui.run_javascript(f'window.logManager.setContent("{self.log_container_id_secondary}", "")')
        self.last_processed_index = 0

    def on_connect_toggle(self, e):
        port = self.port_select.value
        baud = int(self.baud_select.value)
        if e.value:
            app_state.port = port
            app_state.baud = baud
            if serial_manager.connect(port, baud):
                 ui.notify(f"Connected to {port}")
            else:
                 ui.notify(f"Failed to connect to {port}", type='negative')
                 self.connect_switch.value = False
        else:
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

    def send_cli_command(self):
        cmd = self.cli_input.value
        if not cmd: return

        # Add to history
        if not app_state.cli_history or app_state.cli_history[-1] != cmd:
            app_state.cli_history.append(cmd)
            # Keep history reasonable
            if len(app_state.cli_history) > 50:
                app_state.cli_history.pop(0)

        # Determine line ending
        ending = ""
        if app_state.cli_line_ending == "LF": ending = "\n"
        elif app_state.cli_line_ending == "CR": ending = "\r"
        elif app_state.cli_line_ending == "CRLF": ending = "\r\n"

        full_cmd = cmd + ending

        if serial_manager and serial_manager.is_connected:
            serial_manager.write(full_cmd.encode('utf-8'))
            ui.notify(f"Sent: {cmd}")
        elif mock_mode:
             ui.notify(f"Mock Sent: {cmd}")
        else:
            ui.notify("Not Connected", type='warning')

        self.cli_input.value = ""

    def build_ui(self):
        # Header / Sidebar
        with ui.left_drawer(value=True).classes('bg-slate-100 q-pa-md') as drawer:
            ui.markdown("### ESP32 Monitor")

            # --- Appearance ---
            ui.label("Appearance").classes('text-xs font-bold text-gray-500 mt-2')

            # Font Scale
            with ui.row().classes('w-full items-center justify-between'):
                ui.label("Font Size")
                with ui.row().classes('gap-1'):
                    ui.button("-", on_click=lambda: self.on_font_size_change(-1)).props('dense round flat')
                    ui.button("+", on_click=lambda: self.on_font_size_change(1)).props('dense round flat')

            # Columns
            with ui.expansion('Columns', icon='view_column').classes('w-full text-sm'):
                for col, label in [("timestamp", "Time"), ("level", "Level"), ("file", "File"), ("function", "Function"), ("message", "Message")]:
                    ui.checkbox(label, value=self.visible_columns[col], on_change=lambda e, c=col: self.on_column_toggle(c, e.value)).props('dense')

            # --- Connection ---
            ui.separator().classes('my-2')
            ui.label("Connection").classes('text-xs font-bold text-gray-500')

            ports = serial_manager.list_ports()
            current_port = app_state.port if app_state.port in ports else (ports[0] if ports else None)

            self.port_select = ui.select(options=ports, value=current_port, label="Port").classes('w-full')
            ui.button("Refresh", on_click=self.on_refresh_ports).classes('w-full mb-2 text-xs').props('dense outline')

            self.baud_select = ui.select(
                options=[9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600],
                value=app_state.baud,
                label="Baud"
            ).classes('w-full')

            is_connected = serial_manager.is_connected if serial_manager else False
            self.connect_switch = ui.switch("Connect", value=is_connected, on_change=self.on_connect_toggle).classes('w-full')
            if mock_mode: self.connect_switch.disable()

            ui.checkbox("Auto-reconnect", value=serial_manager.auto_reconnect if serial_manager else False, on_change=lambda e: serial_manager.set_auto_reconnect(e.value))

            # --- Logging ---
            ui.separator().classes('my-2')
            ui.label("Logging").classes('text-xs font-bold text-gray-500')
            ui.checkbox("Save to File", value=serial_manager.save_to_file if serial_manager else False, on_change=lambda e: serial_manager.set_save_to_file(e.value))
            ui.switch("Mock Mode", value=mock_mode, on_change=self.on_mock_toggle)

            # --- Filters ---
            ui.separator().classes('my-2')
            ui.label("Filters").classes('text-xs font-bold text-gray-500')

            # Level
            with ui.row().classes('w-full items-center no-wrap'):
                self.level_select = ui.select(
                    options=["V", "D", "I", "W", "E", "U"],
                    value=app_state.filter_level,
                    label="Level",
                    multiple=True,
                    on_change=self.on_level_filter_change
                ).classes('grow').props('use-chips dense')
                with ui.button(icon='select_all', on_click=lambda: self.level_select.set_value(["V", "D", "I", "W", "E", "U"])).props('flat dense round size=sm'): pass
                with ui.button(icon='clear', on_click=lambda: self.level_select.set_value([])).props('flat dense round color=red size=sm'): pass

            # File
            self.file_select = ui.select(
                options=sorted(list(unique_files)),
                value=app_state.filter_file,
                label="File",
                multiple=True,
                on_change=self.on_file_filter_change
            ).classes('w-full').props('use-chips dense')

            # Function
            self.function_select = ui.select(
                options=sorted(list(unique_functions)),
                value=app_state.filter_function,
                label="Function",
                multiple=True,
                on_change=self.on_function_filter_change
            ).classes('w-full').props('use-chips dense')

            ui.separator().classes('my-4')
            ui.button("Clear Logs", on_click=self.on_clear_logs, color='red').classes('w-full')

        # JS Injection
        ui.add_head_html("""
        <style>
        body { overflow: hidden; }
        .select-text { -webkit-user-select: text !important; user-select: text !important; }
        .log-line { line-height: 1.5; border-bottom: 1px solid transparent; }
        .log-line:hover { border-bottom: 1px solid #ddd; }
        </style>
        <script>
        window.logManager = {
            append: function(id, html, maxLines, autoScroll) {
                const el = document.getElementById(id);
                if (!el) return;

                const scrollTarget = el.closest('.q-scrollarea').querySelector('.q-scrollarea__container');

                el.insertAdjacentHTML('beforeend', html);

                let removedHeight = 0;
                let countToRemove = el.childElementCount - maxLines;

                if (countToRemove > 0) {
                    if (!autoScroll && scrollTarget) {
                        for(let i=0; i<countToRemove; i++) {
                            removedHeight += el.children[i].offsetHeight;
                        }
                    }
                    while (el.childElementCount > maxLines) {
                        el.firstElementChild.remove();
                    }
                    if (!autoScroll && scrollTarget && removedHeight > 0) {
                        scrollTarget.scrollTop -= removedHeight;
                    }
                }

                if (autoScroll && scrollTarget) {
                    scrollTarget.scrollTop = scrollTarget.scrollHeight;
                }
            },
            setContent: function(id, html) {
                const el = document.getElementById(id);
                if (el) el.innerHTML = html;
            }
        }
        </script>
        """)

        # Main Layout
        with ui.column().classes('w-full h-screen p-0 overflow-hidden no-wrap'):

            # --- Top Toolbar ---
            with ui.row().classes('w-full bg-white p-2 border-b items-center shrink-0 gap-2'):
                ui.button(icon='menu', on_click=drawer.toggle).props('flat round dense')

                # Search Bar (Top Center/Left)
                with ui.input(placeholder="Search logs... (* ?)", on_change=self.on_search_change).classes('grow').props('dense outlined rounded') as search:
                    search.value = self.search_term
                    with search.add_slot('prepend'):
                        ui.icon('search')
                    with search.add_slot('append'):
                         ui.icon('close').props('cursor-pointer').on('click', lambda: search.set_value(""))

                ui.switch("Time", value=app_state.realtime_timestamp, on_change=lambda e: setattr(app_state, 'realtime_timestamp', e.value)).props('dense').tooltip("Real-time Timestamp")
                ui.switch("Scroll", value=app_state.auto_scroll, on_change=self.on_autoscroll_change).props('dense').tooltip("Auto-scroll")

            # --- Log Area ---
            self.scroll_area = ui.scroll_area().classes('w-full grow bg-gray-50 select-text')
            with self.scroll_area:
                with ui.column().classes('w-full min-h-full'):
                    # Primary Container (Active Logs)
                    self.log_container_primary = ui.element('div').props(f'id="{self.log_container_id_primary}"').classes('w-full flex flex-col select-text p-2')

                    # Separator (if we have secondary logs logic, though dynamically they appear here)
                    ui.separator().classes('my-4 opacity-30')

                    # Secondary Container (Dimmed/Hidden Logs)
                    ui.label("Filtered Matches (Search Only)").classes('text-xs text-gray-400 ml-2')
                    self.log_container_secondary = ui.element('div').props(f'id="{self.log_container_id_secondary}"').classes('w-full flex flex-col select-text p-2 bg-gray-100 border-t')

            # --- Footer (CLI) ---
            with ui.row().classes('w-full bg-white p-2 border-t items-center shrink-0 gap-2'):
                ui.icon('terminal').classes('text-gray-500')

                # CLI Input
                self.cli_input = ui.input(placeholder="Send command...", on_change=None).classes('grow').props('dense outlined')
                self.cli_input.on('keydown.enter', self.send_cli_command)
                # History handlers (Basic)
                # ui.input doesn't expose easy keydown for specific keys like up/down without some js or custom events?
                # NiceGUI 1.4+ supports key modifiers.
                # We can use on('keydown.up', ...)

                def navigate_history(delta):
                    if not app_state.cli_history: return
                    # Simple history implementation: just cycle last one or use an index if we want to be fancy
                    # For now, just populate the last command
                    self.cli_input.value = app_state.cli_history[-1]

                self.cli_input.on('keydown.up', lambda: navigate_history(-1))

                # Line Ending
                ui.select(
                    options=["LF", "CR", "CRLF"],
                    value=app_state.cli_line_ending,
                    on_change=lambda e: setattr(app_state, 'cli_line_ending', e.value)
                ).props('dense options-dense borderless').classes('w-20')

                ui.button(icon='send', on_click=self.send_cli_command).props('flat round dense color=primary')

        # Start timer
        ui.timer(0.2, self.update_loop)

@ui.page('/')
def main_page(client: Client):
    global serial_manager
    if serial_manager is None:
        serial_manager = SerialManager(on_log_received=handle_log)

    viewer = LogViewer()
    viewer.build_ui()

# Splash Screen Close
def startup():
    if pyi_splash:
        try:
            pyi_splash.close()
        except:
            pass

app.on_startup(startup)

if __name__ in {"__main__", "__mp_main__"}:
    import sys
    is_bundled = getattr(sys, 'frozen', False)
    ui.run(
        title="ESP32 Serial Monitor",
        port=8080,
        reload=False,
        native=is_bundled
    )
