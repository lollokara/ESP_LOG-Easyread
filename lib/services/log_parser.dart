import 'package:serial_lens/models/log_entry.dart';

class LogParser {
  // Regex based on: [TIME][LEVEL][FILE:LINE] FUNCTION(): MESSAGE
  // Dart regex is almost identical to Python
  static final RegExp _regexStandard = RegExp(r'^\[\s*(\d+)\]\[([A-Z])\]\[(.*?):(\d+)\]\s*(.*?)\(\):\s*(.*)$');

  // Secondary Regex for System Logs: D Component: Message
  static final RegExp _regexSystem = RegExp(r'^([VDIWE])\s+(?:\(\d+\)\s+)?([^\[\]\s:]+):\s+(.*)$');

  static LogEntry parse(String line) {
    final trimmed = line.trim();
    if (trimmed.isEmpty) {
      // In Dart we typically return nullable, but to match existing flow
      // where we usually ignore empty lines before calling parse or handle nulls,
      // let's return a special entry or assume caller checks.
      // But adhering to the logic:
      return _createUndefined(trimmed);
    }

    final now = DateTime.now().millisecondsSinceEpoch / 1000.0;

    // Try Standard ESP Log Format
    final match = _regexStandard.firstMatch(trimmed);
    if (match != null) {
      return LogEntry(
        timestamp: match.group(1) ?? "UNDEFINED",
        level: match.group(2) ?? "U",
        file: match.group(3) ?? "UNDEFINED",
        // group 4 is line number, skipped
        function: match.group(5) ?? "UNDEFINED",
        message: match.group(6) ?? "",
        original: trimmed,
        arrivalTime: now,
      );
    }

    // Try System Log Format
    final matchSys = _regexSystem.firstMatch(trimmed);
    if (matchSys != null) {
      return LogEntry(
        timestamp: "UNDEFINED",
        level: matchSys.group(1) ?? "U",
        file: matchSys.group(2) ?? "UNDEFINED",
        function: "UNDEFINED",
        message: matchSys.group(3) ?? "",
        original: trimmed,
        arrivalTime: now,
      );
    }

    // Fallback
    return _createUndefined(trimmed, now);
  }

  static LogEntry _createUndefined(String line, [double? time]) {
    return LogEntry(
      timestamp: "UNDEFINED",
      level: "U",
      file: "UNDEFINED",
      function: "UNDEFINED",
      message: line,
      original: line,
      arrivalTime: time ?? (DateTime.now().millisecondsSinceEpoch / 1000.0),
    );
  }
}
