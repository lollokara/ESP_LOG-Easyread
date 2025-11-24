import 'package:sqflite/sqflite.dart';
import 'package:path_provider/path_provider.dart';
import 'package:path/path.dart';
import 'package:serial_lens/models/log_entry.dart';
import 'dart:io';

class DatabaseManager {
  static const String _dbName = "serial_logs.db";
  Database? _db;

  Future<void> init() async {
    if (_db != null) return;

    final Directory appDocDir;
    if (Platform.isMacOS) {
       // Comply with user memory about ~/Library/Application Support/SerialLens/
       // path_provider getApplicationSupportDirectory does exactly this on macOS
       appDocDir = await getApplicationSupportDirectory();
    } else {
       appDocDir = await getApplicationDocumentsDirectory();
    }

    final dbPath = join(appDocDir.path, _dbName);

    // Ensure directory exists
    try {
      await Directory(dirname(dbPath)).create(recursive: true);
    } catch (_) {}

    _db = await openDatabase(
      dbPath,
      version: 1,
      onCreate: (db, version) async {
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                start_time REAL,
                end_time REAL,
                log_count INTEGER DEFAULT 0,
                connection_info TEXT
            )
        """);

        await db.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                timestamp TEXT,
                arrival_time REAL,
                level TEXT,
                file TEXT,
                function TEXT,
                message TEXT,
                original TEXT,
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            )
        """);

        await db.execute("CREATE INDEX IF NOT EXISTS idx_logs_session ON logs(session_id)");
        await db.execute("CREATE INDEX IF NOT EXISTS idx_logs_arrival ON logs(arrival_time)");
        await db.execute("CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level)");
      },
      onConfigure: (db) async {
        await db.execute("PRAGMA journal_mode=WAL;");
      },
    );
  }

  Future<int> createSession(String name, String connectionInfo) async {
    final db = _db;
    if (db == null) throw Exception("DB not initialized");

    return await db.insert('sessions', {
      'name': name,
      'start_time': DateTime.now().millisecondsSinceEpoch / 1000.0,
      'end_time': null,
      'log_count': 0,
      'connection_info': connectionInfo
    });
  }

  Future<void> endSession(int sessionId) async {
    final db = _db;
    if (db == null) return;
    await db.update(
      'sessions',
      {'end_time': DateTime.now().millisecondsSinceEpoch / 1000.0},
      where: 'id = ?',
      whereArgs: [sessionId]
    );
  }

  Future<void> insertLog(int sessionId, LogEntry entry) async {
    final db = _db;
    if (db == null) return;

    await db.transaction((txn) async {
      await txn.insert('logs', {
        'session_id': sessionId,
        'timestamp': entry.timestamp,
        'arrival_time': entry.arrivalTime,
        'level': entry.level,
        'file': entry.file,
        'function': entry.function,
        'message': entry.message,
        'original': entry.original
      });
      // Updating count on every log might be heavy, but it's what the python code did.
      // We can optimize this later if needed.
      await txn.rawUpdate("UPDATE sessions SET log_count = log_count + 1 WHERE id = ?", [sessionId]);
    });
  }

  // High performance batch insert
  Future<void> insertLogsBatch(int sessionId, List<LogEntry> entries) async {
    if (entries.isEmpty) return;
    final db = _db;
    if (db == null) return;

    final batch = db.batch();
    for (var e in entries) {
      batch.insert('logs', {
        'session_id': sessionId,
        'timestamp': e.timestamp,
        'arrival_time': e.arrivalTime,
        'level': e.level,
        'file': e.file,
        'function': e.function,
        'message': e.message,
        'original': e.original
      });
    }
    batch.rawUpdate("UPDATE sessions SET log_count = log_count + ? WHERE id = ?", [entries.length, sessionId]);
    await batch.commit(noResult: true);
  }

  Future<List<Map<String, dynamic>>> getSessions() async {
    final db = _db;
    if (db == null) return [];
    return await db.query('sessions', orderBy: 'start_time DESC');
  }

  Future<void> deleteSession(int sessionId) async {
    final db = _db;
    if (db == null) return;
    await db.transaction((txn) async {
      await txn.delete('logs', where: 'session_id = ?', whereArgs: [sessionId]);
      await txn.delete('sessions', where: 'id = ?', whereArgs: [sessionId]);
    });
  }

  Future<void> deleteEmptySessions() async {
    final db = _db;
    if (db == null) return;
    await db.delete('sessions', where: 'log_count = 0');
  }

  Future<List<LogEntry>> getLogs(int sessionId, {
    int limit = 2000,
    int offset = 0,
    List<String>? levelFilter,
    List<String>? fileFilter,
    List<String>? functionFilter,
    String? searchTerm,
  }) async {
    final db = _db;
    if (db == null) return [];

    String where = "session_id = ?";
    List<dynamic> args = [sessionId];

    if (levelFilter != null && levelFilter.isNotEmpty) {
      where += " AND level IN (${List.filled(levelFilter.length, '?').join(',')})";
      args.addAll(levelFilter);
    }

    if (fileFilter != null && fileFilter.isNotEmpty && !fileFilter.contains("ALL")) {
      where += " AND file IN (${List.filled(fileFilter.length, '?').join(',')})";
      args.addAll(fileFilter);
    }

    if (functionFilter != null && functionFilter.isNotEmpty && !functionFilter.contains("ALL")) {
      where += " AND function IN (${List.filled(functionFilter.length, '?').join(',')})";
      args.addAll(functionFilter);
    }

    if (searchTerm != null && searchTerm.isNotEmpty) {
       // Logic to match Python's wildcard: * -> %, ? -> _
       String sqlPattern = searchTerm.replaceAll("*", "%").replaceAll("?", "_");
       if (!sqlPattern.contains("%") && !sqlPattern.contains("_")) {
         sqlPattern = "%$sqlPattern%";
       }
       where += " AND original LIKE ?";
       args.append(sqlPattern);
    }

    final List<Map<String, dynamic>> maps = await db.query(
      'logs',
      where: where,
      whereArgs: args,
      orderBy: 'id ASC',
      limit: limit,
      offset: offset,
    );

    return maps.map((e) => LogEntry.fromMap(e)).toList();
  }

  Future<int> getTotalLogCount(int sessionId, {
    List<String>? levelFilter,
    List<String>? fileFilter,
    List<String>? functionFilter,
    String? searchTerm,
  }) async {
    final db = _db;
    if (db == null) return 0;

    String where = "session_id = ?";
    List<dynamic> args = [sessionId];

    if (levelFilter != null && levelFilter.isNotEmpty) {
      where += " AND level IN (${List.filled(levelFilter.length, '?').join(',')})";
      args.addAll(levelFilter);
    }
    if (fileFilter != null && fileFilter.isNotEmpty && !fileFilter.contains("ALL")) {
      where += " AND file IN (${List.filled(fileFilter.length, '?').join(',')})";
      args.addAll(fileFilter);
    }
    if (functionFilter != null && functionFilter.isNotEmpty && !functionFilter.contains("ALL")) {
      where += " AND function IN (${List.filled(functionFilter.length, '?').join(',')})";
      args.addAll(functionFilter);
    }
    if (searchTerm != null && searchTerm.isNotEmpty) {
       String sqlPattern = searchTerm.replaceAll("*", "%").replaceAll("?", "_");
       if (!sqlPattern.contains("%") && !sqlPattern.contains("_")) {
         sqlPattern = "%$sqlPattern%";
       }
       where += " AND original LIKE ?";
       args.add(sqlPattern);
    }

    final result = await db.rawQuery("SELECT COUNT(*) as count FROM logs WHERE $where", args);
    return Sqflite.firstIntValue(result) ?? 0;
  }

  Future<List<String>> getUniqueFiles(int sessionId) async {
    final db = _db;
    if (db == null) return [];
    final result = await db.rawQuery("SELECT DISTINCT file FROM logs WHERE session_id = ? ORDER BY file", [sessionId]);
    return result.map((e) => e['file'] as String).where((f) => f != "UNDEFINED").toList();
  }

  Future<List<String>> getUniqueFunctions(int sessionId) async {
    final db = _db;
    if (db == null) return [];
    final result = await db.rawQuery("SELECT DISTINCT function FROM logs WHERE session_id = ? ORDER BY function", [sessionId]);
    return result.map((e) => e['function'] as String).where((f) => f != "UNDEFINED").toList();
  }
}

// Global accessor extension or provider will be used later
extension ListAppend on List<dynamic> {
  void append(dynamic val) => add(val);
}
