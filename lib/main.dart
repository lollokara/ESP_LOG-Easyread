import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:serial_lens/ui/home_screen.dart';
import 'package:serial_lens/providers/app_state_provider.dart';
import 'package:serial_lens/ui/themes.dart';
import 'package:window_manager/window_manager.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:liquid_glass_ui_design/liquid_glass_ui.dart';
import 'dart:io';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize Database Factory for Desktop
  if (Platform.isWindows || Platform.isLinux || Platform.isMacOS) {
    sqfliteFfiInit();
    databaseFactory = databaseFactoryFfi;
  }

  // Initialize Window Manager
  await windowManager.ensureInitialized();
  WindowOptions windowOptions = const WindowOptions(
    size: Size(1000, 800),
    center: true,
    backgroundColor: Colors.transparent,
    skipTaskbar: false,
    titleBarStyle: TitleBarStyle.normal,
  );
  windowManager.waitUntilReadyToShow(windowOptions, () async {
    await windowManager.show();
    await windowManager.focus();
  });

  runApp(const ProviderScope(child: SerialLensApp()));
}

class SerialLensApp extends ConsumerWidget {
  const SerialLensApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final appState = ref.watch(appStateProvider);
    final serialTheme = SerialLensThemes.getRawTheme(appState.currentTheme);
    final liquidTheme = SerialLensThemes.getLiquidTheme(serialTheme);

    return LiquidThemeProvider(
      theme: liquidTheme,
      child: MaterialApp(
        title: 'SerialLens',
        theme: SerialLensThemes.getTheme(appState.currentTheme),
        debugShowCheckedModeBanner: false,
        home: const HomeScreen(),
      ),
    );
  }
}
