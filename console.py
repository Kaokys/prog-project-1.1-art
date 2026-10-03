"""Keep Thai output usable on Windows without encoding tracebacks."""
import sys


def configure_console():
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError, AttributeError):
            pass
    return True
