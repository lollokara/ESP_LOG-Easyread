import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:liquid_glass_ui_design/liquid_glass_ui.dart';

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
    this.isGlass = true, // Default to true as per request
    this.isDark = true,
  });
}

class SerialLensThemes {
  // All themes now use transparent backgrounds to allow "Liquid" glass effect
  // and desktop visibility.

  static final light = SerialTheme(
    name: "Light",
    bgMain: Colors.white.withOpacity(0.1), // Semi-transparent
    bgSidebar: const Color(0xFFF3F4F6).withOpacity(0.3),
    bgHeader: Colors.white.withOpacity(0.2),
    bgInput: Colors.white.withOpacity(0.3),
    textPrimary: const Color(0xFF1F2937),
    textSecondary: const Color(0xFF4B5563),
    border: const Color(0xFFD1D5DB).withOpacity(0.5),
    logHover: const Color(0xFFF3F4F6).withOpacity(0.4),
    logV: const Color(0xFF6B7280),
    logD: const Color(0xFF2563EB),
    logI: const Color(0xFF16A34A),
    logW: const Color(0xFFCA8A04),
    logE: const Color(0xFFDC2626),
    accent: Colors.blue,
    isDark: false,
    isGlass: true,
  );

  static final dark = SerialTheme(
    name: "Dark",
    bgMain: const Color(0xFF0F172A).withOpacity(0.1),
    bgSidebar: const Color(0xFF1E293B).withOpacity(0.3),
    bgHeader: const Color(0xFF1E293B).withOpacity(0.2),
    bgInput: const Color(0xFF0F172A).withOpacity(0.3),
    textPrimary: const Color(0xFFE5E7EB),
    textSecondary: const Color(0xFF9CA3AF),
    border: const Color(0xFF334155).withOpacity(0.5),
    logHover: const Color(0xFF1E293B).withOpacity(0.4),
    logV: const Color(0xFF9CA3AF),
    logD: const Color(0xFF60A5FA),
    logI: const Color(0xFF4ADE80),
    logW: const Color(0xFFFACC15),
    logE: const Color(0xFFF87171),
    accent: Colors.blueAccent,
    isDark: true,
    isGlass: true,
  );

  static final cyberpunk = SerialTheme(
    name: "Cyberpunk",
    bgMain: Colors.black.withOpacity(0.1),
    bgSidebar: const Color(0xFF121212).withOpacity(0.4),
    bgHeader: const Color(0xFF121212).withOpacity(0.3),
    bgInput: Colors.black.withOpacity(0.4),
    textPrimary: const Color(0xFF00FF9C),
    textSecondary: const Color(0xFFFF00FF),
    border: const Color(0xFF00FFFF).withOpacity(0.6),
    logHover: const Color(0xFF1A1A1A).withOpacity(0.5),
    logV: const Color(0xFF808080),
    logD: const Color(0xFF00FFFF),
    logI: const Color(0xFF00FF9C),
    logW: const Color(0xFFFFD700),
    logE: const Color(0xFFFF0055),
    accent: const Color(0xFF00FFFF),
    isDark: true,
    isGlass: true,
  );

  static final monokai = SerialTheme(
    name: "Monokai",
    bgMain: const Color(0xFF272822).withOpacity(0.1),
    bgSidebar: const Color(0xFF1E1F1C).withOpacity(0.4),
    bgHeader: const Color(0xFF1E1F1C).withOpacity(0.3),
    bgInput: const Color(0xFF272822).withOpacity(0.4),
    textPrimary: const Color(0xFFF8F8F2),
    textSecondary: const Color(0xFF75715E),
    border: const Color(0xFF75715E).withOpacity(0.5),
    logHover: const Color(0xFF3E3D32).withOpacity(0.5),
    logV: const Color(0xFF75715E),
    logD: const Color(0xFF66D9EF),
    logI: const Color(0xFFA6E22E),
    logW: const Color(0xFFFD971F),
    logE: const Color(0xFFF92672),
    accent: const Color(0xFFA6E22E),
    isDark: true,
    isGlass: true,
  );

  // Deprecated specific glass themes as all are now glass,
  // but keeping them mapped for backward compatibility of saved settings
  static final glassDark = dark.copyWith(name: "Glass Dark");
  static final glassLight = light.copyWith(name: "Glass Light");

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

  static LiquidTheme getLiquidTheme(SerialTheme t) {
    return LiquidTheme(
      primaryColor: t.bgSidebar, // Using sidebar color as primary "glass" color
      accentColor: t.accent,
      // textColor removed
      backgroundColor: t.bgMain,
      blurStrength: 20.0, // Strong blur for the glass look
      borderRadius: 12.0,
    );
  }

  static ThemeData getTheme(String name) {
    final t = getRawTheme(name);
    final base = t.isDark ? ThemeData.dark() : ThemeData.light();

    return base.copyWith(
      scaffoldBackgroundColor: Colors.transparent, // Always transparent for glass/window
      colorScheme: base.colorScheme.copyWith(
        primary: t.accent,
        background: Colors.transparent,
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
