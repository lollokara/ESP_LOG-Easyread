import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

// Persistence State (Survives Reloads)
class AppState {
  final String currentTheme;
  final double fontSize;
  final String? port;
  final int baud;
  final bool autoScroll;
  final bool autoReconnect;
  final bool saveToFile;
  final bool mockMode;
  final bool realtimeTimestamp;
  final String sessionMode;
  final String cliLineEnding;
  final Map<String, bool> visibleColumns;

  AppState({
    this.currentTheme = "Dark",
    this.fontSize = 14.0,
    this.port,
    this.baud = 115200,
    this.autoScroll = true,
    this.autoReconnect = false,
    this.saveToFile = false,
    this.mockMode = false,
    this.realtimeTimestamp = false,
    this.sessionMode = "Auto-New",
    this.cliLineEnding = "LF",
    this.visibleColumns = const {
      "timestamp": true,
      "level": true,
      "file": true,
      "function": true,
      "message": true
    },
  });

  AppState copyWith({
    String? currentTheme,
    double? fontSize,
    String? port,
    int? baud,
    bool? autoScroll,
    bool? autoReconnect,
    bool? saveToFile,
    bool? mockMode,
    bool? realtimeTimestamp,
    String? sessionMode,
    String? cliLineEnding,
    Map<String, bool>? visibleColumns,
  }) {
    return AppState(
      currentTheme: currentTheme ?? this.currentTheme,
      fontSize: fontSize ?? this.fontSize,
      port: port ?? this.port,
      baud: baud ?? this.baud,
      autoScroll: autoScroll ?? this.autoScroll,
      autoReconnect: autoReconnect ?? this.autoReconnect,
      saveToFile: saveToFile ?? this.saveToFile,
      mockMode: mockMode ?? this.mockMode,
      realtimeTimestamp: realtimeTimestamp ?? this.realtimeTimestamp,
      sessionMode: sessionMode ?? this.sessionMode,
      cliLineEnding: cliLineEnding ?? this.cliLineEnding,
      visibleColumns: visibleColumns ?? this.visibleColumns,
    );
  }
}

class AppStateNotifier extends StateNotifier<AppState> {
  AppStateNotifier() : super(AppState()) {
    _loadSettings();
  }

  Future<void> _loadSettings() async {
    final prefs = await SharedPreferences.getInstance();
    state = AppState(
      currentTheme: prefs.getString('current_theme') ?? "Dark",
      fontSize: prefs.getDouble('font_size') ?? 14.0,
      port: prefs.getString('port'),
      baud: prefs.getInt('baud') ?? 115200,
      cliLineEnding: prefs.getString('cli_line_ending') ?? "LF",
      // Other flags can be added similarly
    );
  }

  Future<void> _saveSettings() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('current_theme', state.currentTheme);
    await prefs.setDouble('font_size', state.fontSize);
    if (state.port != null) await prefs.setString('port', state.port!);
    await prefs.setInt('baud', state.baud);
    await prefs.setString('cli_line_ending', state.cliLineEnding);
  }

  void setTheme(String theme) {
    state = state.copyWith(currentTheme: theme);
    _saveSettings();
  }

  void setFontSize(double size) {
    state = state.copyWith(fontSize: size.clamp(8.0, 30.0));
    _saveSettings();
  }

  void setPort(String? port) {
    state = state.copyWith(port: port);
    _saveSettings();
  }

  void setBaud(int baud) {
    state = state.copyWith(baud: baud);
    _saveSettings();
  }

  void setAutoScroll(bool val) => state = state.copyWith(autoScroll: val);
  void setRealtimeTimestamp(bool val) => state = state.copyWith(realtimeTimestamp: val);
  void setCliLineEnding(String val) {
    state = state.copyWith(cliLineEnding: val);
    _saveSettings();
  }

  void toggleColumn(String col, bool visible) {
    final newCols = Map<String, bool>.from(state.visibleColumns);
    newCols[col] = visible;
    state = state.copyWith(visibleColumns: newCols);
  }

  void setSessionMode(String mode) => state = state.copyWith(sessionMode: mode);
  void setMockMode(bool val) => state = state.copyWith(mockMode: val);
}

final appStateProvider = StateNotifierProvider<AppStateNotifier, AppState>((ref) {
  return AppStateNotifier();
});
