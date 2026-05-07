from src.todo_cli.commands import run_command
from src.todo_cli.storage import Storage
from src.todo_cli.config import Config
from pathlib import Path
import shutil

# Create clean temp storage
tmpdir = Path(r"C:\Development\todo-cli\.test_edge_cases")
if tmpdir.exists():
    shutil.rmtree(tmpdir)
tmpdir.mkdir(exist_ok=True)

storage = Storage(tmpdir / "todos.json")
storage.load()
config = Config()

# Test 1: Whitespace handling
print("Test 1: Whitespace-only line")
result = run_command("   ", storage, config)
print(f"  Result: exit={result.exit}, clear={result.clear}, renderable={result.renderable}")

# Test 2: Parse error with unbalanced quotes
print("\nTest 2: Unbalanced quotes")
result = run_command("/help \"missing quote", storage, config)
print(f"  Result: {type(result.renderable).__name__}")
print(f"  Contains Parse error: {'Parse error' in str(result.renderable)}")

# Test 3: Unknown command with no close match
print("\nTest 3: Unknown command with no close match")
result = run_command("/xyz", storage, config)
print(f"  Contains Unknown command: {'Unknown command' in str(result.renderable)}")
print(f"  Contains suggestion: {'Did you mean' in str(result.renderable)}")

# Test 4: Command with extra args (should still work)
print("\nTest 4: /exit with extra args")
result = run_command("/exit extraarg", storage, config)
print(f"  Result: exit={result.exit}")

# Test 5: Case sensitivity
print("\nTest 5: Case sensitivity (/HELP)")
result = run_command("/HELP", storage, config)
print(f"  Result: {'Found /help' if 'Commands:' in str(result.renderable) else 'Treated as unknown'}")

# Cleanup
shutil.rmtree(tmpdir)
