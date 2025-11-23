from nicegui import ui, app, Client
import asyncio
from serial_manager import SerialManager
from log_parser import LogEntry
from database import DatabaseManager
from storage_utils import get_db_path
from session_manager import SessionManager as SessionManagerUI
import threading
import time
import random
import traceback
import json
import datetime
from collections import deque
import fnmatch
import sys
import io

# App Log Capture
class LogCapture:
    def __init__(self, max_len=10000):
        self.buffer = deque(maxlen=max_len)
        self.original_stderr = sys.stderr
        self.original_stdout = sys.stdout

    def write(self, message):
        if message:
            self.buffer.append(message)
            # Echo to original stderr (or stdout if preferred) for debugging
            try:
                self.original_stderr.write(message)
                self.original_stderr.flush()
            except Exception:
                pass

    def flush(self):
        try:
            self.original_stderr.flush()
        except Exception:
            pass

    def get_content(self):
        return "".join(self.buffer)

app_log_capture = LogCapture()
# Redirect stderr to capture tracebacks
sys.stderr = app_log_capture

# Global backend state (shared across clients)
serial_manager = None
mock_mode = False
mock_thread = None

# Initialize Database
db_path = get_db_path()
print(f"Using database at: {db_path}")
db = DatabaseManager(db_path=db_path)

# Persistence State (Survives Reloads)
class AppState:
    def __init__(self):
        self.port = None
        self.baud = 115200
        self.filter_level = ["V", "D", "I", "W", "E", "U"]
        self.filter_file = ["ALL"]
        self.filter_function = ["ALL"]
        self.auto_scroll = True
        self.auto_reconnect = False
        self.save_to_file = False
        self.mock_mode = False
        self.realtime_timestamp = False
        self.session_mode = "Auto-New"
        self.current_session_id = None
        
        self.search_term = ""
        self.cli_history = []
        self.cli_line_ending = "LF"
        self.font_size = 14
        self.visible_columns = {
            "timestamp": True,
            "level": True,
            "file": True,
            "function": True,
            "message": True
        }
        self.current_theme = "Dark"

app_state = AppState()

# Ensure a default session exists on app start
if app_state.current_session_id is None:
    app_state.current_session_id = db.create_session(f"Session {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "App Start")

global_lock = threading.Lock()
unique_files = {"ALL"}
unique_functions = {"ALL"}

def handle_log(entry: LogEntry):
    # Insert into Database
    if app_state.current_session_id is not None:
        db.insert_log(app_state.current_session_id, entry)

    # Update global unique filters (simple cache)
    with global_lock:
        if entry.file != "UNDEFINED":
            unique_files.add(entry.file)
        if entry.function != "UNDEFINED":
            unique_functions.add(entry.function)

def mock_log_generator():
    files = ["main.cpp", "wifi.cpp", "sensor.cpp", "preferences.cpp", "display.cpp"]
    functions = ["setup", "loop", "connect", "read_data", "update_ui", "save_config", "init"]
    levels = ["V", "D", "I", "W", "E"]
    messages = ["Starting up...", "Connection failed", "Data received: 0xFE", "Battery level: 85%", "NVS Error: Key not found", "WiFi connected, IP: 192.168.1.123", "Rendering frame", "Watchdog reset"]
    counter = 0
    while mock_mode:
        timestamp = str(int(time.time() * 1000) % 100000)
        level = random.choice(levels)
        file = random.choice(files)
        line = random.randint(10, 500)
        function = random.choice(functions)
        msg = random.choice(messages)
        if random.random() < 0.1: raw = f"Standard output message {counter}"
        else: raw = f"[{timestamp}][{level}][{file}:{line}] {function}(): {msg} {counter}"
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

THEMES = {
    "Light": {
        "bg_main": "bg-white", "bg_sidebar": "bg-gray-100", "bg_header": "bg-white", "bg_input": "bg-white",
        "text_primary": "text-gray-800", "text_secondary": "text-gray-600", "border": "border-gray-300",
        "log_hover": "hover:bg-gray-100", "log_V": "text-gray-500", "log_D": "text-blue-600",
        "log_I": "text-green-600", "log_W": "text-yellow-600", "log_E": "text-red-600 font-bold",
        "button_active": "bg-blue-500 text-white", "accent": "blue-500", "log_bg": "bg-gray-50"
    },
    "Dark": {
        "bg_main": "bg-slate-900", "bg_sidebar": "bg-slate-800", "bg_header": "bg-slate-800", "bg_input": "bg-slate-900",
        "text_primary": "text-gray-200", "text_secondary": "text-gray-400", "border": "border-slate-700",
        "log_hover": "hover:bg-slate-800", "log_V": "text-gray-400", "log_D": "text-blue-400",
        "log_I": "text-green-400", "log_W": "text-yellow-400", "log_E": "text-red-400 font-bold",
        "button_active": "bg-blue-600 text-white", "accent": "blue-400", "log_bg": "bg-slate-900"
    },
    "Cyberpunk": {
        "bg_main": "bg-black", "bg_sidebar": "bg-zinc-900", "bg_header": "bg-zinc-900", "bg_input": "bg-black",
        "text_primary": "text-cyan-400", "text_secondary": "text-pink-500", "border": "border-pink-500",
        "log_hover": "hover:bg-zinc-900", "log_V": "text-zinc-500", "log_D": "text-cyan-400",
        "log_I": "text-green-400", "log_W": "text-yellow-400", "log_E": "text-red-500 font-bold",
        "button_active": "bg-pink-600 text-black", "accent": "cyan-400", "log_bg": "bg-black"
    },
    "Monokai": {
        "bg_main": "bg-[#272822]", "bg_sidebar": "bg-[#1e1f1c]", "bg_header": "bg-[#1e1f1c]", "bg_input": "bg-[#272822]",
        "text_primary": "text-[#f8f8f2]", "text_secondary": "text-[#75715e]", "border": "border-[#75715e]",
        "log_hover": "hover:bg-[#3e3d32]", "log_V": "text-[#75715e]", "log_D": "text-[#66d9ef]",
        "log_I": "text-[#a6e22e]", "log_W": "text-[#fd971f]", "log_E": "text-[#f92672] font-bold",
        "button_active": "bg-[#a6e22e] text-[#272822]", "accent": "green-400", "log_bg": "bg-[#272822]"
    }
}

class LogViewer:
    def __init__(self):
        self.filter_level = app_state.filter_level
        self.filter_file = app_state.filter_file
        self.filter_function = app_state.filter_function
        self.auto_scroll = app_state.auto_scroll
        self.search_term = app_state.search_term
        self.font_size = app_state.font_size
        self.visible_columns = app_state.visible_columns.copy()
        self.current_theme = app_state.current_theme
        
        self.log_container_id = f"log-container-{id(self)}"
        self.log_container = None
        self.window_size = 200 # Small fetch size for responsiveness
        self.max_display_lines = 2000 # Max lines to keep in DOM

        # State for Infinite Scroll
        self.fetching = False
        self.earliest_loaded_offset = 0 # The offset (from start) of the top-most log in view
        self.latest_loaded_offset = 0 # The offset (from start) of the bottom-most log in view + 1
        
        self.drawer = None
        self.main_column = None
        self.header_row = None
        self.footer_row = None
        self.scroll_area = None
        self.inputs = []
        self.selects = []
        self.scroll_top_btn = None
        self.scroll_bottom_btn = None

        self.last_fetched_count = 0
        self.session_manager_ui = SessionManagerUI(db, self.load_session_by_id)

        # Simple App Logger
        self.app_log_dialog = None
        self.app_log_content = None

    def load_session_by_id(self, session_id):
        app_state.current_session_id = session_id
        # Reload view
        self.on_clear_logs()
        asyncio.create_task(self.load_initial_view())

    def get_theme(self):
        return THEMES.get(self.current_theme, THEMES["Dark"])

    async def update_loop(self):
        """
        Polls the database for new logs.
        If we are at the bottom (auto_scroll=True), we append new logs.
        """
        if not self.log_container or not self.log_container.client.has_socket_connection: return

        try:
            if not app_state.current_session_id: return

            # Fetch total count first to see if anything changed
            total_logs = db.get_total_log_count(app_state.current_session_id, self.get_filters(), self.search_term)

            # Only update if Auto Scroll is ON
            if self.auto_scroll and total_logs > self.latest_loaded_offset:
                print(f"[Update] Auto-scroll ON. Total: {total_logs}, Latest: {self.latest_loaded_offset}. Fetching...")
                # New logs arrived and we are watching live
                limit = min(self.window_size, total_logs - self.latest_loaded_offset)

                new_logs = db.get_logs(
                    app_state.current_session_id,
                    limit=limit,
                    offset=self.latest_loaded_offset,
                    filters=self.get_filters(),
                    search_term=self.search_term
                )

                if new_logs:
                    html_chunk = "".join([self.format_log_html(l) for l in new_logs])
                    js_html = json.dumps(html_chunk)
                    # Append to DOM.
                    ui.run_javascript(f'if(window.logManager) window.logManager.append("{self.log_container_id}", {js_html}, {self.max_display_lines}, true)')

                    # Update Offsets
                    count = len(new_logs)
                    self.latest_loaded_offset += count

                    # If we exceeded max lines, we dropped from top
                    current_count = self.latest_loaded_offset - self.earliest_loaded_offset
                    if current_count > self.max_display_lines:
                        dropped = current_count - self.max_display_lines
                        self.earliest_loaded_offset += dropped
                        print(f"[Update] Pruned {dropped} lines from TOP. New Earliest: {self.earliest_loaded_offset}")

            # Keep filters updated regardless
            if total_logs > self.last_fetched_count:
                self.last_fetched_count = total_logs
                self.update_filter_options()

        except Exception as e:
            print("Error in update_loop:")
            traceback.print_exc()

    def update_filter_options(self):
         # Update select options periodically
         if hasattr(self, 'file_select'):
            current_opts = set(self.file_select.options)
            if len(unique_files) > len(current_opts):
                self.file_select.options = sorted(list(unique_files))
                self.file_select.update()
         if hasattr(self, 'function_select'):
            current_opts = set(self.function_select.options)
            if len(unique_functions) > len(current_opts):
                self.function_select.options = sorted(list(unique_functions))
                self.function_select.update()

    def get_filters(self):
        return {
            "level": self.filter_level,
            "file": self.filter_file,
            "function": self.filter_function
        }

    async def load_initial_view(self):
        """Loads the last N logs for the initial view"""
        if not app_state.current_session_id: return
        if not self.log_container: return

        try:
            total_logs = db.get_total_log_count(app_state.current_session_id, self.get_filters(), self.search_term)
            self.last_fetched_count = total_logs

            # Load last N logs
            start_offset = max(0, total_logs - self.max_display_lines)
            self.earliest_loaded_offset = start_offset
            self.latest_loaded_offset = total_logs

            logs = db.get_logs(
                app_state.current_session_id,
                limit=self.max_display_lines,
                offset=start_offset,
                filters=self.get_filters(),
                search_term=self.search_term
            )

            html = "".join([self.format_log_html(l) for l in logs])
            js_html = json.dumps(html)
            # Use client context to avoid slot errors
            with self.log_container.client:
                 ui.run_javascript(f'if(window.logManager) window.logManager.setContent("{self.log_container_id}", {js_html})')

            # Scroll to bottom
            if self.scroll_area:
                self.scroll_area.scroll_to(percent=1.0)
        except Exception:
            traceback.print_exc()

    async def load_older_logs(self):
        """Called when user scrolls to top"""
        if self.fetching or not app_state.current_session_id or self.earliest_loaded_offset <= 0: return
        self.fetching = True

        try:
            # We want to load 'window_size' logs BEFORE 'earliest_loaded_offset'
            fetch_limit = self.window_size
            fetch_offset = max(0, self.earliest_loaded_offset - fetch_limit)

            # If we are near 0, we might request fewer than window_size
            real_limit = self.earliest_loaded_offset - fetch_offset

            if real_limit <= 0: return

            logs = db.get_logs(
                app_state.current_session_id,
                limit=real_limit,
                offset=fetch_offset,
                filters=self.get_filters(),
                search_term=self.search_term
            )

            if logs:
                html = "".join([self.format_log_html(l) for l in logs])
                js_html = json.dumps(html)
                # Use prepend in JS with max lines to prune bottom
                ui.run_javascript(f'if(window.logManager) window.logManager.prepend("{self.log_container_id}", {js_html}, {self.max_display_lines})')

                self.earliest_loaded_offset = fetch_offset

                # If we prepended, we might have dropped from bottom
                current_count = self.latest_loaded_offset - self.earliest_loaded_offset
                # (Note: This is a bit of an estimation if JS and Python drift, but we trust logic)
                # The actual count in DOM is now min(current_count + len(logs), max_display_lines)
                # Wait, current_count before append was (latest - earliest_old).
                # New count = (latest - earliest_new).
                # If > max, we drop from bottom, so 'latest' moves back.

                # Recalculate 'latest' based on strict window size
                virtual_end = self.earliest_loaded_offset + self.max_display_lines
                if self.latest_loaded_offset > virtual_end:
                    self.latest_loaded_offset = virtual_end

        except Exception as e:
            print("Error loading older logs:")
            traceback.print_exc()
        finally:
            self.fetching = False

    async def load_newer_logs(self):
        """Called when user scrolls to bottom (and auto_scroll is off)"""
        if self.fetching or not app_state.current_session_id: return

        # Check if we actually have newer logs in DB
        # We need the real total count
        total_logs = db.get_total_log_count(app_state.current_session_id, self.get_filters(), self.search_term)
        if self.latest_loaded_offset >= total_logs: return

        print(f"[ScrollDown] Loading newer logs. Current Latest: {self.latest_loaded_offset}, Total: {total_logs}")
        self.fetching = True
        try:
            fetch_limit = self.window_size

            logs = db.get_logs(
                app_state.current_session_id,
                limit=fetch_limit,
                offset=self.latest_loaded_offset,
                filters=self.get_filters(),
                search_term=self.search_term
            )

            if logs:
                html = "".join([self.format_log_html(l) for l in logs])
                js_html = json.dumps(html)
                # Append, NO auto-scroll force
                ui.run_javascript(f'if(window.logManager) window.logManager.append("{self.log_container_id}", {js_html}, {self.max_display_lines}, false)')

                self.latest_loaded_offset += len(logs)

                # If we exceeded max lines, we dropped from top
                current_count = self.latest_loaded_offset - self.earliest_loaded_offset
                if current_count > self.max_display_lines:
                    dropped = current_count - self.max_display_lines
                    self.earliest_loaded_offset += dropped
                    print(f"[ScrollDown] Pruned {dropped} lines from TOP. New Earliest: {self.earliest_loaded_offset}")

        except Exception as e:
            print("Error loading newer logs:")
            traceback.print_exc()
        finally:
            self.fetching = False

    def format_log_html(self, entry: LogEntry, dimmed: bool = False) -> str:
        theme = self.get_theme()
        if app_state.realtime_timestamp:
            dt = datetime.datetime.fromtimestamp(entry.arrival_time)
            ts_str = dt.strftime("%M:%S:%f")[:-3]
        else: ts_str = entry.timestamp

        base_opacity = "opacity-50 grayscale" if dimmed else ""
        font_style = f"font-size: {self.font_size}px;"
        color_class = theme["text_primary"]
        if entry.level == "E": color_class = theme["log_E"]
        elif entry.level == "W": color_class = theme["log_W"]
        elif entry.level == "I": color_class = theme["log_I"]
        elif entry.level == "D": color_class = theme["log_D"]
        elif entry.level == "V": color_class = theme["log_V"]

        safe_msg = entry.message.replace("<", "&lt;").replace(">", "&gt;")
        cols = []
        if self.visible_columns.get("timestamp", True): cols.append(f'<div class="{theme["text_secondary"]} w-24 shrink-0">[{ts_str}]</div>')
        if self.visible_columns.get("level", True): cols.append(f'<div class="{color_class} w-8 shrink-0">[{entry.level}]</div>')
        if self.visible_columns.get("file", True):
            file_str = f"[{entry.file}]" if entry.file != "UNDEFINED" else ""
            cols.append(f'<div class="text-purple-500 w-48 shrink-0 truncate" title="{entry.file}">{file_str}</div>')
        if self.visible_columns.get("function", True):
            func_str = f"{entry.function}()" if entry.function != "UNDEFINED" else ""
            cols.append(f'<div class="text-orange-500 w-40 shrink-0 truncate" title="{entry.function}">{func_str}</div>')
        if self.visible_columns.get("message", True): cols.append(f'<div class="{color_class} grow break-all select-text">{safe_msg}</div>')
        inner_html = "".join(cols)
        # Add data-id for scroll tracking
        return f"""<div class="log-line w-full flex gap-1 font-mono items-start no-wrap {theme['log_hover']} select-text {base_opacity} animate-fade-in" style="{font_style}" data-id="{entry.id if hasattr(entry, 'id') else 0}">{inner_html}</div>"""

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
        asyncio.create_task(self.load_initial_view())

    def on_function_filter_change(self, e):
        self.filter_function = self._handle_smart_all_selection(e.value, self.filter_function, self.function_select)
        app_state.filter_function = self.filter_function
        asyncio.create_task(self.load_initial_view())

    def on_level_filter_change(self, e):
        self.filter_level = e.value
        app_state.filter_level = self.filter_level
        asyncio.create_task(self.load_initial_view())

    def on_autoscroll_change(self, e):
        self.auto_scroll = e.value
        app_state.auto_scroll = e.value
        if self.auto_scroll and self.scroll_area: self.scroll_area.scroll_to(percent=1.0)

    def on_search_change(self, e):
        self.search_term = e.value
        app_state.search_term = e.value
        asyncio.create_task(self.load_initial_view())
        
    def on_font_size_change(self, delta):
        self.font_size = max(8, min(30, self.font_size + delta))
        app_state.font_size = self.font_size
        asyncio.create_task(self.load_initial_view())
        
    def on_column_toggle(self, col_name, value):
        self.visible_columns[col_name] = value
        app_state.visible_columns = self.visible_columns
        asyncio.create_task(self.load_initial_view())

    def on_clear_logs(self):
        # Clear View Only
        if self.log_container: ui.run_javascript(f'if(window.logManager) window.logManager.setContent("{self.log_container_id}", "")')
        self.last_fetched_count = 0 # Reset fetch counter so we re-fetch if needed?
        # Actually, if we clear view, we might want to reload fresh.
        # But user wants "Clear Logs" -> Clear screen.
        # If we reload, they appear again.
        # So we should probably mark a "hidden_before" timestamp or similar.
        # For now, just clear the DOM.

    def on_connect_toggle(self, e):
        port = self.port_select.value
        baud = int(self.baud_select.value)
        if e.value: 
            if app_state.session_mode == "Auto-New":
                 if app_state.current_session_id:
                     db.end_session(app_state.current_session_id)
                 new_name = f"Session {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                 app_state.current_session_id = db.create_session(new_name, f"{port}@{baud}")
                 self.on_clear_logs()
                 ui.notify("New Session Started")

            app_state.port = port
            app_state.baud = baud
            if serial_manager.connect(port, baud): ui.notify(f"Connected to {port}")
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
            if self.connect_switch: self.connect_switch.disable()
        else:
            ui.notify("Mock Mode Stopped")
            if self.connect_switch: self.connect_switch.enable()
                
    def send_cli_command(self):
        cmd = self.cli_input.value
        if not cmd: return
        if not app_state.cli_history or app_state.cli_history[-1] != cmd:
            app_state.cli_history.append(cmd)
            if len(app_state.cli_history) > 50: app_state.cli_history.pop(0)
        self.history_index = -1
        ending = {"LF": "\n", "CR": "\r", "CRLF": "\r\n"}.get(app_state.cli_line_ending, "\n")
        full_cmd = cmd + ending
        if serial_manager and serial_manager.is_connected:
            try:
                serial_manager.write(full_cmd.encode('utf-8'))
                ui.notify(f"Sent: {cmd}")
                self.cli_input.value = ""
            except Exception as e:
                ui.notify(f"Error sending: {e}", type='negative')
        elif mock_mode:
            ui.notify(f"Mock Sent: {cmd}")
            self.cli_input.value = ""
        else:
            ui.notify("Not Connected", type='warning')

    def on_theme_change(self, e):
        app_state.current_theme = e.value
        ui.run_javascript('location.reload()')

    def scroll_to_top(self):
        if self.scroll_area:
            self.scroll_area.scroll_to(percent=0.0)

    def scroll_to_bottom(self):
        if self.scroll_area:
            self.scroll_area.scroll_to(percent=1.0)

    def on_scroll(self, e):
        # Infinite Scroll Trigger
        if e.vertical_percentage < 0.05: # Top 5%
            asyncio.create_task(self.load_older_logs())
        elif e.vertical_percentage > 0.95 and not self.auto_scroll: # Bottom 5% and NOT auto-scrolling
            asyncio.create_task(self.load_newer_logs())

        # Show/Hide Scroll to Top Button
        if self.scroll_top_btn:
             if e.vertical_percentage > 0.1:
                 self.scroll_top_btn.classes(remove='hidden')
             else:
                 self.scroll_top_btn.classes(add='hidden')

        # Show/Hide Scroll to Bottom Button
        if self.scroll_bottom_btn:
             if e.vertical_percentage < 0.95:
                 self.scroll_bottom_btn.classes(remove='hidden')
             else:
                 self.scroll_bottom_btn.classes(add='hidden')

    def open_app_logs(self):
        with ui.dialog() as self.app_log_dialog, ui.card().classes('w-full max-w-4xl h-[80vh] flex flex-col'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label("App Logs").classes('text-xl font-bold')
                with ui.row().classes('gap-2'):
                    ui.button(icon='refresh', on_click=lambda: self.app_log_content.set_text(app_log_capture.get_content())).props('flat round dense')
                    ui.button(icon='close', on_click=self.app_log_dialog.close).props('flat round dense')
            ui.separator()
            with ui.scroll_area().classes('w-full grow bg-black text-white p-2 font-mono text-xs'):
                 self.app_log_content = ui.label(app_log_capture.get_content()).classes('whitespace-pre-wrap')
            self.app_log_dialog.open()

    def build_ui(self):
        is_dark = str(self.current_theme != "Light").lower()
        theme = self.get_theme()

        ui.add_head_html("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');
        body { overflow: hidden; font-family: 'JetBrains Mono', monospace; }
        .select-text { -webkit-user-select: text !important; user-select: text !important; }
        .log-line { line-height: 1.5; border-bottom: 1px solid transparent; }
        .log-line:hover { border-bottom: 1px solid rgba(255, 255, 255, 0.1); }
        @keyframes fade-in { from { opacity: 0; transform: translateX(-5px); } to { opacity: 1; transform: none; } }
        .animate-fade-in { animation: fade-in 0.1s ease-out forwards; }
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: rgba(0,0,0,0.1); }
        ::-webkit-scrollbar-thumb { background: #555; border-radius: 0; }
        ::-webkit-scrollbar-thumb:hover { background: #777; }
        /* Disable browser scroll anchoring to prevent fighting with JS manual adjustment */
        .q-scrollarea__container { overflow-anchor: none !important; }
        </style>
        <script>
        document.addEventListener('contextmenu', (e) => {
            const selection = window.getSelection();
            const text = selection.toString();
            if (text.length > 0) {
                // Try modern API first, fallback to legacy
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    navigator.clipboard.writeText(text).catch(err => {
                        console.warn('Clipboard API failed, trying execCommand', err);
                        try { document.execCommand('copy'); } catch (ex) { console.error('Copy failed', ex); }
                    });
                } else {
                    try { document.execCommand('copy'); } catch (ex) { console.error('Copy failed', ex); }
                }
            }
        });

        window.logManager = {
            append: function(id, html, maxLines, autoScroll) {
                const el = document.getElementById(id);
                if (!el) return;
                const scrollTarget = el.closest('.q-scrollarea').querySelector('.q-scrollarea__container');

                // Check if user is near bottom before appending to decide on auto-scroll override
                const isNearBottom = (scrollTarget.scrollHeight - scrollTarget.scrollTop - scrollTarget.clientHeight) < 50;

                el.insertAdjacentHTML('beforeend', html);

                // Cleanup old logs (FROM TOP)
                let removedHeight = 0;
                let countToRemove = el.childElementCount - maxLines;

                if (countToRemove > 0) {
                    // Logic to remove from TOP
                    // If we are NOT auto-scrolling (viewing history), removing top elements shifts view up.
                    // We must compensate.
                    if (!autoScroll) {
                        for(let i=0; i<countToRemove; i++) {
                            removedHeight += el.children[i].getBoundingClientRect().height;
                        }
                    }

                    for(let i=0; i<countToRemove; i++) { el.firstElementChild.remove(); }

                    if (!autoScroll && removedHeight > 0) {
                        scrollTarget.scrollTop -= removedHeight;
                    }
                }

                // Auto Scroll logic
                if (autoScroll) {
                    scrollTarget.scrollTop = scrollTarget.scrollHeight;
                }
            },
            prepend: function(id, html, maxLines) {
                const el = document.getElementById(id);
                if (!el) return;
                const scrollTarget = el.closest('.q-scrollarea').querySelector('.q-scrollarea__container');
                const oldHeight = scrollTarget.scrollHeight;
                const oldTop = scrollTarget.scrollTop;

                el.insertAdjacentHTML('afterbegin', html);

                // Cleanup logs (FROM BOTTOM) if needed
                let countToRemove = el.childElementCount - maxLines;
                if (countToRemove > 0) {
                    for(let i=0; i<countToRemove; i++) { el.lastElementChild.remove(); }
                }

                // Maintain scroll position (shift down by the height of added elements)
                const newHeight = scrollTarget.scrollHeight;
                // If we removed elements from bottom, scrollHeight might not increase as much as expected,
                // but scrollTop is relative to top. Prepending adds to top.
                // New elements are at top. We want to stay looking at the "old" top element.
                // So we add the height difference.
                // (This assumes bottom removal doesn't affect top position, which is true)
                scrollTarget.scrollTop = oldTop + (newHeight - oldHeight);
            },
            setContent: function(id, html) {
                const el = document.getElementById(id);
                if (el) el.innerHTML = html;
            }
        }
        </script>
        """)

        ui.run_javascript(f'Quasar.Dark.set({is_dark})')

        with ui.left_drawer(value=True).classes(f"q-pa-md {theme['bg_sidebar']} {theme['text_primary']} transition-all duration-300 border-r {theme['border']}") as self.drawer:
            ui.markdown("### SerialLens").classes('font-bold')
            ui.label("Appearance").classes(f"text-xs font-bold mt-4")
            self.selects.append(ui.select(options=list(THEMES.keys()), value=self.current_theme, label="Theme", on_change=self.on_theme_change).classes(f"w-full {theme['bg_input']} {theme['text_primary']}"))
            
            with ui.row().classes('w-full items-center justify-between mt-2'):
                ui.label("Font Size")
                with ui.row().classes('gap-1'):
                    ui.button("-", on_click=lambda: self.on_font_size_change(-1)).props('dense square flat')
                    ui.button("+", on_click=lambda: self.on_font_size_change(1)).props('dense square flat')

            with ui.expansion('Columns', icon='view_column').classes('w-full text-sm'):
                for col, label in [("timestamp", "Time"), ("level", "Level"), ("file", "File"), ("function", "Function"), ("message", "Message")]:
                    ui.checkbox(label, value=self.visible_columns[col], on_change=lambda e, c=col: self.on_column_toggle(c, e.value)).props('dense')

            ui.separator().classes(f"my-4")
            ui.label("Connection").classes(f"text-xs font-bold")

            ports = serial_manager.list_ports()
            current_port = app_state.port if app_state.port in ports else (ports[0] if ports else None)
            self.port_select = ui.select(options=ports, value=current_port, label="Port").classes(f"w-full {theme['bg_input']} {theme['text_primary']}").props('dense outlined')
            self.selects.append(self.port_select)
            ui.button("Refresh", on_click=self.on_refresh_ports).classes(f"w-full mb-2 text-xs border").props('dense square outline')
            self.baud_select = ui.select(options=[9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600], value=app_state.baud, label="Baud").classes(f"w-full {theme['bg_input']} {theme['text_primary']}")
            self.selects.append(self.baud_select)

            is_connected = serial_manager.is_connected if serial_manager else False
            self.connect_switch = ui.switch("Connect", value=is_connected, on_change=self.on_connect_toggle).classes('w-full')
            if mock_mode: self.connect_switch.disable()
            ui.checkbox("Auto-reconnect", value=serial_manager.auto_reconnect if serial_manager else False, on_change=lambda e: serial_manager.set_auto_reconnect(e.value))

            ui.separator().classes(f"my-4")
            ui.label("Logging").classes(f"text-xs font-bold")
            ui.select(options=["Auto-New", "Single"], value=app_state.session_mode, label="Session Mode", on_change=lambda e: setattr(app_state, 'session_mode', e.value)).classes(f"w-full {theme['bg_input']} {theme['text_primary']}").props('dense outlined').tooltip("Auto-New: New session on each connect")

            ui.button("Manage Sessions", icon="history", on_click=self.session_manager_ui.open).classes(f"w-full text-xs border {theme['border']} mb-2").props('dense square outline')
            ui.button("App Logs", icon="bug_report", on_click=self.open_app_logs).classes(f"w-full text-xs border {theme['border']} mb-2").props('dense square outline')

            ui.checkbox("Save to File", value=serial_manager.save_to_file if serial_manager else False, on_change=lambda e: serial_manager.set_save_to_file(e.value))
            ui.switch("Mock Mode", value=mock_mode, on_change=self.on_mock_toggle)

            ui.separator().classes(f"my-4")
            ui.label("Filters").classes(f"text-xs font-bold")
            with ui.row().classes('w-full items-center no-wrap gap-1'):
                self.level_select = ui.select(options=["V", "D", "I", "W", "E", "U"], value=app_state.filter_level, label="Level", multiple=True, on_change=self.on_level_filter_change).classes(f"grow {theme['bg_input']} {theme['text_primary']}").props('use-chips dense outlined')
                self.selects.append(self.level_select)
                ui.button(icon='select_all', on_click=lambda: self.level_select.set_value(["V", "D", "I", "W", "E", "U"])).props('flat dense round size=sm')
                ui.button(icon='clear', on_click=lambda: self.level_select.set_value([])).props('flat dense round color=red size=sm')

            self.file_select = ui.select(options=sorted(list(unique_files)), value=app_state.filter_file, label="File", multiple=True, on_change=self.on_file_filter_change).classes(f"w-full {theme['bg_input']} {theme['text_primary']}")
            self.selects.append(self.file_select)
            self.function_select = ui.select(options=sorted(list(unique_functions)), value=app_state.filter_function, label="Function", multiple=True, on_change=self.on_function_filter_change).classes(f"w-full {theme['bg_input']} {theme['text_primary']}")
            self.selects.append(self.function_select)
            ui.separator().classes(f"my-4")
            ui.button("Clear Logs", on_click=self.on_clear_logs).classes('w-full bg-red-600 text-white rounded-none font-bold shadow-md')

        self.main_column = ui.column().classes(f"w-full h-screen p-0 overflow-hidden no-wrap {theme['bg_main']} {theme['text_primary']}")
        with self.main_column:
            self.header_row = ui.row().classes(f"w-full {theme['bg_header']} p-2 border-b {theme['border']} items-center shrink-0 gap-2 transition-colors duration-300")
            with self.header_row:
                ui.button(icon='menu', on_click=self.drawer.toggle).props('flat round dense')
                with ui.input(placeholder="Search logs... (* ?)", on_change=self.on_search_change).classes(f"grow {theme['bg_input']} {theme['text_primary']}").props('dense outlined square') as search:
                    self.inputs.append(search)
                    search.value = self.search_term
                    with search.add_slot('prepend'): ui.icon('search')
                    with search.add_slot('append'): ui.icon('close').props('cursor-pointer').on('click', lambda: search.set_value(""))
                ui.switch("Time", value=app_state.realtime_timestamp, on_change=lambda e: setattr(app_state, 'realtime_timestamp', e.value)).props('dense').tooltip("Real-time Timestamp")
                ui.switch("Scroll", value=app_state.auto_scroll, on_change=self.on_autoscroll_change).props('dense').tooltip("Auto-scroll")

            # Scroll Area with on_scroll listener
            self.scroll_area = ui.scroll_area(on_scroll=self.on_scroll).classes(f"w-full grow {theme['log_bg']} select-text")
            with self.scroll_area:
                with ui.column().classes('w-full min-h-full'):
                    self.log_container = ui.element('div').props(f'id="{self.log_container_id}"').classes('w-full flex flex-col select-text p-2')

            # Floating "Scroll to Top" Button
            with ui.column().classes('absolute right-8 bottom-24 z-50 gap-2'):
                self.scroll_top_btn = ui.button(icon='arrow_upward', on_click=self.scroll_to_top).props('round color=blue size=lg glossy').classes('hidden opacity-80 hover:opacity-100 transition-opacity')
                self.scroll_bottom_btn = ui.button(icon='arrow_downward', on_click=self.scroll_to_bottom).props('round color=blue size=lg glossy').classes('hidden opacity-80 hover:opacity-100 transition-opacity')

            self.footer_row = ui.row().classes(f"w-full {theme['bg_header']} p-2 border-t {theme['border']} items-center shrink-0 gap-2")
            with self.footer_row:
                ui.icon('terminal')
                self.cli_input = ui.input(placeholder="Send command...", on_change=None).classes(f"grow {theme['bg_input']} {theme['text_primary']}").props('dense outlined square')
                self.inputs.append(self.cli_input)
                self.cli_input.on('keydown.enter', self.send_cli_command)

                def handle_up():
                    if not app_state.cli_history: return
                    if self.history_index == -1: self.history_index = len(app_state.cli_history) - 1
                    else: self.history_index = max(0, self.history_index - 1)
                    self.cli_input.value = app_state.cli_history[self.history_index]
                def handle_down():
                    if not app_state.cli_history: return
                    if self.history_index == -1: return
                    self.history_index += 1
                    if self.history_index >= len(app_state.cli_history):
                        self.history_index = -1
                        self.cli_input.value = ""
                    else: self.cli_input.value = app_state.cli_history[self.history_index]
                self.cli_input.on('keydown.up', handle_up)
                self.cli_input.on('keydown.down', handle_down)
                ui.select(options=["LF", "CR", "CRLF"], value=app_state.cli_line_ending, on_change=lambda e: setattr(app_state, 'cli_line_ending', e.value)).props('dense options-dense borderless').classes(f"w-20")
                ui.button(icon='send', on_click=self.send_cli_command).props('flat round dense')

        ui.timer(0.2, self.update_loop)
        # Initial load
        ui.timer(0.5, lambda: asyncio.create_task(self.load_initial_view()), once=True)

@ui.page('/')
def main_page(client: Client):
    client.content.classes('p-0 m-0 gap-0')
    global serial_manager
    if serial_manager is None: serial_manager = SerialManager(on_log_received=handle_log)
    viewer = LogViewer()
    viewer.build_ui()

if __name__ in {"__main__", "__mp_main__"}:
    import sys
    is_bundled = getattr(sys, 'frozen', False)
    ui.run(title="SerialLens", port=8080, reload=False, native=False, show=False, window_size=(1000, 800))
