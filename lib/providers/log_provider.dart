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
  // We want the serial service to interact with the LogProvider's state or DB directly
  // But SerialService needs a callback.
  // We'll wire it up in the main LogNotifier or a separate coordination logic.
  // For now, let's just expose the class, and LogNotifier will initialize it.
  throw UnimplementedError("Use logProvider to access logs");
});

// The main provider for logs list
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
  final List<LogEntry> _liveBuffer = [];
  bool _initialized = false;

  // Available filter options cache
  final Set<String> _uniqueFiles = {"ALL"};
  final Set<String> _uniqueFunctions = {"ALL"};

  LogNotifier(this.ref, this.db, this.filter) : super(const AsyncValue.loading()) {
    _serialService = SerialService(onLogReceived: _handleLog);
    _init();
  }

  Future<void> _init() async {
    await db.init();
    // Start a default session if needed or load last
    // For now, let's create a new session on app start like Python code
    final sessionId = await db.createSession("Session ${DateTime.now()}", "App Start");
    _currentSessionId = sessionId;

    // Load initial logs
    _loadLogs();
    _initialized = true;
  }

  Future<void> _loadLogs() async {
    if (_currentSessionId == null) return;
    try {
      state = const AsyncValue.loading();
      final logs = await db.getLogs(
        _currentSessionId!,
        limit: 2000, // Initial load limit
        offset: 0, // From start? Or need last N? Python loads last N.
        // But for infinite scroll ListView, we usually just load a chunk.
        // Let's load the *last* 2000 logs if we are auto-scrolling, or first 2000?
        // Flutter ListView.builder can handle list efficiently.
        // If we want "stick to bottom", we usually load all into memory if it fits,
        // or we use a reverse list.
        // Given 2000 lines limit in Python DOM, we can probably hold more in Dart memory.
        // Let's just fetch the last 2000 for now.
        // But `getLogs` with offset 0 and limit 2000 fetches the *first* 2000 chronologically.
        // We need to know the total count to fetch the *last* 2000.
      );

      // Actually, to mimic the Python behavior of "Load Initial View":
      final total = await db.getTotalLogCount(_currentSessionId!,
        levelFilter: filter.levels,
        fileFilter: filter.files,
        functionFilter: filter.functions,
        searchTerm: filter.searchTerm
      );

      int startOffset = 0;
      if (total > 2000) {
        startOffset = total - 2000;
      }

      final initialLogs = await db.getLogs(
        _currentSessionId!,
        limit: 2000,
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

    // Insert into DB
    db.insertLog(_currentSessionId!, entry);

    // Update unique caches
    bool updatedFilters = false;
    if (entry.file != "UNDEFINED" && !_uniqueFiles.contains(entry.file)) {
      _uniqueFiles.add(entry.file);
      updatedFilters = true;
    }
    if (entry.function != "UNDEFINED" && !_uniqueFunctions.contains(entry.function)) {
      _uniqueFunctions.add(entry.function);
      updatedFilters = true;
    }

    // Check if entry matches current filters
    if (!_matchesFilter(entry)) return;

    // Add to state if loaded
    state.whenData((logs) {
      // Create new list to trigger notify
      final newLogs = [...logs, entry];
      // Prune if too large?
      // Python pruned from top if > 2000.
      // In Flutter we can handle more, but let's keep it sane, say 5000.
      if (newLogs.length > 5000) {
        newLogs.removeAt(0);
      }
      state = AsyncValue.data(newLogs);
    });
  }

  bool _matchesFilter(LogEntry entry) {
    if (!filter.levels.contains(entry.level)) return false;
    if (!filter.files.contains("ALL") && !filter.files.contains(entry.file)) return false;
    if (!filter.functions.contains("ALL") && !filter.functions.contains(entry.function)) return false;
    if (filter.searchTerm.isNotEmpty) {
      // Simple contains check for live logs, consistent with SQL LIKE logic approx
      // But for exact wildcard matching we'd need regex or fnmatch logic here too.
      // Let's just do a lower-case check for now or strict.
      // Python used `fnmatch` but SQL uses LIKE.
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
    // Just clear view
    state = const AsyncValue.data([]);
  }

  void refreshFilters() {
    // Trigger a reload based on new filters
    _loadLogs();
  }

  List<String> getUniqueFiles() => _uniqueFiles.toList()..sort();
  List<String> getUniqueFunctions() => _uniqueFunctions.toList()..sort();

  SerialService get serialService => _serialService;

  Future<void> loadOlderLogs() async {
    // This requires tracking the offset of the top log.
    // For MVP, we can implement if needed.
    // Flutter's ListView usually handles this by scrolling up and triggering a fetch.
    // But since we have `state` as a List in memory, we prepend to it.
  }
}
