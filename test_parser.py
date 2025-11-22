import unittest
from log_parser import LogParser

class TestLogParser(unittest.TestCase):
    def test_standard_log(self):
        line = "[12345][I][main.cpp:100] setup(): Starting up..."
        entry = LogParser.parse(line)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.timestamp, "12345")
        self.assertEqual(entry.level, "I")
        self.assertEqual(entry.file, "main.cpp")
        self.assertEqual(entry.function, "setup")
        self.assertEqual(entry.message, "Starting up...")

    def test_system_log(self):
        line = "I WiFi: Connected to AP"
        entry = LogParser.parse(line)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.level, "I")
        self.assertEqual(entry.file, "WiFi")
        self.assertEqual(entry.message, "Connected to AP")

    def test_undefined_log(self):
        line = "Just some random text"
        entry = LogParser.parse(line)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.level, "U")
        self.assertEqual(entry.message, "Just some random text")

if __name__ == '__main__':
    unittest.main()
