import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:serial_lens/providers/app_state_provider.dart';
import 'package:serial_lens/providers/log_provider.dart';
import 'package:serial_lens/ui/themes.dart';
import 'package:liquid_glass_ui_design/liquid_glass_ui.dart';

class HeaderBar extends ConsumerWidget {
  const HeaderBar({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context).extension<SerialThemeExtension>()!.data;
    final appState = ref.watch(appStateProvider);
    final filter = ref.watch(filterProvider);

    return Container(
      height: 60, // Slightly taller for liquid components
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
      // We remove manual background color to let Liquid/Glass handle it,
      // or rely on parent transparency.
      decoration: BoxDecoration(
        color: Colors.transparent, // Let underlying glass show
        border: Border(bottom: BorderSide(color: theme.border.withOpacity(0.3))),
      ),
      child: Row(
        children: [
          LiquidButton(
            width: 40,
            height: 40,
            backgroundColor: theme.bgInput,
            onTap: () => Scaffold.of(context).openDrawer(),
            child: Icon(Icons.menu, color: theme.textPrimary, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: LiquidTextField(
              hintText: "Search logs... (* ?)",
              textColor: theme.textPrimary,
              hintColor: theme.textSecondary.withOpacity(0.5),
              backgroundColor: theme.bgInput,
              onChanged: (val) => ref.read(filterProvider.notifier).setSearchTerm(val),
              prefixIcon: Icon(Icons.search, size: 18, color: theme.textSecondary),
              // We need to handle "clear" button manually or if LiquidTextField supports suffix
              suffixIcon: filter.searchTerm.isNotEmpty
                  ? GestureDetector(
                      onTap: () => ref.read(filterProvider.notifier).setSearchTerm(""),
                      child: Icon(Icons.close, size: 16, color: theme.textSecondary),
                    )
                  : null,
            ),
          ),
          const SizedBox(width: 12),
          _buildLiquidToggle(
            context,
            label: "Time",
            value: appState.realtimeTimestamp,
            onChanged: (v) => ref.read(appStateProvider.notifier).setRealtimeTimestamp(v),
            theme: theme,
          ),
          const SizedBox(width: 8),
          _buildLiquidToggle(
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

  Widget _buildLiquidToggle(BuildContext context, {
    required String label,
    required bool value,
    required Function(bool) onChanged,
    required SerialTheme theme,
  }) {
    return Row(
      children: [
        Text(label, style: TextStyle(color: theme.textSecondary, fontSize: 12)),
        const SizedBox(width: 8),
        SizedBox(
          height: 30,
          child: LiquidSwitch(
            value: value,
            onChanged: onChanged,
            activeColor: theme.accent,
            inactiveColor: theme.bgInput,
          ),
        ),
      ],
    );
  }
}
