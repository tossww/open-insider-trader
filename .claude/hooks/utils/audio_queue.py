"""
Audio Queue Manager

Prevents audio overlap when multiple Claude instances run simultaneously
by serializing audio playback using file-based locking.
"""

import os
import time
import fcntl
from contextlib import contextmanager
from typing import Optional


LOCK_FILE = "/tmp/claude_audio.lock"
DEFAULT_TIMEOUT = 30  # seconds


@contextmanager
def audio_queue(timeout: Optional[float] = DEFAULT_TIMEOUT):
    """
    Context manager that ensures only one audio plays at a time across all terminals.

    Usage:
        with audio_queue():
            play_audio()  # Your audio playback code here

    Args:
        timeout: Maximum seconds to wait for the lock. None = wait forever.

    Raises:
        TimeoutError: If lock cannot be acquired within timeout period
    """
    lock_fd = None
    start_time = time.time()

    try:
        # Create lock file if it doesn't exist
        lock_fd = os.open(LOCK_FILE, os.O_CREAT | os.O_RDWR)

        # Try to acquire exclusive lock
        while True:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break  # Lock acquired
            except (IOError, OSError):
                # Lock is held by another process
                if timeout is not None and (time.time() - start_time) >= timeout:
                    raise TimeoutError(
                        f"Could not acquire audio lock within {timeout} seconds. "
                        "Another audio is still playing."
                    )
                time.sleep(0.1)  # Wait 100ms before retrying

        yield  # Audio playback happens here

    finally:
        # Release lock
        if lock_fd is not None:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                os.close(lock_fd)
            except Exception:
                pass  # Best effort cleanup


def clear_stale_lock():
    """
    Remove stale lock file if it exists.
    Call this if you suspect a lock file was left behind by a crashed process.
    """
    try:
        os.remove(LOCK_FILE)
    except FileNotFoundError:
        pass  # Already removed
    except Exception as e:
        print(f"Warning: Could not remove lock file: {e}")
