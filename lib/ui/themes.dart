import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

// --- Theme Data Classes ---

class SerialTheme {
  final String name;
  final Color bgMain;
  final Color bgSidebar;
  final Color bgHeader;
  final Color bgInput;
  final Color textPrimary;
  final Color textSecondary;
  final Color border;
  final Color logHover;
  final Color logV;
  final Color logD;
  final Color logI;
  final Color logW;
  final Color logE;
  final Color accent;
  final bool isGlass;
  final bool isDark;

  const SerialTheme({
    required this.name,
    required this.bgMain,
    required this.bgSidebar,
    required this.bgHeader,
    required this.bgInput,
    required this.textPrimary,
    required this.textSecondary,
    required this.border,
    required this.logHover,
    required this.logV,
    required this.logD,
    required this.logI,
    required this.logW,
    required this.logE,
    required this.accent,
    this.isGlass = false,
    this.isDark = true,
  });
}

class SerialLensThemes {
  static const light = SerialTheme(
    name: "Light",
    bgMain: Colors.white,
    bgSidebar: Color(0xFFF3F4F6), // gray-100
    bgHeader: Colors.white,
    bgInput: Colors.white,
    textPrimary: Color(0xFF1F2937), // gray-800
    textSecondary: Color(0xFF4B5563), // gray-600
    border: Color(0xFFD1D5DB), // gray-300
    logHover: Color(0xFFF3F4F6),
    logV: Color(0xFF6B7280), // gray-500
    logD: Color(0xFF2563EB), // blue-600
    logI: Color(0xFF16A34A), // green-600
    logW: Color(0xFFCA8A04), // yellow-600
    logE: Color(0xFFDC2626), // red-600
    accent: Colors.blue,
    isDark: false,
  );

  static const dark = SerialTheme(
    name: "Dark",
    bgMain: Color(0xFF0F172A), // slate-900
    bgSidebar: Color(0xFF1E293B), // slate-800
    bgHeader: Color(0xFF1E293B),
    bgInput: Color(0xFF0F172A),
    textPrimary: Color(0xFFE5E7EB), // gray-200
    textSecondary: Color(0xFF9CA3AF), // gray-400
    border: Color(0xFF334155), // slate-700
    logHover: Color(0xFF1E293B),
    logV: Color(0xFF9CA3AF),
    logD: Color(0xFF60A5FA), // blue-400
    logI: Color(0xFF4ADE80), // green-400
    logW: Color(0xFFFACC15), // yellow-400
    logE: Color(0xFFF87171), // red-400
    accent: Colors.blueAccent,
    isDark: true,
  );

  static const cyberpunk = SerialTheme(
    name: "Cyberpunk",
    bgMain: Colors.black,
    bgSidebar: Color(0xFF121212), // Very dark gray
    bgHeader: Color(0xFF121212),
    bgInput: Colors.black,
    textPrimary: Color(0xFF00FF9C), // Neon Green
    textSecondary: Color(0xFFFF00FF), // Neon Pink
    border: Color(0xFF00FFFF), // Cyan
    logHover: Color(0xFF1A1A1A),
    logV: Color(0xFF808080),
    logD: Color(0xFF00FFFF), // Cyan
    logI: Color(0xFF00FF9C), // Green
    logW: Color(0xFFFFD700), // Gold
    logE: Color(0xFFFF0055), // Hot Pink/Red
    accent: Color(0xFF00FFFF),
    isDark: true,
  );

  static const monokai = SerialTheme(
    name: "Monokai",
    bgMain: Color(0xFF272822),
    bgSidebar: Color(0xFF1E1F1C),
    bgHeader: Color(0xFF1E1F1C),
    bgInput: Color(0xFF272822),
    textPrimary: Color(0xFFF8F8F2),
    textSecondary: Color(0xFF75715E),
    border: Color(0xFF75715E),
    logHover: Color(0xFF3E3D32),
    logV: Color(0xFF75715E),
    logD: Color(0xFF66D9EF),
    logI: Color(0xFFA6E22E),
    logW: Color(0xFFFD971F),
    logE: Color(0xFFF92672),
    accent: Color(0xFFA6E22E),
    isDark: true,
  );

  static final glassDark = dark.copyWith(
    name: "Glass Dark",
    bgMain: Colors.transparent, // Handled by container
    bgSidebar: const Color(0x33000000), // More transparent (0x33 = ~20%)
    bgHeader: const Color(0x33000000),
    bgInput: const Color(0x22FFFFFF),
    isGlass: true,
  );

  static final glassLight = light.copyWith(
    name: "Glass Light",
    bgMain: Colors.transparent,
    bgSidebar: const Color(0x33FFFFFF),
    bgHeader: const Color(0x33FFFFFF),
    bgInput: const Color(0x22000000),
    isGlass: true,
  );

  static SerialTheme getRawTheme(String name) {
    switch (name) {
      case "Light": return light;
      case "Cyberpunk": return cyberpunk;
      case "Monokai": return monokai;
      case "Glass Dark": return glassDark;
      case "Glass Light": return glassLight;
      default: return dark;
    }
  }

  static ThemeData getTheme(String name) {
    final t = getRawTheme(name);
    final base = t.isDark ? ThemeData.dark() : ThemeData.light();

    return base.copyWith(
      scaffoldBackgroundColor: t.isGlass ? Colors.transparent : t.bgMain,
      colorScheme: base.colorScheme.copyWith(
        primary: t.accent,
        background: t.bgMain,
        surface: t.bgSidebar,
      ),
      textTheme: GoogleFonts.jetBrainsMonoTextTheme(base.textTheme).apply(
        bodyColor: t.textPrimary,
        displayColor: t.textPrimary,
      ),
      extensions: [
        SerialThemeExtension(t),
      ],
    );
  }
}

class SerialThemeExtension extends ThemeExtension<SerialThemeExtension> {
  final SerialTheme data;
  SerialThemeExtension(this.data);

  @override
  SerialThemeExtension copyWith({SerialTheme? data}) => SerialThemeExtension(data ?? this.data);

  @override
  SerialThemeExtension lerp(ThemeExtension<SerialThemeExtension>? other, double t) {
    if (other is! SerialThemeExtension) return this;
    return this;
  }
}

extension LogEntryCopy on SerialTheme {
  SerialTheme copyWith({
    String? name,
    Color? bgMain,
    Color? bgSidebar,
    Color? bgHeader,
    Color? bgInput,
    bool? isGlass,
  }) {
    return SerialTheme(
      name: name ?? this.name,
      bgMain: bgMain ?? this.bgMain,
      bgSidebar: bgSidebar ?? this.bgSidebar,
      bgHeader: bgHeader ?? this.bgHeader,
      bgInput: bgInput ?? this.bgInput,
      textPrimary: textPrimary,
      textSecondary: textSecondary,
      border: border,
      logHover: logHover,
      logV: logV,
      logD: logD,
      logI: logI,
      logW: logW,
      logE: logE,
      accent: accent,
      isGlass: isGlass ?? this.isGlass,
      isDark: isDark,
    );
  }
}
