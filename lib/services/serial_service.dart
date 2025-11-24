import 'dart:async';
import 'dart:io';
import 'dart:math';
import 'dart:typed_data';
import 'package:flutter_libserialport/flutter_libserialport.dart';
import 'package:serial_lens/services/log_parser.dart';
import 'package:serial_lens/models/log_entry.dart';

// Callback for received logs
typedef LogReceivedCallback = void Function(LogEntry entry);

class SerialService {
  SerialPort? _port;
  SerialPortReader? _reader;
  StreamSubscription? _subscription;

  bool _mockMode = false;
  Timer? _mockTimer;

  final LogReceivedCallback onLogReceived;
  bool saveToFile = false;
  IOSink? _fileSink;

  SerialService({required this.onLogReceived});

  List<String> getAvailablePorts() {
    return SerialPort.availablePorts;
  }

  bool get isConnected => _port != null && _port!.isOpen;
  bool get isMocking => _mockMode;

  Future<void> connect(String portName, int baudRate) async {
    disconnect(); // Ensure clean slate

    try {
      final port = SerialPort(portName);
      if (!port.openReadWrite()) {
        throw Exception("Failed to open port $portName");
      }

      final config = port.config;
      config.baudRate = baudRate;
      config.bits = 8;
      config.stopBits = 1;
      config.parity = 0; // None
      port.config = config;

      _port = port;

      _reader = SerialPortReader(port, timeout: 100);

      // We need to handle split packets.
      // The easiest way for now is to read line-by-line using a transform.
      // However, binary data might break standard LineSplitter.
      // Given the logs are text, we decode to UTF-8.

      _subscription = _reader!.stream.listen((data) {
        // buffer logic would go here if not using a line-splitter based approach
        // For simplicity in this port, we assume we can handle chunks and decode.
        // A robust implementation would use a persistent byte buffer.
        _handleData(data);
      }, onError: (e) {
        print("Serial Error: $e");
        disconnect();
      });

    } catch (e) {
      print("Connect Error: $e");
      rethrow;
    }
  }

  // A simple buffer to hold incomplete lines
  final List<int> _buffer = [];

  void _handleData(Uint8List data) {
    for (var byte in data) {
      if (byte == 10) { // Newline \n
         final line = String.fromCharCodes(_buffer);
         _buffer.clear();
         _processLine(line);
      } else {
        _buffer.add(byte);
      }
    }
  }

  void _processLine(String line) {
    final entry = LogParser.parse(line);
    onLogReceived(entry);

    if (saveToFile && _fileSink != null) {
      _fileSink!.writeln(entry.toFileFormat());
    }
  }

  void disconnect() {
    _subscription?.cancel();
    _subscription = null;

    if (_reader != null) {
      _reader!.close();
      _reader = null;
    }

    if (_port != null) {
      if (_port!.isOpen) _port!.close();
      _port!.dispose();
      _port = null;
    }

    _buffer.clear();
  }

  void setSaveToFile(bool enable, {String? path}) {
    saveToFile = enable;
    if (enable && path != null) {
      final file = File(path);
      _fileSink = file.openWrite(mode: FileMode.append);
    } else {
      _fileSink?.close();
      _fileSink = null;
    }
  }

  void write(String data) {
    if (_port == null || !_port!.isOpen) return;
    final bytes = Uint8List.fromList(data.codeUnits);
    _port!.write(bytes);
  }

  // --- Mock Mode ---

  void startMockMode() {
    if (_mockMode) return;
    _mockMode = true;

    final files = ["main.cpp", "wifi.cpp", "sensor.cpp", "preferences.cpp", "display.cpp"];
    final functions = ["setup", "loop", "connect", "read_data", "update_ui", "save_config", "init"];
    final levels = ["V", "D", "I", "W", "E"];
    final messages = [
      "Starting up...", "Connection failed", "Data received: 0xFE",
      "Battery level: 85%", "NVS Error: Key not found",
      "WiFi connected, IP: 192.168.1.123", "Rendering frame", "Watchdog reset"
    ];
    final random = Random();
    int counter = 0;

    _mockTimer = Timer.periodic(const Duration(milliseconds: 100), (timer) {
      final timestamp = (DateTime.now().millisecondsSinceEpoch % 100000).toString();
      final level = levels[random.nextInt(levels.length)];
      final file = files[random.nextInt(files.length)];
      final line = random.nextInt(500) + 10;
      final function = functions[random.nextInt(functions.length)];
      final msg = messages[random.nextInt(messages.length)];

      String raw;
      if (random.nextDouble() < 0.1) {
        raw = "Standard output message $counter";
      } else {
        raw = "[$timestamp][$level][$file:$line] $function(): $msg $counter";
      }

      _processLine(raw);
      counter++;
    });
  }

  void stopMockMode() {
    _mockMode = false;
    _mockTimer?.cancel();
    _mockTimer = null;
  }
}
