from nicegui import ui

class State:
    def __init__(self):
        self.dark_mode = False

state = State()

@ui.page('/')
def index():
    dm = ui.dark_mode()
    # This is the suspicious line
    try:
        bg = dm.bind_value(state, 'dark_mode').map(lambda x: 'bg-black' if x else 'bg-white')
        ui.label(f"It worked: {bg}")
    except Exception as e:
        ui.label(f"Error: {e}")
        print(f"Caught expected error: {e}")

ui.run(port=8081, native=False, show=False)
