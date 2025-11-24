import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:serial_lens/ui/themes.dart';
import 'package:serial_lens/providers/app_state_provider.dart';
import 'package:serial_lens/ui/components/settings_drawer.dart';
import 'package:serial_lens/ui/components/header_bar.dart';
import 'package:serial_lens/ui/components/log_list_view.dart';
import 'package:serial_lens/ui/components/cli_input.dart';
import 'dart:ui'; // For ImageFilter

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final themeName = ref.watch(appStateProvider).currentTheme;
    final themeData = SerialLensThemes.getRawTheme(themeName);

    // Background handling for Glass Themes
    Widget body = const Column(
      children: [
        HeaderBar(),
        Expanded(child: LogListView()),
        CliInput(),
      ],
    );

    if (themeData.isGlass) {
      body = Stack(
        children: [
          // Dynamic Gradient Background
          Positioned.fill(
            child: _GlassBackground(isDark: themeData.isDark),
          ),
          // Main Content
          Positioned.fill(
            child: body,
          ),
        ],
      );
    } else {
      // Solid background handled by Scaffold backgroundColor in main.dart
    }

    return Scaffold(
      drawer: const SettingsDrawer(),
      body: body,
    );
  }
}

class _GlassBackground extends StatefulWidget {
  final bool isDark;
  const _GlassBackground({required this.isDark});

  @override
  State<_GlassBackground> createState() => _GlassBackgroundState();
}

class _GlassBackgroundState extends State<_GlassBackground> {
  Offset mousePos = Offset.zero;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      onHover: (event) {
        setState(() {
          mousePos = event.position;
        });
      },
      child: Container(
        decoration: BoxDecoration(
          gradient: RadialGradient(
            center: Alignment(
              (mousePos.dx / MediaQuery.of(context).size.width) * 2 - 1,
              (mousePos.dy / MediaQuery.of(context).size.height) * 2 - 1,
            ),
            radius: 1.0,
            colors: widget.isDark
              ? [const Color(0xFF1a1a2e), Colors.black]
              : [const Color(0xFFe0eafc), const Color(0xFFcfdef3)],
          ),
        ),
      ),
    );
  }
}
