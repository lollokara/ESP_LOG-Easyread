from nicegui import ui
from database import DatabaseManager
from storage_utils import get_db_path
import datetime
import csv
import io

class SessionManager:
    def __init__(self, db: DatabaseManager, on_load_session):
        self.db = db
        self.on_load_session = on_load_session
        self.dialog = None
        self.grid = None

    def open(self):
        with ui.dialog() as self.dialog, ui.card().classes('w-full max-w-4xl h-[80vh] flex flex-col'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label("Session Manager").classes('text-xl font-bold')
                ui.button(icon='close', on_click=self.dialog.close).props('flat round dense')

            ui.separator().classes('my-2')

            # Sessions Grid/List
            self.refresh_grid()

            self.dialog.open()

    def refresh_grid(self):
        if self.grid: self.grid.clear()

        sessions = self.db.get_sessions()

        columns = [
            {'name': 'id', 'label': 'ID', 'field': 'id', 'sortable': True, 'align': 'left'},
            {'name': 'name', 'label': 'Name', 'field': 'name', 'sortable': True, 'align': 'left'},
            {'name': 'start_time', 'label': 'Start Time', 'field': lambda r: self._format_ts(r['start_time']), 'sortable': True, 'align': 'left'},
            {'name': 'log_count', 'label': 'Logs', 'field': 'log_count', 'sortable': True, 'align': 'right'},
            {'name': 'actions', 'label': 'Actions', 'field': 'actions', 'align': 'center'}
        ]

        with ui.element('div').classes('grow w-full overflow-hidden') as container:
            self.grid = container

            # Using AG Grid or simple table? Quasar Table is good.
            # NiceGUI ui.table is easy.

            table = ui.table(columns=columns, rows=sessions, row_key='id', pagination=10).classes('w-full h-full')

            # Custom slot for actions
            table.add_slot('body-cell-actions', r'''
                <q-td key="actions" :props="props">
                    <q-btn icon="visibility" flat dense color="primary" @click="$parent.$emit('load', props.row)" tooltip="Load">
                        <q-tooltip>Load Session</q-tooltip>
                    </q-btn>
                    <q-btn icon="download" flat dense color="secondary" @click="$parent.$emit('export', props.row)">
                        <q-tooltip>Export CSV</q-tooltip>
                    </q-btn>
                    <q-btn icon="delete" flat dense color="negative" @click="$parent.$emit('delete', props.row)">
                        <q-tooltip>Delete</q-tooltip>
                    </q-btn>
                </q-td>
            ''')

            table.on('load', lambda e: self.load_session(e.args))
            table.on('delete', lambda e: self.delete_session(e.args))
            table.on('export', lambda e: self.export_session(e.args))

    def _format_ts(self, ts):
        if not ts: return ""
        return datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')

    def load_session(self, row):
        session_id = row['id']
        self.on_load_session(session_id)
        self.dialog.close()
        ui.notify(f"Loaded session: {row['name']}")

    def delete_session(self, row):
        session_id = row['id']
        self.db.delete_session(session_id)
        ui.notify(f"Deleted session: {row['name']}")
        self.dialog.close()
        self.open() # Re-open to refresh

    def export_session(self, row):
        session_id = row['id']
        logs = self.db.get_logs(session_id, limit=1000000) # Fetch all

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Timestamp", "Level", "File", "Function", "Message"])
        for log in logs:
            writer.writerow([log.timestamp, log.level, log.file, log.function, log.message])

        ui.download(output.getvalue().encode('utf-8'), filename=f"session_{session_id}.csv")
