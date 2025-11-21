import re
from dataclasses import dataclass

@dataclass
class LogEntry:
    timestamp: str
    level: str
    file: str
    function: str
    message: str
    original: str

    def to_file_format(self) -> str:
        """
        Returns the log string formatted for file saving.
        If it was a valid log, it returns the original line.
        If it was undefined, it constructs a formatted string with placeholders.
        """
        if self.timestamp == "UNDEFINED":
            # Construct a formatted string that mimics the standard ESP log format
            # [TIME][LEVEL][FILE:LINE] FUNCTION(): MESSAGE
            file_val = self.file if self.file != "UNDEFINED" else "UNDEFINED"
            return f"[UNDEFINED][{self.level}][{file_val}:0] UNDEFINED(): {self.message}"
        return self.original

class LogParser:
    # Regex based on: [TIME][LEVEL][FILE:LINE] FUNCTION(): MESSAGE
    # [   199] -> \[\s*(\d+)\]
    # [E] -> \[(.)\]
    # [Preferences.cpp:483] -> \[(.*?):(\d+)\]
    # getString(): -> \s*(.*?)\(\):
    # nvs_get_str len fail... -> \s*(.*)

    REGEX = re.compile(r'^\[\s*(\d+)\]\[([A-Z])\]\[(.*?):(\d+)\]\s*(.*?)\(\):\s*(.*)$')

    # Secondary Regex for System Logs: D Component: Message
    # ^([VDIWE]) -> Level
    # \s+
    # (.*?): -> Component (mapped to File)
    # \s+
    # (.*)$ -> Message
    REGEX_SYSTEM = re.compile(r'^([VDIWE])\s+(.*?):\s+(.*)$')

    @staticmethod
    def parse(line: str) -> LogEntry:
        line = line.strip()
        if not line:
            return None

        # Try Standard ESP Log Format
        match = LogParser.REGEX.match(line)
        if match:
            return LogEntry(
                timestamp=match.group(1),
                level=match.group(2),
                file=match.group(3),
                # group 4 is line number, we skip it as per requirements
                function=match.group(5),
                message=match.group(6),
                original=line
            )

        # Try System Log Format
        match_sys = LogParser.REGEX_SYSTEM.match(line)
        if match_sys:
             return LogEntry(
                timestamp="UNDEFINED",
                level=match_sys.group(1),
                file=match_sys.group(2),
                function="UNDEFINED",
                message=match_sys.group(3),
                original=line
            )

        # Fallback
        return LogEntry(
            timestamp="UNDEFINED",
            level="U",
            file="UNDEFINED",
            function="UNDEFINED",
            message=line,
            original=line
        )
