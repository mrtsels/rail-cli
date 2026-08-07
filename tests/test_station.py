"""Unit tests for rail_cli.station (pure logic, no network).

Run: python3 -m unittest tests.test_station -v
"""
import unittest

from rail_cli import station


class TelecodeDetectionTest(unittest.TestCase):
    def test_three_letters(self):
        self.assertTrue(station.is_telecode("SZQ"))
        self.assertTrue(station.is_telecode("ioq"))  # lowercase ok

    def test_not_telecode(self):
        for bad in ["深圳", "深圳北", "G1", "SZ", "SZQQ", "S1Q", "szq!", ""]:
            self.assertFalse(station.is_telecode(bad), bad)


class MappingLookupTest(unittest.TestCase):
    def test_exact_name(self):
        self.assertEqual(station.telecode_of("深圳北"), "IOQ")
        self.assertEqual(station.telecode_of("北京南"), "VNP")
        self.assertEqual(station.telecode_of("上海虹桥"), "AOH")

    def test_trailing_zhan_suffix(self):
        self.assertEqual(station.telecode_of("深圳北站"), "IOQ")
        self.assertEqual(station.telecode_of("广州东站"), "GGQ")

    def test_unknown_name(self):
        self.assertIsNone(station.telecode_of("不存在的车站"))

    def test_mapping_has_no_code_conflicts(self):
        mapping = station.load_mapping()
        self.assertGreater(len(mapping), 3000)
        # every value is a 3-letter telecode
        for name, code in mapping.items():
            self.assertTrue(station.is_telecode(code), f"{name}: {code}")


if __name__ == "__main__":
    unittest.main()
