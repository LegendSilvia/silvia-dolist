from src.todo_cli.commands import _HANDLERS, KNOWN_COMMANDS

# Check if all decorated handlers are registered
print('Checking handler registration:')
print(f'  _HANDLERS has {len(_HANDLERS)} entries: {sorted(_HANDLERS.keys())}')
print()
print('Checking KNOWN_COMMANDS:')
print(f'  KNOWN_COMMANDS has {len(KNOWN_COMMANDS)} entries')
print()
print('Discrepancy analysis:')
print(f'  Handlers registered but not in KNOWN_COMMANDS: {set(_HANDLERS.keys()) - set(KNOWN_COMMANDS)}')
print(f'  In KNOWN_COMMANDS but no handler: {set(KNOWN_COMMANDS) - set(_HANDLERS.keys())}')
print()
print('Exit handler registered for both /exit and /quit:')
print(f'  /exit points to: {_HANDLERS["/exit"].__name__}')
print(f'  /quit points to: {_HANDLERS["/quit"].__name__}')
print(f'  Same function? {_HANDLERS["/exit"] is _HANDLERS["/quit"]}')
