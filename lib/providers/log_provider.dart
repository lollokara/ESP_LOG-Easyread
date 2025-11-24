import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:serial_lens/services/database_manager.dart';
import 'package:serial_lens/models/log_entry.dart';
import 'package:serial_lens/services/serial_service.dart';
import 'package:serial_lens/providers/app_state_provider.dart';

// Filter State
class FilterState {
  final List<String> levels;
  final List<String> files;
  final List<String> functions;
  final String searchTerm;

  FilterState({
    this.levels = const ["V", "D", "I", "W", "E", "U"],
    this.files = const ["ALL"],
    this.functions = const ["ALL"],
    this.searchTerm = "",
  });

  FilterState copyWith({
    List<String>? levels,
    List<String>? files,
    List<String>? functions,
    String? searchTerm,
  }) {
    return FilterState(
      levels: levels ?? this.levels,
      files: files ?? this.files,
      functions: functions ?? this.functions,
      searchTerm: searchTerm ?? this.searchTerm,
    );
  }
}

final filterProvider = StateNotifierProvider<FilterNotifier, FilterState>((ref) {
  return FilterNotifier();
});

class FilterNotifier extends StateNotifier<FilterState> {
  FilterNotifier() : super(FilterState());

  void setLevels(List<String> levels) => state = state.copyWith(levels: levels);

  void setFiles(List<String> files) {
    state = state.copyWith(files: _handleSmartAll(files, state.files));
  }

  void setFunctions(List<String> functions) {
    state = state.copyWith(functions: _handleSmartAll(functions, state.functions));
  }

  void setSearchTerm(String term) => state = state.copyWith(searchTerm: term);

  List<String> _handleSmartAll(List<String> newVal, List<String> currentVal) {
    if (newVal.isEmpty) return ["ALL"];
    if (currentVal.contains("ALL") && newVal.length > currentVal.length) {
      // User selected something else while ALL was selected -> Remove ALL
      return newVal.where((e) => e != "ALL").toList();
    } else if (!currentVal.contains("ALL") && newVal.contains("ALL")) {
      // User selected ALL -> Remove everything else
      return ["ALL"];
    }
    return newVal;
  }
}

// Log Manager
final dbProvider = Provider((ref) => DatabaseManager());

final serialServiceProvider = Provider((ref) {
  throw UnimplementedError("Use logProvider to access logs");
});

final logProvider = StateNotifierProvider<LogNotifier, AsyncValue<List<LogEntry>>>((ref) {
  final db = ref.watch(dbProvider);
  final filter = ref.watch(filterProvider);
  return LogNotifier(ref, db, filter);
});

class LogNotifier extends StateNotifier<AsyncValue<List<LogEntry>>> {
  final Ref ref;
  final DatabaseManager db;
  final FilterState filter;
  late final SerialService _serialService;

  int? _currentSessionId;

  // Windowing State
  int _dbOffset = 0; // The offset of the FIRST log in our current list relative to the DB result set
  final int _windowSize = 2000; // Max logs to keep in memory/list

  // Available filter options cache
  final Set<String> _uniqueFiles = {"ALL"};
  final Set<String> _uniqueFunctions = {"ALL"};

  bool _fetching = false;

  LogNotifier(this.ref, this.db, this.filter) : super(const AsyncValue.loading()) {
    _serialService = SerialService(onLogReceived: _handleLog);
    _init();
  }

  Future<void> _init() async {
    await db.init();
    final sessionId = await db.createSession("Session ${DateTime.now()}", "App Start");
    _currentSessionId = sessionId;

    // Load initial logs
    _loadInitialView();
  }

  Future<void> _loadInitialView() async {
    if (_currentSessionId == null) return;
    try {
      state = const AsyncValue.loading();

      final total = await db.getTotalLogCount(_currentSessionId!,
        levelFilter: filter.levels,
        fileFilter: filter.files,
        functionFilter: filter.functions,
        searchTerm: filter.searchTerm
      );

      // Load last N logs
      int startOffset = 0;
      if (total > _windowSize) {
        startOffset = total - _windowSize;
      }
      _dbOffset = startOffset;

      final initialLogs = await db.getLogs(
        _currentSessionId!,
        limit: _windowSize,
        offset: startOffset,
        levelFilter: filter.levels,
        fileFilter: filter.files,
        functionFilter: filter.functions,
        searchTerm: filter.searchTerm
      );

      state = AsyncValue.data(initialLogs);

    } catch (e, stack) {
      state = AsyncValue.error(e, stack);
    }
  }

  void _handleLog(LogEntry entry) {
    if (_currentSessionId == null) return;

    // 1. Always insert into DB
    db.insertLog(_currentSessionId!, entry);

    // 2. Update unique caches
    if (entry.file != "UNDEFINED" && !_uniqueFiles.contains(entry.file)) {
      _uniqueFiles.add(entry.file);
    }
    if (entry.function != "UNDEFINED" && !_uniqueFunctions.contains(entry.function)) {
      _uniqueFunctions.add(entry.function);
    }

    // 3. Update UI List ONLY if AutoScroll is ON (Live Mode)
    final autoScroll = ref.read(appStateProvider).autoScroll;

    if (autoScroll) {
      // Check if entry matches current filters
      if (!_matchesFilter(entry)) return;

      state.whenData((logs) {
        final newLogs = [...logs, entry];

        // Prune from top if too large (keep window sliding forward)
        if (newLogs.length > _windowSize) {
          final removedCount = newLogs.length - _windowSize;
          newLogs.removeRange(0, removedCount);
          _dbOffset += removedCount; // Our window start moved forward in the DB
        }

        state = AsyncValue.data(newLogs);
      });
    } else {
      // History Mode: Do NOT update state.
      // The user is looking at a static window.
      // New logs are in DB but not in our list.
      // If user scrolls down later, we fetch them.
    }
  }

  bool _matchesFilter(LogEntry entry) {
    if (!filter.levels.contains(entry.level)) return false;
    if (!filter.files.contains("ALL") && !filter.files.contains(entry.file)) return false;
    if (!filter.functions.contains("ALL") && !filter.functions.contains(entry.function)) return false;
    if (filter.searchTerm.isNotEmpty) {
      if (!entry.original.toLowerCase().contains(filter.searchTerm.toLowerCase())) return false;
    }
    return true;
  }

  // Public Actions

  Future<void> connect(String port, int baud) async {
    final appState = ref.read(appStateProvider);
    if (appState.sessionMode == "Auto-New") {
       if (_currentSessionId != null) await db.endSession(_currentSessionId!);
       _currentSessionId = await db.createSession("Session ${DateTime.now()}", "$port@$baud");
       state = const AsyncValue.data([]);
       _uniqueFiles.clear(); _uniqueFiles.add("ALL");
       _uniqueFunctions.clear(); _uniqueFunctions.add("ALL");
       _dbOffset = 0;
    }

    ref.read(appStateProvider.notifier).setPort(port);
    ref.read(appStateProvider.notifier).setBaud(baud);
    await _serialService.connect(port, baud);
  }

  void disconnect() {
    _serialService.disconnect();
  }

  void toggleMockMode(bool enable) {
    if (enable) _serialService.startMockMode();
    else _serialService.stopMockMode();
    ref.read(appStateProvider.notifier).setMockMode(enable);
  }

  void clearLogs() {
    state = const AsyncValue.data([]);
    _dbOffset = 0; // But wait, DB isn't cleared.
    // Usually "Clear Logs" means clear the view.
    // If we reload from DB, we might see them again unless we mark a "start_time".
    // For now, assume view clear.
  }

  void refreshFilters() {
    _loadInitialView();
  }

  List<String> getUniqueFiles() => _uniqueFiles.toList()..sort();
  List<String> getUniqueFunctions() => _uniqueFunctions.toList()..sort();

  SerialService get serialService => _serialService;

  Future<int> loadOlderLogs() async {
    if (_fetching || _currentSessionId == null || _dbOffset <= 0) return 0;
    _fetching = true;

    try {
      final int fetchCount = 500;
      final int targetOffset = (_dbOffset - fetchCount) < 0 ? 0 : (_dbOffset - fetchCount);
      final int realLimit = _dbOffset - targetOffset;

      if (realLimit <= 0) return 0;

      final olderLogs = await db.getLogs(
        _currentSessionId!,
        limit: realLimit,
        offset: targetOffset,
        levelFilter: filter.levels,
        fileFilter: filter.files,
        functionFilter: filter.functions,
        searchTerm: filter.searchTerm
      );

      if (olderLogs.isNotEmpty) {
        state.whenData((currentLogs) {
          final newLogs = [...olderLogs, ...currentLogs];
          // Prune bottom if too big (sliding window back)
          if (newLogs.length > _windowSize) {
             newLogs.removeRange(_windowSize, newLogs.length);
             // Note: removing from bottom doesn't affect _dbOffset start position
             // BUT it creates a gap at the end. That's fine.
          }
          state = AsyncValue.data(newLogs);
          _dbOffset = targetOffset;
        });
      }
      return olderLogs.length;
    } finally {
      _fetching = false;
    }
  }

  Future<int> loadNewerLogs() async {
    if (_fetching || _currentSessionId == null) return 0;

    final currentLen = state.value?.length ?? 0;
    if (currentLen == 0) return 0;

    // We want logs starting after our current last log.
    // Our list starts at _dbOffset and has currentLen items.
    // So next log is at _dbOffset + currentLen.

    _fetching = true;
    try {
      final start = _dbOffset + currentLen;
      final fetchCount = 500;

      final newerLogs = await db.getLogs(
        _currentSessionId!,
        limit: fetchCount,
        offset: start,
        levelFilter: filter.levels,
        fileFilter: filter.files,
        functionFilter: filter.functions,
        searchTerm: filter.searchTerm
      );

      if (newerLogs.isNotEmpty) {
         state.whenData((currentLogs) {
           final newLogs = [...currentLogs, ...newerLogs];
           // Prune top if too big (sliding window forward)
           if (newLogs.length > _windowSize) {
             final removed = newLogs.length - _windowSize;
             newLogs.removeRange(0, removed);
             _dbOffset += removed;
           }
           state = AsyncValue.data(newLogs);
         });
      }
      return newerLogs.length;
    } finally {
      _fetching = false;
    }
  }
}
