"""Auto-Capture (Layer 0) hook adapters.

These adapters translate Claude Code hook payloads into Event Log appends. They
are deliberately defensive: a hook must never raise into the host session, so
every adapter swallows failures and signals them via a non-fatal return value.
"""
