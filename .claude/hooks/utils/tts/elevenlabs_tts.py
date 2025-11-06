#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = [
#     "elevenlabs",
#     "python-dotenv",
# ]
# ///

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path for audio_queue import
sys.path.insert(0, str(Path(__file__).parent.parent))
from audio_queue import audio_queue

def main():
    """
    ElevenLabs Turbo v2.5 TTS Script

    Uses ElevenLabs' Turbo v2.5 model for fast, high-quality text-to-speech.
    Cost: Subscription-based (Free tier: 10K chars/month)

    Usage:
    - ./elevenlabs_tts.py                    # Uses default text
    - ./elevenlabs_tts.py "Your custom text" # Uses provided text
    - ./elevenlabs_tts.py --list-voices      # List available voices

    Features:
    - Fast generation (optimized for real-time use)
    - High-quality voice synthesis
    - Turbo models use 0.5 credits per character (50% cheaper than standard)
    """

    # Load environment variables
    load_dotenv()

    # Get API key from environment
    api_key = os.getenv('ELEVENLABS_API_KEY')
    if not api_key:
        print("❌ Error: ELEVENLABS_API_KEY not found in environment variables")
        print("Please add your ElevenLabs API key to config/.env file:")
        print("ELEVENLABS_API_KEY=your_api_key_here")
        sys.exit(1)

    try:
        from elevenlabs.client import ElevenLabs
        from elevenlabs.play import play

        # Initialize client
        elevenlabs = ElevenLabs(api_key=api_key)

        # Check for --list-voices flag
        if len(sys.argv) > 1 and sys.argv[1] == "--list-voices":
            print("Available voices:")
            voices = elevenlabs.voices.get_all()
            for voice in voices.voices:
                print(f"  {voice.name}: {voice.voice_id}")
            sys.exit(0)

        # Get voice ID from environment or use default
        voice_id = os.getenv('ELEVENLABS_VOICE_ID', 'EXAVITQu4vr4xnSDxMaL')

        # Get text from command line argument or use default
        if len(sys.argv) > 1:
            text = " ".join(sys.argv[1:])
        else:
            text = "Ready for your next command."

        # Generate and play audio directly
        audio = elevenlabs.text_to_speech.convert(
            text=text,
            voice_id=voice_id,
            model_id="eleven_turbo_v2_5",
        )

        # Use audio queue to prevent overlap across terminals
        with audio_queue():
            play(audio)

    except ImportError:
        print("❌ Error: elevenlabs package not installed")
        print("This script uses UV to auto-install dependencies.")
        print("Make sure UV is installed: https://docs.astral.sh/uv/")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
