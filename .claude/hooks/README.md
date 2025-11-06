# Claude Code Hooks

Audio notification hooks for Claude Code.

## Hooks

**`notification.py`** - Announces when Claude needs input
**`stop.py`** - Announces task completion (supports custom summaries via JSON `summary` field)
**`announce.py`** - Standalone script for custom announcements

```bash
uv run .claude/hooks/announce.py "Task completed successfully"
```

## Configuration (`.env`)

**Audio Service:**
- `elevenlabs` - Best quality, free tier (10K chars/month)
- `openai-standard` - High quality (~$0.75/100)
- `openai-mini` - Budget (~$0.03/100)
- `system` - Free system TTS
- `off` - Silent

**Voice IDs:**
```bash
ELEVENLABS_VOICE_ID=YOUR_VOICE_ID
OPENAI_VOICE_ID=alloy  # alloy, echo, fable, onyx, nova, shimmer
```

**AI Summaries:**
```bash
ANTHROPIC_API_KEY=YOUR_KEY  # For intelligent summaries via Claude Haiku
```
