import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:serial_lens/providers/app_state_provider.dart';
import 'package:serial_lens/providers/log_provider.dart';
import 'package:serial_lens/ui/themes.dart';

class CliInput extends ConsumerStatefulWidget {
  const CliInput({super.key});

  @override
  ConsumerState<CliInput> createState() => _CliInputState();
}

class _CliInputState extends ConsumerState<CliInput> {
  final TextEditingController _controller = TextEditingController();
  final FocusNode _focusNode = FocusNode();

  // Local history state
  final List<String> _history = [];
  int _historyIndex = -1;

  void _send() {
    final cmd = _controller.text;
    if (cmd.isEmpty) return;

    // Add to history
    if (_history.isEmpty || _history.last != cmd) {
      _history.add(cmd);
      if (_history.length > 50) _history.removeAt(0);
    }
    _historyIndex = -1;

    final appState = ref.read(appStateProvider);
    final ending = appState.cliLineEnding == "LF" ? "\n" : (appState.cliLineEnding == "CR" ? "\r" : "\r\n");
    final fullCmd = "$cmd$ending";

    // Send via SerialService
    ref.read(logProvider.notifier).serialService.write(fullCmd);

    _controller.clear();
    // Keep focus
    _focusNode.requestFocus();
  }

  void _handleKey(RawKeyEvent event) {
    // Handling Up/Down arrow for history is tricky in Flutter TextField directly
    // Usually requires a FocusNode KeyListener wrapper.
    // Implemented in build via KeyboardListener.
  }

  void _navigateHistory(int dir) {
    if (_history.isEmpty) return;

    if (_historyIndex == -1) {
       _historyIndex = _history.length - 1;
    } else {
       _historyIndex += dir;
    }

    if (_historyIndex < 0) _historyIndex = 0;
    if (_historyIndex >= _history.length) {
      _historyIndex = -1;
      _controller.clear();
      return;
    }

    _controller.text = _history[_historyIndex];
    _controller.selection = TextSelection.fromPosition(TextPosition(offset: _controller.text.length));
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context).extension<SerialThemeExtension>()!.data;
    final appState = ref.watch(appStateProvider);

    return Container(
      decoration: BoxDecoration(
        color: theme.bgHeader,
        border: Border(top: BorderSide(color: theme.border)),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      child: Row(
        children: [
          Icon(Icons.terminal, color: theme.textSecondary),
          const SizedBox(width: 8),
          Expanded(
            child: RawKeyboardListener(
              focusNode: FocusNode(), // Dummy node to capture keys before TextField?
              // Actually wrapping TextField in KeyboardListener works if TextField has focus
              onKey: (event) {
                if (event is RawKeyDownEvent) {
                   if (event.logicalKey.keyLabel == "Arrow Up") {
                     _navigateHistory(-1);
                   } else if (event.logicalKey.keyLabel == "Arrow Down") {
                     _navigateHistory(1);
                   }
                }
              },
              child: TextField(
                controller: _controller,
                focusNode: _focusNode,
                style: TextStyle(color: theme.textPrimary, fontFamily: 'JetBrains Mono'),
                decoration: InputDecoration(
                  hintText: "Send command...",
                  hintStyle: TextStyle(color: theme.textSecondary.withOpacity(0.5)),
                  border: InputBorder.none,
                ),
                onSubmitted: (_) => _send(),
              ),
            ),
          ),
          // Line Ending Selector
          DropdownButtonHideUnderline(
            child: DropdownButton<String>(
              value: appState.cliLineEnding,
              dropdownColor: theme.bgSidebar,
              style: TextStyle(color: theme.textSecondary, fontSize: 12),
              items: ["LF", "CR", "CRLF"].map((e) => DropdownMenuItem(value: e, child: Text(e))).toList(),
              onChanged: (v) => ref.read(appStateProvider.notifier).setCliLineEnding(v!),
            ),
          ),
          IconButton(
            icon: Icon(Icons.send, color: theme.accent),
            onPressed: _send,
          )
        ],
      ),
    );
  }
}
