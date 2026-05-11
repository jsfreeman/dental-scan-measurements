import sys

print(f"Python version: {sys.version}")
major, minor = sys.version_info[:2]
if (major, minor) >= (3, 10):
    print(f"OK: Python {major}.{minor} >= 3.10")
else:
    print(f"FAIL: Python {major}.{minor} is below 3.10")
