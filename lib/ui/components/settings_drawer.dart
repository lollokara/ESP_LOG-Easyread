import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:serial_lens/providers/app_state_provider.dart';
import 'package:serial_lens/providers/log_provider.dart';
import 'package:serial_lens/ui/themes.dart';

class SettingsDrawer extends ConsumerWidget {
  const SettingsDrawer({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final appState = ref.watch(appStateProvider);
    final theme = Theme.of(context).extension<SerialThemeExtension>()!.data;
    final logNotifier = ref.read(logProvider.notifier);
    final filter = ref.watch(filterProvider);
    final filterNotifier = ref.read(filterProvider.notifier);
    final isConnected = ref.watch(logProvider).hasValue && logNotifier.serialService.isConnected;

    // Unique files/functions (fetch from notifier which caches them)
    final uniqueFiles = logNotifier.getUniqueFiles();
    final uniqueFunctions = logNotifier.getUniqueFunctions();
    final ports = logNotifier.serialService.getAvailablePorts();

    return Drawer(
      backgroundColor: theme.bgSidebar,
      child: Column(
        children: [
          // Header
          Container(
            padding: const EdgeInsets.all(16),
            alignment: Alignment.centerLeft,
            child: Text(
              "SerialLens",
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
                color: theme.textPrimary,
              ),
            ),
          ),
          const Divider(height: 1),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(12),
              children: [
                _buildSectionLabel("Appearance", theme),
                _buildDropdown<String>(
                  context,
                  label: "Theme",
                  value: appState.currentTheme,
                  items: ["Light", "Dark", "Cyberpunk", "Monokai", "Glass Light", "Glass Dark"],
                  onChanged: (val) => ref.read(appStateProvider.notifier).setTheme(val!),
                  theme: theme,
                ),
                const SizedBox(height: 8),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text("Font Size", style: TextStyle(color: theme.textSecondary)),
                    Row(
                      children: [
                        IconButton(
                          icon: const Icon(Icons.remove, size: 16),
                          onPressed: () => ref.read(appStateProvider.notifier).setFontSize(appState.fontSize - 1),
                          color: theme.textPrimary,
                        ),
                        Text("${appState.fontSize.toInt()}", style: TextStyle(color: theme.textPrimary)),
                        IconButton(
                          icon: const Icon(Icons.add, size: 16),
                          onPressed: () => ref.read(appStateProvider.notifier).setFontSize(appState.fontSize + 1),
                          color: theme.textPrimary,
                        ),
                      ],
                    ),
                  ],
                ),
                ExpansionTile(
                  title: Text("Columns", style: TextStyle(color: theme.textSecondary, fontSize: 14)),
                  collapsedIconColor: theme.textSecondary,
                  iconColor: theme.textPrimary,
                  children: appState.visibleColumns.entries.map((e) {
                    return CheckboxListTile(
                      title: Text(e.key, style: TextStyle(color: theme.textPrimary, fontSize: 12)),
                      value: e.value,
                      onChanged: (v) => ref.read(appStateProvider.notifier).toggleColumn(e.key, v!),
                      activeColor: theme.accent,
                      dense: true,
                      controlAffinity: ListTileControlAffinity.leading,
                    );
                  }).toList(),
                ),

                const Divider(),
                _buildSectionLabel("Connection", theme),
                _buildDropdown<String?>(
                  context,
                  label: "Port",
                  value: ports.contains(appState.port) ? appState.port : (ports.isNotEmpty ? ports.first : null),
                  items: ports,
                  onChanged: (val) => ref.read(appStateProvider.notifier).setPort(val),
                  theme: theme,
                ),
                const SizedBox(height: 8),
                _buildDropdown<int>(
                  context,
                  label: "Baud",
                  value: appState.baud,
                  items: [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600],
                  onChanged: (val) => ref.read(appStateProvider.notifier).setBaud(val!),
                  theme: theme,
                ),
                const SizedBox(height: 12),
                SwitchListTile(
                  title: Text("Connect", style: TextStyle(color: theme.textPrimary)),
                  value: isConnected,
                  onChanged: appState.mockMode ? null : (val) {
                    if (val) {
                      if (appState.port != null) {
                        logNotifier.connect(appState.port!, appState.baud);
                      }
                    } else {
                      logNotifier.disconnect();
                    }
                  },
                  activeColor: theme.accent,
                ),

                const Divider(),
                _buildSectionLabel("Logging", theme),
                _buildDropdown<String>(
                  context,
                  label: "Session Mode",
                  value: appState.sessionMode,
                  items: ["Auto-New", "Single"],
                  onChanged: (val) => ref.read(appStateProvider.notifier).setSessionMode(val!),
                  theme: theme,
                ),
                SwitchListTile(
                  title: Text("Mock Mode", style: TextStyle(color: theme.textPrimary)),
                  value: appState.mockMode,
                  onChanged: (val) => logNotifier.toggleMockMode(val),
                  activeColor: theme.accent,
                ),

                const Divider(),
                _buildSectionLabel("Filters", theme),
                _buildMultiSelect(
                  context,
                  label: "Levels",
                  options: ["V", "D", "I", "W", "E", "U"],
                  selected: filter.levels,
                  onChanged: filterNotifier.setLevels,
                  theme: theme
                ),
                const SizedBox(height: 8),
                _buildMultiSelect(
                  context,
                  label: "Files",
                  options: uniqueFiles,
                  selected: filter.files,
                  onChanged: filterNotifier.setFiles,
                  theme: theme
                ),
                const SizedBox(height: 8),
                _buildMultiSelect(
                  context,
                  label: "Functions",
                  options: uniqueFunctions,
                  selected: filter.functions,
                  onChanged: filterNotifier.setFunctions,
                  theme: theme
                ),

                const SizedBox(height: 20),
                ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.red,
                    foregroundColor: Colors.white,
                  ),
                  onPressed: logNotifier.clearLogs,
                  child: const Text("Clear Logs"),
                )
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSectionLabel(String label, SerialTheme theme) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8.0, top: 4.0),
      child: Text(
        label.toUpperCase(),
        style: TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.bold,
          color: theme.textSecondary,
        ),
      ),
    );
  }

  Widget _buildDropdown<T>(BuildContext context, {
    required String label,
    required T value,
    required List<T> items,
    required Function(T?) onChanged,
    required SerialTheme theme
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: TextStyle(color: theme.textSecondary, fontSize: 12)),
        Container(
          height: 40,
          padding: const EdgeInsets.symmetric(horizontal: 12),
          decoration: BoxDecoration(
            color: theme.bgInput,
            border: Border.all(color: theme.border),
            borderRadius: BorderRadius.circular(4),
          ),
          child: DropdownButtonHideUnderline(
            child: DropdownButton<T>(
              value: value,
              isExpanded: true,
              dropdownColor: theme.bgSidebar,
              style: TextStyle(color: theme.textPrimary, fontSize: 14),
              items: items.map((e) => DropdownMenuItem(
                value: e,
                child: Text("$e"),
              )).toList(),
              onChanged: onChanged,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildMultiSelect(BuildContext context, {
    required String label,
    required List<String> options,
    required List<String> selected,
    required Function(List<String>) onChanged,
    required SerialTheme theme
  }) {
     return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: TextStyle(color: theme.textSecondary, fontSize: 12)),
        InkWell(
          onTap: () async {
            // Simple dialog for multi-select
            await showDialog(
              context: context,
              builder: (ctx) => _MultiSelectDialog(
                options: options,
                selected: selected,
                onConfirm: onChanged,
                theme: theme
              )
            );
          },
          child: Container(
            height: 40,
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: theme.bgInput,
              border: Border.all(color: theme.border),
              borderRadius: BorderRadius.circular(4),
            ),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    selected.join(", "),
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(color: theme.textPrimary, fontSize: 12),
                  ),
                ),
                Icon(Icons.arrow_drop_down, color: theme.textSecondary),
              ],
            ),
          ),
        )
      ],
    );
  }
}

class _MultiSelectDialog extends StatefulWidget {
  final List<String> options;
  final List<String> selected;
  final Function(List<String>) onConfirm;
  final SerialTheme theme;

  const _MultiSelectDialog({required this.options, required this.selected, required this.onConfirm, required this.theme});

  @override
  State<_MultiSelectDialog> createState() => _MultiSelectDialogState();
}

class _MultiSelectDialogState extends State<_MultiSelectDialog> {
  late List<String> _current;

  @override
  void initState() {
    super.initState();
    _current = List.from(widget.selected);
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      backgroundColor: widget.theme.bgSidebar,
      title: Text("Select Items", style: TextStyle(color: widget.theme.textPrimary)),
      content: SizedBox(
        width: 300,
        height: 400,
        child: ListView(
          children: widget.options.map((e) {
             final isSelected = _current.contains(e);
             return CheckboxListTile(
               title: Text(e, style: TextStyle(color: widget.theme.textPrimary)),
               value: isSelected,
               activeColor: widget.theme.accent,
               onChanged: (val) {
                 setState(() {
                   if (val!) {
                     if (e == "ALL") _current = ["ALL"];
                     else {
                       _current.remove("ALL");
                       _current.add(e);
                     }
                   } else {
                     _current.remove(e);
                     if (_current.isEmpty) _current = ["ALL"];
                   }
                 });
               },
             );
          }).toList(),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text("Cancel"),
        ),
        TextButton(
          onPressed: () {
            widget.onConfirm(_current);
            Navigator.pop(context);
          },
          child: const Text("OK"),
        ),
      ],
    );
  }
}
