class LogEntry {
  final int? id;
  final String timestamp;
  final String level;
  final String file;
  final String function;
  final String message;
  final String original;
  final double arrivalTime;

  LogEntry({
    this.id,
    required this.timestamp,
    required this.level,
    required this.file,
    required this.function,
    required this.message,
    required this.original,
    required this.arrivalTime,
  });

  factory LogEntry.fromMap(Map<String, dynamic> map) {
    return LogEntry(
      id: map['id'] as int?,
      timestamp: map['timestamp'] as String,
      level: map['level'] as String,
      file: map['file'] as String,
      function: map['function'] as String,
      message: map['message'] as String,
      original: map['original'] as String,
      arrivalTime: (map['arrival_time'] as num).toDouble(),
    );
  }

  Map<String, dynamic> toMap() {
    return {
      if (id != null) 'id': id,
      'timestamp': timestamp,
      'level': level,
      'file': file,
      'function': function,
      'message': message,
      'original': original,
      'arrival_time': arrivalTime,
    };
  }

  LogEntry copyWith({
    int? id,
    String? timestamp,
    String? level,
    String? file,
    String? function,
    String? message,
    String? original,
    double? arrivalTime,
  }) {
    return LogEntry(
      id: id ?? this.id,
      timestamp: timestamp ?? this.timestamp,
      level: level ?? this.level,
      file: file ?? this.file,
      function: function ?? this.function,
      message: message ?? this.message,
      original: original ?? this.original,
      arrivalTime: arrivalTime ?? this.arrivalTime,
    );
  }

  String toFileFormat() {
    if (timestamp == "UNDEFINED") {
      final fileVal = file != "UNDEFINED" ? file : "UNDEFINED";
      return "[UNDEFINED][$level][$fileVal:0] UNDEFINED(): $message";
    }
    return original;
  }
}
