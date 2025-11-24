import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:serial_lens/providers/app_state_provider.dart';
import 'package:serial_lens/providers/log_provider.dart';
import 'package:serial_lens/ui/themes.dart';
import 'package:liquid_glass_ui_design/liquid_glass_ui.dart';

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
      // Keep background transparent or use LiquidContainer?
      // Using LiquidContainer for consistency with glass theme.
      // But HeaderBar removed background, maybe we should too?
      // Let's use LiquidContainer but with theme.bgHeader (which is semi-transparent)
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
      decoration: BoxDecoration(
         // Using transparent container but with border handled by parent or manual
         border: Border(top: BorderSide(color: theme.border.withOpacity(0.3))),
      ),
      child: Row(
        children: [
          Icon(Icons.terminal, color: theme.textSecondary),
          const SizedBox(width: 12),
          Expanded(
            child: RawKeyboardListener(
              focusNode: FocusNode(),
              onKey: (event) {
                if (event is RawKeyDownEvent) {
                   if (event.logicalKey.keyLabel == "Arrow Up") {
                     _navigateHistory(-1);
                   } else if (event.logicalKey.keyLabel == "Arrow Down") {
                     _navigateHistory(1);
                   }
                }
              },
              // LiquidTextField doesn't support focusNode, so we use a standard TextField wrapped in a glass container
              child: LiquidContainer(
                color: theme.bgInput,
                child: TextField(
                  controller: _controller,
                  focusNode: _focusNode,
                  style: TextStyle(color: theme.textPrimary, fontFamily: 'JetBrains Mono'),
                  decoration: InputDecoration(
                    hintText: "Send command...",
                    hintStyle: TextStyle(color: theme.textSecondary.withOpacity(0.5)),
                    border: InputBorder.none,
                    contentPadding: const EdgeInsets.symmetric(horizontal: 8),
                  ),
                  onSubmitted: (_) => _send(),
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
          // Line Ending Selector
          SizedBox(
            width: 80,
            child: LiquidDropdown<String>(
              value: appState.cliLineEnding,
              items: ["LF", "CR", "CRLF"].map((e) => DropdownMenuItem(value: e, child: Text(e))).toList(),
              onChanged: (v) => ref.read(appStateProvider.notifier).setCliLineEnding(v!),
              color: theme.bgInput,
              // dropdownColor removed
              // borderColor removed
            ),
          ),
          const SizedBox(width: 8),
          SizedBox(
            width: 40, height: 40,
            child: LiquidButton(
              color: theme.accent.withOpacity(0.2),
              onTap: _send,
              child: Icon(Icons.send, color: theme.accent, size: 20),
            ),
          )
        ],
      ),
    );
  }
}
