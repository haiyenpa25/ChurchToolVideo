"""Compatibility entry point; tests now live in tests/."""
import sys

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main(["tests", *sys.argv[1:]]))
