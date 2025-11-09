#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = [
#     "python-dotenv",
# ]
# ///

import argparse
import json
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


def announce_notification():
    """Announce that the agent needs user input."""
    try:
        tts_script = get_tts_script_path()
        if not tts_script:
            return  # No TTS scripts available

        notification_message = "Your agent needs your input"

        # Call the TTS script with the notification message
        subprocess.run([
            "uv", "run", tts_script, notification_message
        ],
        capture_output=True,  # Suppress output
        timeout=10  # 10-second timeout
        )

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        # Fail silently if TTS encounters issues
        pass
    except Exception:
        # Fail silently for any other errors
        pass


def main():
    try:
        # Read JSON input from stdin
        input_data = json.loads(sys.stdin.read())

        # Skip TTS for the generic "Claude is waiting for your input" message
        if input_data.get('message') != 'Claude is waiting for your input':
            announce_notification()

        sys.exit(0)

    except json.JSONDecodeError:
        # Handle JSON decode errors gracefully
        sys.exit(0)
    except Exception:
        # Handle any other errors gracefully
        sys.exit(0)

if __name__ == '__main__':
    main()
