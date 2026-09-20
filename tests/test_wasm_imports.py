"""The import gate must reject foreign, missing and duplicate imports."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from wasm_imports import EXPECTED_IMPORTS, validate_plugin


def uint(value):
    result = bytearray()
    while value >= 128:
        result.append((value & 127) | 128)
        value >>= 7
    return bytes(result) + bytes([value])


def wasm(names):
    def string(value):
        data = value.encode()
        return uint(len(data)) + data
    payload = uint(len(names)) + b''.join(
        string(module) + string(name) + b'\x00\x00' for module, name in names)
    return b'\x00asm\x01\x00\x00\x00\x01\x04\x01\x60\x00\x00\x02' + uint(len(payload)) + payload


class ImportTests(unittest.TestCase):
    def test_allowlist_and_cli_exit_status(self):
        expected = sorted(EXPECTED_IMPORTS)
        cases = [(wasm(expected), True), (wasm([('env', 'evil')]), False),
                 (wasm(expected + [('env', 'evil')]), False),
                 (wasm(expected[:1]), False), (wasm([]), False),
                 (wasm(expected + expected[:1]), False), (b'not wasm', False)]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'test.wasm'
            for data, valid in cases:
                with self.subTest(data=data):
                    path.write_bytes(data)
                    if valid:
                        self.assertEqual(validate_plugin(path), expected)
                    else:
                        with self.assertRaises(ValueError):
                            validate_plugin(path)
                    result = subprocess.run([sys.executable, str(ROOT / 'scripts/wasm_imports.py'),
                                             '--check', str(path)], capture_output=True)
                    self.assertEqual(result.returncode == 0, valid, result.stderr)
