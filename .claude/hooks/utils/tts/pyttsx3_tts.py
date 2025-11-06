#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "pyttsx3",
# ]
# ///

import sys
from pathlib import Path

# Add parent directory to path for audio_queue import
sys.path.insert(0, str(Path(__file__).parent.parent))
from audio_queue import audio_queue

def main():
    """
    System TTS using pyttsx3 (Free, No API Key Required)

    Uses your system's built-in text-to-speech.
    Cost: Free (no API key needed)
    Quality: Basic but functional

    Usage:
    - ./pyttsx3_tts.py                    # Uses default text
    - ./pyttsx3_tts.py "Your custom text" # Uses provided text
    """

    try:
        import pyttsx3
        import os

        # Initialize engine
        engine = pyttsx3.init()

        # Set voice to Ava (Premium) (or from env variable)
        voice_name = os.getenv('SYSTEM_VOICE', 'Ava')
        voices = engine.getProperty('voices')
        for voice in voices:
            if voice_name.lower() in voice.name.lower():
                engine.setProperty('voice', voice.id)
                break

        # Adjust speaking rate (default: 200, lower = slower, higher = faster)
        rate = int(os.getenv('SYSTEM_TTS_RATE', '180'))
        engine.setProperty('rate', rate)

        # Adjust volume (0.0 to 1.0)
        volume = float(os.getenv('SYSTEM_TTS_VOLUME', '0.9'))
        engine.setProperty('volume', volume)

        # Get text from command line argument or use default
        if len(sys.argv) > 1:
            text = " ".join(sys.argv[1:])
        else:
            text = "Ready for your next command."

        # Use audio queue to prevent overlap across terminals
        with audio_queue():
            # Speak the text
            engine.say(text)
            engine.runAndWait()

    except ImportError:
        print("❌ Error: pyttsx3 package not installed")
        print("This script uses UV to auto-install dependencies.")
        print("Make sure UV is installed: https://docs.astral.sh/uv/")
        sys.exit(1)
    except Exception as e:
        # Fail silently for audio errors
        pass

if __name__ == "__main__":
    main()
