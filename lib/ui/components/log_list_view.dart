import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:serial_lens/models/log_entry.dart';
import 'package:serial_lens/providers/app_state_provider.dart';
import 'package:serial_lens/providers/log_provider.dart';
import 'package:serial_lens/ui/themes.dart';
import 'package:intl/intl.dart';

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
        // Re-enable auto-scroll? Or let user do it via button?
        // Usually clicking "Scroll to Bottom" re-enables it.
      }
      if (_showScrollToBottom) setState(() => _showScrollToBottom = false);
    }
  }

  void _scrollToBottom() {
    if (_scrollController.hasClients) {
      _scrollController.jumpTo(_scrollController.position.maxScrollExtent);
      setState(() {
        _stickToBottom = true;
        _showScrollToBottom = false;
      });
      ref.read(appStateProvider.notifier).setAutoScroll(true);
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
              // Cache extent for smoother scrolling
              cacheExtent: 500,
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
          loading: () => Center(child: CircularProgressIndicator(color: theme.accent)),
          error: (err, stack) => Center(child: Text("Error: $err", style: const TextStyle(color: Colors.red))),
        ),

        // Scroll to Bottom FAB
        if (_showScrollToBottom)
          Positioned(
            right: 20,
            bottom: 20,
            child: FloatingActionButton(
              mini: true,
              backgroundColor: theme.accent,
              onPressed: _scrollToBottom,
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

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 1),
      decoration: BoxDecoration(
        border: Border(bottom: BorderSide(color: Colors.transparent)),
      ),
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
