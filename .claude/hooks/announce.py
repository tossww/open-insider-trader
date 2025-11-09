#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = [
#     "python-dotenv",
# ]
# ///

import os
import sys
import subprocess
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional


def get_tts_script_path():
    """
    Determine which TTS script to use based on AUDIO_NOTIFICATIONS setting.
    Options: 'elevenlabs', 'openai-standard', 'openai-mini', 'system', 'off'
    """
    script_dir = Path(__file__).parent
    tts_dir = script_dir / "utils" / "tts"

    # Get TTS service preference from environment
    tts_service = os.getenv('AUDIO_NOTIFICATIONS', 'off').lower()

    if tts_service == 'elevenlabs':
        elevenlabs_script = tts_dir / "elevenlabs_tts.py"
        if elevenlabs_script.exists():
            return str(elevenlabs_script)

    elif tts_service == 'openai-standard':
        openai_script = tts_dir / "openai_tts.py"
        if openai_script.exists():
            return str(openai_script)

    elif tts_service == 'openai-mini':
        openai_mini_script = tts_dir / "openai_tts_mini.py"
        if openai_mini_script.exists():
            return str(openai_mini_script)

    elif tts_service == 'system':
        system_script = tts_dir / "pyttsx3_tts.py"
        if system_script.exists():
            return str(system_script)

    # 'off' or any other value = no audio
    return None


def announce(message):
    """Announce a custom message using the configured TTS service."""
    try:
        tts_script = get_tts_script_path()
        if not tts_script:
            # Notifications are off, silently return
            return

        # Call the TTS script with the message
        subprocess.run(
            ["uv", "run", tts_script, message],
            capture_output=True,  # Suppress output
            timeout=10,  # 10-second timeout
        )

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        # Fail silently if TTS encounters issues
        pass
    except Exception:
        # Fail silently for any other errors
        pass


def main():
    """
    Announce a custom message.

    Usage:
        announce.py "Task completed - all tests passing"
        announce.py "Authentication system is ready"
    """
    if len(sys.argv) < 2:
        print("Usage: announce.py <message>")
        sys.exit(1)

    # Join all arguments to support multi-word messages
    message = " ".join(sys.argv[1:])

    announce(message)
    sys.exit(0)


if __name__ == "__main__":
    main()
