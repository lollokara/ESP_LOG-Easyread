import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:serial_lens/providers/app_state_provider.dart';
import 'package:serial_lens/providers/log_provider.dart';
import 'package:serial_lens/ui/themes.dart';

class HeaderBar extends ConsumerWidget {
  const HeaderBar({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context).extension<SerialThemeExtension>()!.data;
    final appState = ref.watch(appStateProvider);
    final filter = ref.watch(filterProvider);

    return Container(
      height: 50,
      decoration: BoxDecoration(
        color: theme.bgHeader,
        border: Border(bottom: BorderSide(color: theme.border)),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 8),
      child: Row(
        children: [
          IconButton(
            icon: Icon(Icons.menu, color: theme.textPrimary),
            onPressed: () => Scaffold.of(context).openDrawer(),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Container(
              height: 36,
              decoration: BoxDecoration(
                color: theme.bgInput,
                border: Border.all(color: theme.border),
                borderRadius: BorderRadius.circular(4),
              ),
              child: Row(
                children: [
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                    child: Icon(Icons.search, size: 18, color: theme.textSecondary),
                  ),
                  Expanded(
                    child: TextField(
                      style: TextStyle(color: theme.textPrimary, fontSize: 13),
                      decoration: InputDecoration(
                        hintText: "Search logs... (* ?)",
                        hintStyle: TextStyle(color: theme.textSecondary.withOpacity(0.5)),
                        border: InputBorder.none,
                        isDense: true,
                        contentPadding: const EdgeInsets.symmetric(vertical: 10),
                      ),
                      onChanged: (val) => ref.read(filterProvider.notifier).setSearchTerm(val),
                    ),
                  ),
                  if (filter.searchTerm.isNotEmpty)
                    IconButton(
                      icon: Icon(Icons.close, size: 16, color: theme.textSecondary),
                      onPressed: () => ref.read(filterProvider.notifier).setSearchTerm(""),
                    )
                ],
              ),
            ),
          ),
          const SizedBox(width: 8),
          _buildToggle(
            context,
            label: "Time",
            value: appState.realtimeTimestamp,
            onChanged: (v) => ref.read(appStateProvider.notifier).setRealtimeTimestamp(v),
            theme: theme,
          ),
          const SizedBox(width: 8),
          _buildToggle(
            context,
            label: "Scroll",
            value: appState.autoScroll,
            onChanged: (v) => ref.read(appStateProvider.notifier).setAutoScroll(v),
            theme: theme,
          ),
        ],
      ),
    );
  }

  Widget _buildToggle(BuildContext context, {
    required String label,
    required bool value,
    required Function(bool) onChanged,
    required SerialTheme theme,
  }) {
    return Row(
      children: [
        Text(label, style: TextStyle(color: theme.textSecondary, fontSize: 12)),
        Switch(
          value: value,
          onChanged: onChanged,
          activeColor: theme.accent,
        ),
      ],
    );
  }
}
