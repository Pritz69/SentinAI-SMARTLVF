import sqlite3
import json
import asyncio
import sys

# ─── 1. Check raw SQLite tables and recent checkpoints ───────────────────────
conn = sqlite3.connect("sentinai_state.db")
conn.row_factory = sqlite3.Row

tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("=== Tables ===")
print(tables)
print()

if "checkpoints" in tables:
    rows = conn.execute(
        "SELECT thread_id, checkpoint_id, metadata FROM checkpoints ORDER BY rowid DESC LIMIT 10"
    ).fetchall()
    print(f"=== Checkpoints (last {len(rows)}) ===")
    for r in rows:
        meta = json.loads(r["metadata"]) if r["metadata"] else {}
        print(f"  thread_id = {r['thread_id']}")
        print(f"    next    = {meta.get('writes', '(no writes key)')}")
        print(f"    source  = {meta.get('source', '?')}")
        print(f"    step    = {meta.get('step', '?')}")
        print()
else:
    print("No 'checkpoints' table found!")

conn.close()

# ─── 2. Use LangGraph's aget_state to see what FastAPI would see ──────────────
sim_id = sys.argv[1] if len(sys.argv) > 1 else "sim_794b12e06235"

async def check_state():
    from config.settings import settings
    from agents.graph import sentinai_graph

    config = {"configurable": {"thread_id": sim_id}}
    snapshot = await sentinai_graph.aget_state(config)

    if not snapshot or not snapshot.values:
        print(f"=== aget_state for {sim_id} ===")
        print("  RESULT: No state found (404 would be returned)")
        return

    print(f"=== aget_state for {sim_id} ===")
    print(f"  snapshot.next   = {snapshot.next}")
    print(f"  turn_count      = {snapshot.values.get('turn_count')}")
    print(f"  has evaluation  = {snapshot.values.get('evaluation') is not None}")
    if snapshot.next:
        print(f"  STATUS → paused_for_hitl (next node: {snapshot.next})")
    else:
        print(f"  STATUS → completed (no next nodes)")

asyncio.run(check_state())
