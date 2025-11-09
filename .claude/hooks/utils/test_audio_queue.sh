#!/bin/bash
#
# Test script for audio queue system
#
# Usage:
#   Open multiple terminals and run this script simultaneously to test
#   that audio plays sequentially instead of overlapping.
#
#   Terminal 1: ./test_audio_queue.sh "Terminal one speaking"
#   Terminal 2: ./test_audio_queue.sh "Terminal two speaking"
#   Terminal 3: ./test_audio_queue.sh "Terminal three speaking"
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TTS_DIR="$SCRIPT_DIR/tts"

# Get text to speak or use default
TEXT="${1:-Testing audio queue from terminal}"

# Detect which TTS is configured
AUDIO_SERVICE="${AUDIO_NOTIFICATIONS:-system}"

echo "Testing audio queue with service: $AUDIO_SERVICE"
echo "Speaking: $TEXT"

case "$AUDIO_SERVICE" in
    elevenlabs)
        "$TTS_DIR/elevenlabs_tts.py" "$TEXT"
        ;;
    openai-standard)
        "$TTS_DIR/openai_tts.py" "$TEXT"
        ;;
    openai-mini)
        "$TTS_DIR/openai_tts_mini.py" "$TEXT"
        ;;
    system)
        "$TTS_DIR/pyttsx3_tts.py" "$TEXT"
        ;;
    *)
        echo "Audio disabled or unknown service: $AUDIO_SERVICE"
        exit 1
        ;;
esac

echo "Done!"
