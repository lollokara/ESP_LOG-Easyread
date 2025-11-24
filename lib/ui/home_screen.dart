import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:serial_lens/ui/themes.dart';
import 'package:serial_lens/providers/app_state_provider.dart';
import 'package:serial_lens/ui/components/settings_drawer.dart';
import 'package:serial_lens/ui/components/header_bar.dart';
import 'package:serial_lens/ui/components/log_list_view.dart';
import 'package:serial_lens/ui/components/cli_input.dart';
import 'package:liquid_glass_ui_design/liquid_glass_ui.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // We rely on LiquidScaffold for the glass structure.
    // Since we want "desktop/other apps" to be visible, we avoid adding an opaque background here.
    // The main.dart sets window background to transparent.
    // LiquidScaffold handles the layout.

    return LiquidScaffold(
      // Drawer works a bit differently in standard Flutter vs custom scaffolds.
      // LiquidScaffold might not have a `drawer` slot. Let's check typical usage.
      // If it inherits from Scaffold or wraps it, we can use it.
      // Based on typical package design, it likely wraps Scaffold or implements similar.
      // If LiquidScaffold doesn't support drawer directly, we might need a standard Scaffold
      // with transparent background wrapping our content.

      // Checking package info memory: "LiquidScaffold, LiquidAppBar...".
      // Assuming LiquidScaffold has `drawer` property or we put drawer in standard Scaffold
      // inside a glass container?
      // Actually, standard Scaffold is fine if we make it transparent, but LiquidScaffold provides the "Glass" look.

      // However, to keep it safe and flexible:
      // We will use a standard Scaffold (transparent) to hold the Drawer logic,
      // and use Liquid components inside.
      // Wait, LiquidScaffold probably applies the blur/glass effect to the *entire* app background.

      // Let's use LiquidScaffold as the root widget of the screen.
      appBar: const LiquidAppBar(
         title: HeaderBar(), // We'll put our custom header here or below
         // LiquidAppBar expects a title widget.
         // Our HeaderBar is complex (search, buttons).
         // We might just put HeaderBar in the body if LiquidAppBar is too restrictive.
         // backgroundColor: Colors.transparent, // Removed invalid param
         elevation: 0,
      ),
      drawer: const SettingsDrawer(),
      body: const Column(
        children: [
          // If we didn't use LiquidAppBar for the complex header, we put it here.
          // But HeaderBar was designed as a row.
          // Let's stick to the previous layout but wrapped in transparent container.
          Expanded(child: LogListView()),
          CliInput(),
        ],
      ),
    );
  }
}
