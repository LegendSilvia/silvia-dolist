"""Hand a todo over to Claude Code.

Builds a prompt that includes the todo's metadata, asks Claude to read
the rest of the list via the MCP server for context, copies it to the
clipboard, and spawns `claude` in a new terminal with the prompt
already loaded so the user doesn't have to paste anything.

Sessions are named (``-n <name>``) so the same conversation can be
resumed on a later /ask. The session name is stored on the todo.
"""
from __future__ import annotations
import shutil
import subprocess
import sys
import uuid
from typing import Optional

from todo_cli.models import Todo


def build_prompt(todo: Todo) -> str:
    parts = ["I'm working on this todo and would like your help:\n"]
    parts.append(f"- ID: #{todo.id}")
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
        "You're running in a terminal where the `todo` CLI is on PATH. Read my "
        "list before answering — cross-context usually shapes better advice:\n"
        "  todo /list                   open todos\n"
        "  todo /list --all             include done items\n"
        "  todo /list --tag X           filter by tag\n"
        "  todo /list --project P       filter by project\n"
        "  todo /show <id>              full detail for one todo"
    )
    parts.append("")
    parts.append(
        "If you want to *propose* state changes for me to apply, here's the "
        "syntax. I'll run them myself — don't run destructive commands "
        "(/done is reversible; /del is not):\n"
        "  todo /add <text>             new todo. text is NL-parsed for dates,\n"
        "                               #tags, @project, p1|p2|p3 (e.g.\n"
        "                               'buy milk tmr #shop @groceries p2')\n"
        "  todo /done <id>              mark complete\n"
        "  todo /undo <id>              mark incomplete\n"
        "  todo /del <id>               delete (asks me y/n in the TUI)\n"
        "  todo /edit <id> <field> <value>\n"
        "                               fields: text, description, due,\n"
        "                               due_time, priority, tags, project, done\n"
        "                               (use 'none' as <value> to clear)"
    )
    parts.append("")
    parts.append(
        "Then help me think through this todo specifically — break it into "
        "steps, surface anything I might be missing, and suggest a concrete "
        "first action. If progress here unblocks or affects other items in "
        "the list, point it out."
    )
    return "\n".join(parts)


def new_session_name(todo: Todo) -> str:
    """Stable, unique session name we can resume by later."""
    return f"todo-{todo.id}-{uuid.uuid4().hex[:8]}"


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


def _build_claude_args(
    prompt: Optional[str],
    session_name: Optional[str],
    resume_session: Optional[str],
) -> list[str]:
    args = ["claude"]
    if resume_session is not None:
        # Resume an existing named session — claude picks up the conversation
        # right where it left off; don't re-pass the prompt.
        args.extend(["--resume", resume_session])
        return args
    if session_name is not None:
        args.extend(["-n", session_name])
    if prompt is not None:
        args.append(prompt)
    return args


def open_terminal_with_claude(
    prompt: Optional[str] = None,
    *,
    session_name: Optional[str] = None,
    resume_session: Optional[str] = None,
    cwd: Optional[str] = None,
) -> bool:
    """Spawn a new terminal window running `claude`.

    - ``prompt`` is the initial user message (passed as positional arg so the
      session opens interactive with the response already streaming).
    - ``session_name`` names a fresh session via ``claude -n``.
    - ``resume_session`` resumes an existing named session via
      ``claude --resume`` and ignores the prompt.
    - ``cwd`` is the working directory the new terminal opens in.
    """
    args = _build_claude_args(prompt, session_name, resume_session)
    try:
        if sys.platform == "win32":
            claude_path = shutil.which("claude")
            if not claude_path:
                return False
            new_console = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
            subprocess.Popen(
                [claude_path] + args[1:],
                creationflags=new_console,
                shell=False,
                cwd=cwd,
            )
            return True
        if sys.platform == "darwin":
            quoted = " ".join(_shell_quote(a) for a in args)
            cd_prefix = f"cd {_shell_quote(cwd)} && " if cwd else ""
            subprocess.Popen([
                "osascript", "-e",
                f'tell application "Terminal" to do script "{cd_prefix}{quoted}"',
            ])
            return True
        for term in ("x-terminal-emulator", "gnome-terminal", "konsole", "xterm"):
            if shutil.which(term):
                subprocess.Popen([term, "-e"] + args, cwd=cwd)
                return True
        return False
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return False


def _shell_quote(s: str) -> str:
    """Minimal POSIX-safe single-quote wrap; escape embedded single quotes."""
    return "'" + s.replace("'", "'\"'\"'") + "'"
