#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "openai",
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
    OpenAI GPT-4o-mini-TTS Script

    Uses OpenAI's GPT-4o-mini TTS model for text-to-speech.
    Cost: $0.0006 per 1K characters (25x cheaper than TTS-1!)

    Usage:
    - ./openai_tts_mini.py                    # Uses default text
    - ./openai_tts_mini.py "Your custom text" # Uses provided text
    """

    # Load environment variables
    load_dotenv()

    # Get API key from environment
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ Error: OPENAI_API_KEY not found in environment variables")
        print("Please add your OpenAI API key to config/.env file:")
        print("OPENAI_API_KEY=your_api_key_here")
        sys.exit(1)

    try:
        from openai import OpenAI
        import tempfile
        import subprocess

        # Initialize client
        client = OpenAI(api_key=api_key)

        # Get voice from environment or use default
        voice = os.getenv('OPENAI_VOICE_ID', 'nova')

        # Get text from command line argument or use default
        if len(sys.argv) > 1:
            text = " ".join(sys.argv[1:])
        else:
            text = "Ready for your next command."

        # Generate audio using GPT-4o-mini-TTS
        response = client.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice=voice,  # Options: alloy, echo, fable, onyx, nova, shimmer
            input=text
        )

        # Save to temporary file and play
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
            tmp_file.write(response.content)
            tmp_path = tmp_file.name

        try:
            # Use audio queue to prevent overlap across terminals
            with audio_queue():
                # Play audio using afplay (macOS)
                subprocess.run(["afplay", tmp_path], check=True)
        finally:
            # Clean up temp file
            os.unlink(tmp_path)

    except ImportError:
        print("❌ Error: openai package not installed")
        print("This script uses UV to auto-install dependencies.")
        print("Make sure UV is installed: https://docs.astral.sh/uv/")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
