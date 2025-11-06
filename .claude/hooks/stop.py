#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = [
#     "python-dotenv",
# ]
# ///

import json
import os
import sys
import subprocess
import re
from pathlib import Path

try:
    from dotenv import load_dotenv
    # Load .env from project config directory
    project_dir = os.getenv('CLAUDE_PROJECT_DIR', os.getcwd())
    env_file = Path(project_dir) / 'config' / '.env'
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass  # dotenv is optional

# Import our utilities
sys.path.insert(0, str(Path(__file__).parent / "utils"))
try:
    from transcript_parser import get_last_assistant_message
except ImportError:
    # If imports fail, skip audio
    get_last_assistant_message = None


def extract_summary_from_context(context: str) -> str:
    """
    Extract Friday summary from HTML comment in conversation context.

    Format: <!-- friday_summary: Your summary here -->

    Args:
        context: Conversation context text

    Returns:
        Extracted summary text, or None if not found
    """
    pattern = r'<!--\s*friday_summary:\s*(.*?)\s*-->'
    match = re.search(pattern, context, re.DOTALL)

    if match:
        return match.group(1).strip()

    return None


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


def has_api_key(service):
    """Check if API key exists for a TTS service."""
    if service == 'elevenlabs':
        return bool(os.getenv('ELEVENLABS_API_KEY'))
    elif service == 'openai':
        return bool(os.getenv('OPENAI_API_KEY'))
    elif service == 'system':
        return True  # System TTS doesn't need API key
    return False


def try_tts(script_path, message, service):
    """Try to run a TTS script with the given message."""
    try:
        # Check if API key exists (skip if not)
        if not has_api_key(service):
            return False

        # Run TTS process in background (don't wait for playback)
        process = subprocess.Popen(
            ["uv", "run", script_path, message],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait briefly to see if it starts successfully (5 seconds max)
        try:
            returncode = process.wait(timeout=5)
            return returncode == 0
        except subprocess.TimeoutExpired:
            # Process still running after 5s - means it's playing audio
            return True

    except Exception:
        return False


def announce_completion(message):
    """Announce completion using TTS with automatic fallback chain."""
    if not message:
        return

    script_dir = Path(__file__).parent
    tts_dir = script_dir / "utils" / "tts"

    # Get primary TTS preference
    tts_service = os.getenv('AUDIO_NOTIFICATIONS', 'off').lower()

    if tts_service == 'off':
        return

    # Build fallback chain based on primary preference
    fallback_chain = []

    if tts_service == 'elevenlabs':
        fallback_chain = [
            (tts_dir / "elevenlabs_tts.py", "elevenlabs"),
            (tts_dir / "openai_tts_mini.py", "openai"),
            (tts_dir / "pyttsx3_tts.py", "system"),
        ]
    elif tts_service == 'openai-standard':
        fallback_chain = [
            (tts_dir / "openai_tts.py", "openai"),
            (tts_dir / "pyttsx3_tts.py", "system"),
        ]
    elif tts_service == 'openai-mini':
        fallback_chain = [
            (tts_dir / "openai_tts_mini.py", "openai"),
            (tts_dir / "pyttsx3_tts.py", "system"),
        ]
    elif tts_service == 'system':
        fallback_chain = [
            (tts_dir / "pyttsx3_tts.py", "system"),
        ]
    else:
        return

    # Try each TTS in fallback chain
    for tts_script, service_name in fallback_chain:
        if tts_script.exists() and try_tts(str(tts_script), message, service_name):
            return  # Success!


def main():
    try:
        # Play completion sound (jingle) if enabled
        play_jingle = os.getenv('PLAY_JINGLE', 'off').lower()
        if play_jingle == 'on':
            try:
                subprocess.Popen(
                    ["afplay", "/System/Library/Sounds/Glass.aiff"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass  # Fail silently if sound doesn't play

        # Read JSON input from stdin (required by hook interface)
        input_data = json.load(sys.stdin)

        # Extract summary from last assistant message if available
        if get_last_assistant_message:
            try:
                # Get last assistant message from transcript (optimized - only reads last message)
                last_message = get_last_assistant_message()

                # Extract summary from HTML comment
                if last_message:
                    summary = extract_summary_from_context(last_message)

                    # Announce the summary
                    if summary:
                        announce_completion(summary)

            except Exception:
                # Fail silently
                pass

        sys.exit(0)

    except json.JSONDecodeError:
        # Handle JSON decode errors gracefully
        sys.exit(0)
    except Exception:
        # Handle any other errors gracefully
        sys.exit(0)


if __name__ == "__main__":
    main()
