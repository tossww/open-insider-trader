---
description: Hand off context to next agent after /clear
---

**PURPOSE:** Make TODO.md so detailed that after /clear, the next agent knows EXACTLY what to work on just by reading it.

**IMPORTANT:** All paths are relative to current project. Detect current branch first:
- Run `git branch --show-current` to get branch name
- Set `PROJECT_PATH=projects/{branch}/`
- All file operations use `{PROJECT_PATH}/`

1. **Collect session history:**
   - Get `{PROJECT_PATH}/TODO.md`'s last modified timestamp (if it exists)
   - Get all git commits since that timestamp: `git log --since="<timestamp>" --format="%h %s" --reverse`
   - This captures ALL work done since last handoff, not just what we remember
   - Review commit messages to identify any work not yet documented in TODO.md

2. **Git commit first (if changes exist):**
   - Run git status and git diff to see changes
   - Create descriptive commit message (explain WHY, not just WHAT)
   - Don't push unless explicitly requested
   - Save commit hash for documentation

3. **Update {PROJECT_PATH}/TODO.md:**
   - Update "📍 Current Session Context" section at top:
     - Session Date: Current date
     - Where We Are: Brief summary of milestone progress (including work from git commits since last handoff)
     - Working On: What's currently in progress (🔄 items)
     - Next Up: What should be tackled next
   - Move completed todos (✅) to "Completed Milestones" section:
     - Keep ONLY: ✅ name, commit hash, test results
     - Remove verbose status/next/files details
     - Include any completed work discovered from git commits
   - For in-progress todos (🔄), ensure they have:
     - Current status: What's been done so far
     - Next steps: Exactly what needs to happen next
     - Relevant files: Paths to files being worked on
     - Any blockers or important notes

4. **Update {PROJECT_PATH}/Logs.md:**
   - Add ONE final handoff log entry (newest at top)
   - Include: completed todos (from session + git history), all commit hashes since last handoff, next focus
   - Keep it VERY concise (~5-8 lines)
   - Then archive entire log file to `{PROJECT_PATH}/Archive/Logs/YYYY-MM-DD-session.md`
   - Create fresh `{PROJECT_PATH}/Logs.md` with just the header

5. **Custom announcement:**
   - Summarize what was completed this session (from session memory + git commits)
   - List ALL commit hash(es) since last handoff
   - State what's next for the next agent
   - Remind Boss to run /clear for fresh context
