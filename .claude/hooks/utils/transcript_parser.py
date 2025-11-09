#!/usr/bin/env python3
"""
Transcript Parser for Claude Code Audio Summaries

Parses the conversation history to extract context for AI-generated summaries.
Reads from ~/.claude/projects/{project-slug}/{session-id}.jsonl and finds relevant
conversation since last user message.
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from glob import glob

# Constants
TRANSCRIPT_TAIL_LINES = 50  # Number of lines to read from end of transcript (increased to capture more context)
SESSION_DIR = Path.home() / ".claude" / "projects"



def get_project_path() -> str:
    """Get the current project path from environment or current working directory."""
    # Try CLAUDE_PROJECT_DIR first (if available)
    project_path = os.getenv('CLAUDE_PROJECT_DIR')
    if project_path:
        return project_path

    # Fall back to current working directory
    return os.getcwd()


def find_current_session_file() -> Optional[Path]:
    """
    Find the current session transcript file.
    Session files are stored in ~/.claude/projects/{project-name-slug}/{session-id}.jsonl

    Returns:
        Path to the most recent session file, or None if not found
    """
    try:
        project_path = get_project_path()

        # Convert project path to slug format (e.g., /Users/foo/bar -> -Users-foo-bar)
        # Claude Code also converts dots and other special chars to dashes
        project_slug = project_path.replace('/', '-').replace('.', '-')
        if project_slug.startswith('-'):
            project_slug = project_slug[1:]  # Remove leading dash

        # Find project directory
        project_dir = SESSION_DIR / f"-{project_slug}"

        if not project_dir.exists():
            return None

        # Find all session files and get the most recent one
        session_files = list(project_dir.glob("*.jsonl"))
        if not session_files:
            return None

        # Sort by modification time, most recent first
        session_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        current_session = session_files[0]

        return current_session

    except Exception:
        return None


def extract_text_from_message(msg: Dict) -> str:
    """
    Extract text content from a session message.

    Args:
        msg: Message dictionary from session file

    Returns:
        Extracted text content
    """
    try:
        message_content = msg.get('message', {}).get('content')

        if not message_content:
            return ""

        # User messages: content is a string
        if isinstance(message_content, str):
            return message_content

        # Assistant messages: content is an array of blocks
        if isinstance(message_content, list):
            text_parts = []
            for content_block in message_content:
                if isinstance(content_block, dict) and content_block.get('type') == 'text':
                    text = content_block.get('text', '')
                    text_parts.append(text)

            return '\n'.join(text_parts)

        return ""

    except Exception:
        return ""


def is_user_message(msg: Dict) -> bool:
    """
    Check if a message is from the user (actual text, not tool results).

    Args:
        msg: Message dictionary from session file

    Returns:
        True if message is from user with actual text content
    """
    if msg.get('type') != 'user':
        return False

    # Check if it's actual user text (string) vs tool_result (array)
    content = msg.get('message', {}).get('content')

    # User text messages have string content
    # Tool result messages have array content with tool_result type
    if isinstance(content, str):
        return True

    # Tool results are arrays - not actual user messages
    return False


def read_transcript_tail(num_lines: int = TRANSCRIPT_TAIL_LINES) -> List[Dict]:
    """
    Read the last N messages from the current session file.
    Optimized to stop early once we've found the user's last message.

    Args:
        num_lines: Maximum number of messages to read (default: 20)

    Returns:
        List of message dictionaries from the transcript
    """
    session_file = find_current_session_file()
    if not session_file or not session_file.exists():
        return []

    try:
        # Read all lines from session file
        with open(session_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()

        # Parse messages in reverse order (most recent first)
        messages = []
        found_user_message = False

        for line in reversed(all_lines):
            if not line.strip():
                continue

            try:
                msg = json.loads(line.strip())

                # Only include user and assistant messages (skip system messages, etc.)
                if msg.get('type') in ['user', 'assistant']:
                    messages.append(msg)

                    # Check if this is a user message
                    if not found_user_message and is_user_message(msg):
                        found_user_message = True

                    # Stop once we have enough messages
                    if len(messages) >= num_lines:
                        break

                    # If we found user message and have at least 5 messages after it, we can stop
                    if found_user_message and len(messages) >= 5:
                        break

            except json.JSONDecodeError:
                continue

        # Reverse to get chronological order
        return list(reversed(messages))

    except Exception:
        return []


def find_last_user_message_index(messages: List[Dict]) -> Optional[int]:
    """
    Find the index of the last user message in the conversation.

    Args:
        messages: List of message dictionaries

    Returns:
        Index of last user message, or None if not found
    """
    if not messages:
        return None

    # Search backwards through messages
    for i in range(len(messages) - 1, -1, -1):
        if is_user_message(messages[i]):
            return i

    # If no user message found, return the first message index
    return 0 if messages else None


def extract_context_since_user(messages: List[Dict]) -> str:
    """
    Extract conversation context since the last user message.

    Args:
        messages: List of message dictionaries

    Returns:
        Formatted string of conversation context
    """
    if not messages:
        return ""

    # Find last user message
    user_msg_idx = find_last_user_message_index(messages)

    if user_msg_idx is None:
        # No user message found - return all messages
        relevant_messages = messages
    else:
        # Get all messages from user message onward
        relevant_messages = messages[user_msg_idx:]

    # Format messages into readable context
    context_parts = []
    for msg in relevant_messages:
        # Extract text from the new message format
        text = extract_text_from_message(msg).strip()
        if text:
            # Add role prefix for clarity
            role = "User" if is_user_message(msg) else "Assistant"
            context_parts.append(f"{role}: {text}")

    return "\n\n".join(context_parts)


def get_conversation_context() -> str:
    """
    Main entry point: Get relevant conversation context for summarization.

    Returns:
        String containing conversation context since last user message
    """
    # Read last N lines from transcript
    messages = read_transcript_tail(TRANSCRIPT_TAIL_LINES)

    if not messages:
        return "No recent conversation history available."

    # Extract context since last user message
    context = extract_context_since_user(messages)

    return context if context else "No conversation context found."


def get_last_assistant_message() -> str:
    """
    Optimized function: Get only the last assistant message text.

    This is much faster than get_conversation_context() since it:
    - Reads from END of file (not all lines)
    - Only reads last ~50KB which typically contains last few messages
    - Returns immediately after finding the last assistant message

    Returns:
        Text content of the last assistant message, or empty string if not found
    """
    session_file = find_current_session_file()
    if not session_file or not session_file.exists():
        return ""

    try:
        # Read only from end of file (last 50KB should contain last few messages)
        # This is much faster than reading entire file for long sessions
        TAIL_BYTES = 50 * 1024  # 50KB

        with open(session_file, 'rb') as f:
            # Get file size
            f.seek(0, 2)  # Seek to end
            file_size = f.tell()

            # Determine where to start reading
            start_pos = max(0, file_size - TAIL_BYTES)
            f.seek(start_pos)

            # Read tail portion
            tail_data = f.read().decode('utf-8', errors='ignore')

        # Split into lines and search from end
        lines = tail_data.split('\n')

        for line in reversed(lines):
            if not line.strip():
                continue

            try:
                msg = json.loads(line.strip())

                # Only look for assistant messages
                if msg.get('type') == 'assistant':
                    text = extract_text_from_message(msg).strip()
                    if text:
                        return text

            except json.JSONDecodeError:
                continue

        return ""

    except Exception:
        return ""
