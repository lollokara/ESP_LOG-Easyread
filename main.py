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

# Global backend state (shared across clients)
serial_manager = None
mock_mode = False
mock_thread = None

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

global_lock = threading.Lock()
global_logs = []
unique_files = {"ALL"}
unique_functions = {"ALL"}

def handle_log(entry: LogEntry):
    global global_logs, unique_files, unique_functions
    with global_lock:
        global_logs.append(entry)
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
        
        self.history_index = -1
        self.last_processed_index = 0
        self.html_logs_primary = deque(maxlen=2000)
        self.html_logs_secondary = deque(maxlen=500) 

        self.log_container_id_primary = f"log-container-primary-{id(self)}"
        self.log_container_id_secondary = f"log-container-secondary-{id(self)}"
        self.log_container_primary = None
        
        self.drawer = None
        self.main_column = None
        self.header_row = None
        self.footer_row = None
        self.scroll_area = None
        self.inputs = []
        self.buttons = []
        self.labels = []
        self.separators = []
        self.selects = []

    def get_theme(self):
        return THEMES.get(self.current_theme, THEMES["Dark"])

    def check_match(self, entry: LogEntry):
        matches_search = True
        if self.search_term:
            text_to_search = entry.original.lower()
            pattern = self.search_term.lower()
            if '*' in pattern or '?' in pattern:
                 if not fnmatch.fnmatch(text_to_search, f"*{pattern}*"): matches_search = False
            else:
                 if pattern not in text_to_search: matches_search = False
        if not matches_search: return 0
        if entry.level not in self.filter_level: return 2
        if "ALL" not in self.filter_file and entry.file not in self.filter_file: return 2
        if "ALL" not in self.filter_function and entry.function not in self.filter_function: return 2
        return 1

    async def update_loop(self):
        global global_logs
        try:
            if not self.log_container_primary or not self.log_container_primary.client.has_socket_connection: return
        except Exception: return

        try:
            with global_lock:
                current_len = len(global_logs)
                if current_len > self.last_processed_index:
                    new_entries = global_logs[self.last_processed_index:current_len]
                    self.last_processed_index = current_len
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

                if primary_chunk:
                    joined_html = "".join(primary_chunk)
                    js_html = json.dumps(joined_html)
                    cmd = f'window.logManager.append("{self.log_container_id_primary}", {js_html}, 2000, {str(self.auto_scroll).lower()})'
                    ui.run_javascript(cmd)

                if secondary_chunk:
                    joined_html = "".join(secondary_chunk)
                    js_html = json.dumps(joined_html)
                    cmd = f'window.logManager.append("{self.log_container_id_secondary}", {js_html}, 500, false)'
                    ui.run_javascript(cmd)
                    if not primary_chunk and self.auto_scroll and self.scroll_area:
                        self.scroll_area.scroll_to(percent=1.0)
        except Exception as e:
            print("Error in update_loop:")
            traceback.print_exc()

    def refresh_log_view(self):
        if not self.log_container_primary: return
        self.html_logs_primary.clear()
        self.html_logs_secondary.clear()
        with global_lock:
            current_len = len(global_logs)
            scan_start = max(0, current_len - 5000)
            entries_to_scan = global_logs[scan_start:]
            self.last_processed_index = current_len
        for entry in entries_to_scan:
            match_status = self.check_match(entry)
            if match_status == 1: self.html_logs_primary.append(self.format_log_html(entry, dimmed=False))
            elif match_status == 2: self.html_logs_secondary.append(self.format_log_html(entry, dimmed=True))
        while len(self.html_logs_primary) > 2000: self.html_logs_primary.popleft()
        while len(self.html_logs_secondary) > 500: self.html_logs_secondary.popleft()
        joined_html_p = "".join(self.html_logs_primary)
        js_html_p = json.dumps(joined_html_p)
        ui.run_javascript(f'window.logManager.setContent("{self.log_container_id_primary}", {js_html_p})')
        joined_html_s = "".join(self.html_logs_secondary)
        js_html_s = json.dumps(joined_html_s)
        ui.run_javascript(f'window.logManager.setContent("{self.log_container_id_secondary}", {js_html_s})')
        if self.auto_scroll and self.scroll_area: self.scroll_area.scroll_to(percent=1.0)

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
        return f"""<div class="log-line w-full flex gap-1 font-mono items-start no-wrap {theme['log_hover']} select-text {base_opacity} animate-fade-in" style="{font_style}">{inner_html}</div>"""

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
        if self.auto_scroll and self.scroll_area: self.scroll_area.scroll_to(percent=1.0)

    def on_search_change(self, e):
        self.search_term = e.value
        app_state.search_term = e.value
        self.refresh_log_view()
        
    def on_font_size_change(self, delta):
        self.font_size = max(8, min(30, self.font_size + delta))
        app_state.font_size = self.font_size
        self.refresh_log_view()
        
    def on_column_toggle(self, col_name, value):
        self.visible_columns[col_name] = value
        app_state.visible_columns = self.visible_columns
        self.refresh_log_view()

    def on_clear_logs(self):
        global global_logs
        with global_lock: global_logs.clear()
        self.html_logs_primary.clear()
        self.html_logs_secondary.clear()
        if self.log_container_primary: ui.run_javascript(f'window.logManager.setContent("{self.log_container_id_primary}", "")')
        if self.log_container_secondary: ui.run_javascript(f'window.logManager.setContent("{self.log_container_id_secondary}", "")')
        self.last_processed_index = 0

    def on_connect_toggle(self, e):
        port = self.port_select.value
        baud = int(self.baud_select.value)
        if e.value: 
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
            serial_manager.write(full_cmd.encode('utf-8'))
            ui.notify(f"Sent: {cmd}")
        elif mock_mode: ui.notify(f"Mock Sent: {cmd}")
        else: ui.notify("Not Connected", type='warning')
        self.cli_input.value = ""

    def on_theme_change(self, e):
        self.current_theme = e.value
        app_state.current_theme = e.value
        theme = self.get_theme()

        # Sync Quasar Dark Mode
        ui.dark_mode().value = (self.current_theme != "Light")

        # Update Main Layout
        self.main_column.classes(replace=f"w-full h-screen p-0 overflow-hidden no-wrap {theme['bg_main']} {theme['text_primary']}")
        self.drawer.classes(replace=f"q-pa-md {theme['bg_sidebar']} {theme['text_primary']} transition-all duration-300 border-r {theme['border']}")
        self.header_row.classes(replace=f"w-full {theme['bg_header']} p-2 border-b {theme['border']} items-center shrink-0 gap-2 transition-colors duration-300")
        self.footer_row.classes(replace=f"w-full {theme['bg_header']} p-2 border-t {theme['border']} items-center shrink-0 gap-2")
        self.scroll_area.classes(replace=f"w-full grow {theme['log_bg']} select-text")
        self.log_container_secondary.classes(replace=f"w-full flex flex-col select-text p-2 {theme['bg_sidebar']} border-t {theme['border']}")

        # Update Controls
        for inp in self.inputs: inp.classes(replace=f"grow {theme['bg_input']}").props('dense outlined square')
        for sel in self.selects: sel.classes(replace=f"w-full {theme['bg_input']}").props('dense outlined')
        
        self.refresh_log_view()

    def build_ui(self):
        # Initialize Quasar Dark Mode based on initial theme
        ui.dark_mode().value = (self.current_theme != "Light")

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
                        for(let i=0; i<countToRemove; i++) { removedHeight += el.children[i].offsetHeight; }
                    }
                    while (el.childElementCount > maxLines) { el.firstElementChild.remove(); }
                    if (!autoScroll && scrollTarget && removedHeight > 0) { scrollTarget.scrollTop -= removedHeight; }
                }
                if (autoScroll && scrollTarget) { scrollTarget.scrollTop = scrollTarget.scrollHeight; }
            },
            setContent: function(id, html) {
                const el = document.getElementById(id);
                if (el) el.innerHTML = html;
            }
        }
        </script>
        """)

        # 1. Drawer defined at top level
        with ui.left_drawer(value=True).classes(f"q-pa-md {theme['bg_sidebar']} {theme['text_primary']} transition-all duration-300 border-r {theme['border']}") as self.drawer:
            ui.markdown("### SerialLens").classes('font-bold')
            ui.label("Appearance").classes(f"text-xs font-bold mt-4")
            self.selects.append(ui.select(options=list(THEMES.keys()), value=self.current_theme, label="Theme", on_change=self.on_theme_change))
            
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
            self.port_select = ui.select(options=ports, value=current_port, label="Port").classes(f"w-full {theme['bg_input']}").props('dense outlined')
            self.selects.append(self.port_select)
            ui.button("Refresh", on_click=self.on_refresh_ports).classes(f"w-full mb-2 text-xs border").props('dense square outline')
            self.baud_select = ui.select(options=[9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600], value=app_state.baud, label="Baud")
            self.selects.append(self.baud_select)

            is_connected = serial_manager.is_connected if serial_manager else False
            self.connect_switch = ui.switch("Connect", value=is_connected, on_change=self.on_connect_toggle).classes('w-full')
            if mock_mode: self.connect_switch.disable()
            ui.checkbox("Auto-reconnect", value=serial_manager.auto_reconnect if serial_manager else False, on_change=lambda e: serial_manager.set_auto_reconnect(e.value))

            ui.separator().classes(f"my-4")
            ui.label("Logging").classes(f"text-xs font-bold")
            ui.checkbox("Save to File", value=serial_manager.save_to_file if serial_manager else False, on_change=lambda e: serial_manager.set_save_to_file(e.value))
            ui.switch("Mock Mode", value=mock_mode, on_change=self.on_mock_toggle)

            ui.separator().classes(f"my-4")
            ui.label("Filters").classes(f"text-xs font-bold")
            with ui.row().classes('w-full items-center no-wrap gap-1'):
                self.level_select = ui.select(options=["V", "D", "I", "W", "E", "U"], value=app_state.filter_level, label="Level", multiple=True, on_change=self.on_level_filter_change).classes(f"grow {theme['bg_input']}").props('use-chips dense outlined')
                ui.button(icon='select_all', on_click=lambda: self.level_select.set_value(["V", "D", "I", "W", "E", "U"])).props('flat dense round size=sm')
                ui.button(icon='clear', on_click=lambda: self.level_select.set_value([])).props('flat dense round color=red size=sm')

            self.file_select = ui.select(options=sorted(list(unique_files)), value=app_state.filter_file, label="File", multiple=True, on_change=self.on_file_filter_change)
            self.selects.append(self.file_select)
            self.function_select = ui.select(options=sorted(list(unique_functions)), value=app_state.filter_function, label="Function", multiple=True, on_change=self.on_function_filter_change)
            self.selects.append(self.function_select)
            ui.separator().classes(f"my-4")
            ui.button("Clear Logs", on_click=self.on_clear_logs).classes('w-full bg-red-600 text-white rounded-none font-bold shadow-md')

        # 2. Main Column defined at top level, NOT containing the drawer
        self.main_column = ui.column().classes(f"w-full h-screen p-0 overflow-hidden no-wrap {theme['bg_main']} {theme['text_primary']}")
        with self.main_column:
            self.header_row = ui.row().classes(f"w-full {theme['bg_header']} p-2 border-b {theme['border']} items-center shrink-0 gap-2 transition-colors duration-300")
            with self.header_row:
                ui.button(icon='menu', on_click=self.drawer.toggle).props('flat round dense')
                with ui.input(placeholder="Search logs... (* ?)", on_change=self.on_search_change).classes(f"grow {theme['bg_input']}").props('dense outlined square') as search:
                    self.inputs.append(search)
                    search.value = self.search_term
                    with search.add_slot('prepend'): ui.icon('search')
                    with search.add_slot('append'): ui.icon('close').props('cursor-pointer').on('click', lambda: search.set_value(""))
                ui.switch("Time", value=app_state.realtime_timestamp, on_change=lambda e: setattr(app_state, 'realtime_timestamp', e.value)).props('dense').tooltip("Real-time Timestamp")
                ui.switch("Scroll", value=app_state.auto_scroll, on_change=self.on_autoscroll_change).props('dense').tooltip("Auto-scroll")

            self.scroll_area = ui.scroll_area().classes(f"w-full grow {theme['log_bg']} select-text")
            with self.scroll_area:
                with ui.column().classes('w-full min-h-full'):
                    self.log_container_primary = ui.element('div').props(f'id="{self.log_container_id_primary}"').classes('w-full flex flex-col select-text p-2')
                    ui.separator().classes(f"my-4 opacity-30")
                    ui.label("Filtered Matches (Search Only)").classes(f"text-xs ml-2")
                    self.log_container_secondary = ui.element('div').props(f'id="{self.log_container_id_secondary}"').classes(f"w-full flex flex-col select-text p-2 {theme['bg_sidebar']} border-t {theme['border']}")

            self.footer_row = ui.row().classes(f"w-full {theme['bg_header']} p-2 border-t {theme['border']} items-center shrink-0 gap-2")
            with self.footer_row:
                ui.icon('terminal')
                self.cli_input = ui.input(placeholder="Send command...", on_change=None).classes(f"grow {theme['bg_input']}").props('dense outlined square')
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

@ui.page('/')
def main_page(client: Client):
    global serial_manager
    if serial_manager is None: serial_manager = SerialManager(on_log_received=handle_log)
    viewer = LogViewer()
    viewer.build_ui()

if __name__ in {"__main__", "__mp_main__"}:
    import sys
    is_bundled = getattr(sys, 'frozen', False)
    ui.run(title="SerialLens", port=8080, reload=False, native=False, show=False, window_size=(1000, 800))
