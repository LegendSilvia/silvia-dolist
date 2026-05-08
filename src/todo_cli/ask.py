"""Open a new terminal running `claude` and copy a ready-to-paste
prompt about a todo to the clipboard.

The user can hit a single command (/ask) on the selected todo, then
paste in the new claude window. Cross-platform: Windows uses clip.exe
and `start cmd /k claude`; macOS uses pbcopy + osascript Terminal;
Linux tries pyperclip-style fallbacks via xclip/xsel and a few common
terminal emulators.
"""
from __future__ import annotations
import shutil
import subprocess
import sys

from todo_cli.models import Todo


def build_prompt(todo: Todo) -> str:
    parts = ["I'm working on this todo and would like your help:\n"]
    parts.append(f"- Title: {todo.text}")
    if todo.description:
        parts.append(f"- Description: {todo.description}")
    if todo.due:
        due_str = todo.due.isoformat()
        if todo.due_time:
            due_str += f" {todo.due_time.strftime('%H:%M')}"
        parts.append(f"- Due: {due_str}")
    if todo.priority:
        parts.append(f"- Priority: {todo.priority}")
    if todo.tags:
        parts.append(f"- Tags: {', '.join(todo.tags)}")
    if todo.project:
        parts.append(f"- Project: {todo.project}")
    parts.append("")
    parts.append(
        "Please help me think through how to approach this — break it into "
        "steps, surface anything I might be missing, and suggest a concrete "
        "first action."
    )
    return "\n".join(parts)


def copy_to_clipboard(text: str) -> bool:
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["clip"], input=text, text=True, encoding="utf-8",
                check=True,
            )
            return True
        if sys.platform == "darwin":
            subprocess.run(
                ["pbcopy"], input=text, text=True, encoding="utf-8",
                check=True,
            )
            return True
        for cmd in (["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]):
            if shutil.which(cmd[0]):
                subprocess.run(cmd, input=text, text=True, check=True)
                return True
        return False
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return False


def open_terminal_with_claude() -> bool:
    """Spawn a new terminal window running `claude`."""
    try:
        if sys.platform == "win32":
            if shutil.which("wt"):
                subprocess.Popen(
                    ["wt", "--", "claude"],
                    creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
                )
            else:
                subprocess.Popen("start cmd /k claude", shell=True)
            return True
        if sys.platform == "darwin":
            subprocess.Popen([
                "osascript", "-e",
                'tell application "Terminal" to do script "claude"',
            ])
            return True
        for term in ("x-terminal-emulator", "gnome-terminal", "konsole", "xterm"):
            if shutil.which(term):
                subprocess.Popen([term, "-e", "claude"])
                return True
        return False
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return False
