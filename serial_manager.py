import serial
import serial.tools.list_ports
import threading
import time
import asyncio
from typing import Callable, List, Optional
from log_parser import LogParser, LogEntry

class SerialManager:
    def __init__(self, on_log_received: Callable[[LogEntry], None]):
        self.serial_port: Optional[serial.Serial] = None
        self.is_connected = False
        self.should_run = False
        self.on_log_received = on_log_received
        self.current_port = ""
        self.current_baud = 115200
        self.auto_reconnect = False
        self.save_to_file = False
        self.file_handle = None
        self.file_path = "session.log"
        self._thread = None

    def list_ports(self) -> List[str]:
        ports = serial.tools.list_ports.comports()
        return [p.device for p in ports]

    def connect(self, port: str, baud: int):
        if self.is_connected:
            self.disconnect()

        self.current_port = port
        self.current_baud = baud
        self.should_run = True

        try:
            self._open_serial()
            self._start_reading_thread()
            return True
        except Exception as e:
            print(f"Error connecting: {e}")
            return False

    def _open_serial(self):
        self.serial_port = serial.Serial(
            self.current_port,
            self.current_baud,
            timeout=1
        )
        self.is_connected = True

    def disconnect(self):
        self.should_run = False
        self.is_connected = False
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.serial_port = None
        self._close_file()

    def set_auto_reconnect(self, enable: bool):
        self.auto_reconnect = enable

    def set_save_to_file(self, enable: bool):
        self.save_to_file = enable
        if enable:
            # Create unique filename with timestamp
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            self.file_path = f"session_{timestamp}.log"
            self._open_file()
        else:
            self._close_file()

    def _open_file(self):
        if not self.file_handle:
            try:
                self.file_handle = open(self.file_path, "a", encoding="utf-8")
            except Exception as e:
                print(f"Error opening file: {e}")

    def _close_file(self):
        if self.file_handle:
            self.file_handle.close()
            self.file_handle = None

    def _start_reading_thread(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def _read_loop(self):
        buffer = bytearray()
        while self.should_run:
            if self.is_connected and self.serial_port and self.serial_port.is_open:
                try:
                    if self.serial_port.in_waiting > 0:
                        data = self.serial_port.read(self.serial_port.in_waiting)
                        buffer.extend(data)

                        while b'\n' in buffer:
                            idx = buffer.find(b'\n')
                            line_bytes = buffer[:idx+1]
                            buffer = buffer[idx+1:]

                            try:
                                line = line_bytes.decode('utf-8', errors='replace').strip()
                            except Exception:
                                line = str(line_bytes)

                            if not line:
                                continue

                            log_entry = LogParser.parse(line)
                            if log_entry:
                                self.on_log_received(log_entry)

                                if self.save_to_file and self.file_handle:
                                    self.file_handle.write(log_entry.to_file_format() + "\n")
                                    self.file_handle.flush()
                    else:
                        time.sleep(0.01)
                except (OSError, serial.SerialException) as e:
                    print(f"Serial error: {e}")
                    self.is_connected = False
                    try:
                        if self.serial_port:
                            self.serial_port.close()
                    except Exception:
                        pass
                    self.serial_port = None
                    buffer.clear()
            else:
                # Not connected
                if self.auto_reconnect and self.should_run:
                    # Try to reconnect
                    time.sleep(1)
                    print(f"Attempting to reconnect to {self.current_port}...")
                    try:
                        self._open_serial()
                        print("Reconnected!")
                    except Exception:
                        pass
                else:
                    time.sleep(0.1)
