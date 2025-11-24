import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:serial_lens/models/log_entry.dart';
import 'package:serial_lens/providers/app_state_provider.dart';
import 'package:serial_lens/providers/log_provider.dart';
import 'package:serial_lens/ui/themes.dart';
import 'package:intl/intl.dart';
import 'package:liquid_glass_ui_design/liquid_glass_ui.dart';

class LogListView extends ConsumerStatefulWidget {
  const LogListView({super.key});

  @override
  ConsumerState<LogListView> createState() => _LogListViewState();
}

class _LogListViewState extends ConsumerState<LogListView> {
  final ScrollController _scrollController = ScrollController();
  bool _stickToBottom = true;
  bool _showScrollToBottom = false;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
  }

  void _onScroll() {
    if (!_scrollController.hasClients) return;

    final maxScroll = _scrollController.position.maxScrollExtent;
    final currentScroll = _scrollController.position.pixels;

    // 1. Detect Stick to Bottom
    // Check if user scrolled away from bottom
    if (maxScroll - currentScroll > 50) {
      if (_stickToBottom) {
        setState(() => _stickToBottom = false);
        // Also disable auto-scroll in settings
        ref.read(appStateProvider.notifier).setAutoScroll(false);
      }
      if (!_showScrollToBottom) setState(() => _showScrollToBottom = true);
    } else {
      if (!_stickToBottom) {
        setState(() => _stickToBottom = true);
      }
      if (_showScrollToBottom) setState(() => _showScrollToBottom = false);
    }

    // 2. Detect Top Edge (Load Older)
    if (currentScroll < 100) { // Top threshold
       _handleLoadOlder();
    }

    // 3. Detect Bottom Edge (Load Newer - if not sticking)
    if (!_stickToBottom && (maxScroll - currentScroll < 100)) {
       _handleLoadNewer();
    }
  }

  Future<void> _handleLoadOlder() async {
    final notifier = ref.read(logProvider.notifier);
    final count = await notifier.loadOlderLogs();

    if (count > 0 && _scrollController.hasClients) {
      // Logic for preserving scroll position could go here.
    }
  }

  Future<void> _handleLoadNewer() async {
     await ref.read(logProvider.notifier).loadNewerLogs();
  }

  void _scrollToBottom() {
    if (_scrollController.hasClients) {
      _scrollController.jumpTo(_scrollController.position.maxScrollExtent);
      setState(() {
        _stickToBottom = true;
        _showScrollToBottom = false;
      });
      ref.read(appStateProvider.notifier).setAutoScroll(true);
      // Also ensure we load newer logs if we were far back
      ref.read(logProvider.notifier).loadNewerLogs();
    }
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context).extension<SerialThemeExtension>()!.data;
    final appState = ref.watch(appStateProvider);
    final logsAsync = ref.watch(logProvider);

    // Auto-scroll effect
    ref.listen(logProvider, (prev, next) {
      if (appState.autoScroll && _stickToBottom && _scrollController.hasClients) {
        // Use post frame callback to scroll after build
        WidgetsBinding.instance.addPostFrameCallback((_) {
            _scrollController.jumpTo(_scrollController.position.maxScrollExtent);
        });
      }
    });

    return Stack(
      children: [
        logsAsync.when(
          data: (logs) {
            if (logs.isEmpty) {
              return Center(child: Text("No logs", style: TextStyle(color: theme.textSecondary)));
            }

            return ListView.builder(
              controller: _scrollController,
              itemCount: logs.length,
              cacheExtent: 500,
              // Transparent background for ListView to see through window
              padding: const EdgeInsets.all(0),
              itemBuilder: (context, index) {
                final entry = logs[index];
                return _LogItem(
                  entry: entry,
                  theme: theme,
                  appState: appState,
                );
              },
            );
          },
          loading: () => Center(child: LiquidLoader(color: theme.accent)),
          error: (err, stack) => Center(child: Text("Error: $err", style: const TextStyle(color: Colors.red))),
        ),

        // Scroll to Bottom FAB
        if (_showScrollToBottom)
          Positioned(
            right: 20,
            bottom: 20,
            child: LiquidFAB(
              onPressed: _scrollToBottom, // Changed from onTap to onPressed
              // backgroundColor -> might be color or background
              color: theme.accent,
              child: const Icon(Icons.arrow_downward, color: Colors.white),
            ),
          )
      ],
    );
  }
}

class _LogItem extends StatelessWidget {
  final LogEntry entry;
  final SerialTheme theme;
  final AppState appState;

  const _LogItem({required this.entry, required this.theme, required this.appState});

  @override
  Widget build(BuildContext context) {
    Color levelColor = theme.textPrimary;
    switch (entry.level) {
      case "V": levelColor = theme.logV; break;
      case "D": levelColor = theme.logD; break;
      case "I": levelColor = theme.logI; break;
      case "W": levelColor = theme.logW; break;
      case "E": levelColor = theme.logE; break;
    }

    String tsStr = entry.timestamp;
    if (appState.realtimeTimestamp) {
      final dt = DateTime.fromMillisecondsSinceEpoch((entry.arrivalTime * 1000).toInt());
      tsStr = DateFormat('mm:ss.SSS').format(dt);
    }

    final fontSize = appState.fontSize;

    // We do NOT wrap each item in a heavy LiquidCard for performance.
    // However, we ensure the text color contrasts well with the semi-transparent background.
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 1),
      child: SelectableText.rich(
        TextSpan(
          style: TextStyle(fontFamily: 'JetBrains Mono', fontSize: fontSize, height: 1.2),
          children: [
             if (appState.visibleColumns['timestamp']!)
               TextSpan(text: "[$tsStr] ", style: TextStyle(color: theme.textSecondary)),
             if (appState.visibleColumns['level']!)
               TextSpan(text: "[${entry.level}] ", style: TextStyle(color: levelColor)),
             if (appState.visibleColumns['file']! && entry.file != "UNDEFINED")
               TextSpan(text: "[${entry.file}] ", style: const TextStyle(color: Colors.purpleAccent)),
             if (appState.visibleColumns['function']! && entry.function != "UNDEFINED")
               TextSpan(text: "${entry.function}() ", style: const TextStyle(color: Colors.orangeAccent)),
             if (appState.visibleColumns['message']!)
               TextSpan(text: entry.message, style: TextStyle(color: entry.level == 'E' ? theme.logE : theme.textPrimary)),
          ]
        ),
      ),
    );
  }
}
