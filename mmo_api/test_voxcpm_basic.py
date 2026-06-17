#!/usr/bin/env python3
"""
Quick test to verify VoxCPM2 integration works.
This tests imports and basic model loading (WITHOUT generating audio).
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

print("[TEST] Testing VoxCPM2 integration...")
print(f"[TEST] Python: {sys.version}")
print()

# Test 1: Import voxcpm module
try:
    from voxcpm import VoxCPM
    import soundfile as sf
    print("✓ VoxCPM2 and soundfile imports successful")
except ImportError as e:
    print(f"✗ Failed to import VoxCPM2: {e}")
    sys.exit(1)

# Test 2: Import our dubbing module
try:
    from src.dubbing import synthesize_khmer_tts, VOXCPM_AVAILABLE
    print("✓ src.dubbing imports successful")
    print(f"  - VOXCPM_AVAILABLE: {VOXCPM_AVAILABLE}")
except ImportError as e:
    print(f"✗ Failed to import src.dubbing: {e}")
    sys.exit(1)

# Test 3: Check configuration helpers
try:
    from src.dubbing import (
        _resolve_tts_setting,
        _resolve_float_setting,
        _resolve_int_setting,
        _resolve_bool_setting,
    )
    print("✓ Configuration helpers imported")
except ImportError as e:
    print(f"✗ Failed to import config helpers: {e}")
    sys.exit(1)

# Test 4: Test resolver functions
print()
print("[TEST] Testing configuration resolvers...")
test_val = _resolve_tts_setting("test", "MISSING_VAR", "default")
assert test_val == "test", "String resolver failed"
print("✓ _resolve_tts_setting works")

test_float = _resolve_float_setting(2.5, "MISSING_VAR", 1.0)
assert test_float == 2.5, "Float resolver failed"
print("✓ _resolve_float_setting works")

test_int = _resolve_int_setting(10, "MISSING_VAR", 5)
assert test_int == 10, "Int resolver failed"
print("✓ _resolve_int_setting works")

test_bool = _resolve_bool_setting(True, "MISSING_VAR", False)
assert test_bool == True, "Bool resolver failed"
print("✓ _resolve_bool_setting works")

print()
print("[TEST] ✓ All basic tests passed!")
print()
print("Note: Model loading skipped (large download ~2GB)")
print("To test full synthesis, call: synthesize_khmer_tts('ทดสอบ', 'test.wav')")
