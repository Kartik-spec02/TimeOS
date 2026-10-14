import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    params = StdioServerParameters(command="python", args=["server.py"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            print("=== Test 1: Add first event (10:00-11:00) ===")
            r = await session.call_tool("add_event", {
                "title": "Team Meeting",
                "start_time": "2026-10-20T10:00:00",
                "end_time": "2026-10-20T11:00:00"
            })
            print(r.content[0].text)

            print("\n=== Test 2: Add conflicting event (10:30-11:30) ===")
            r = await session.call_tool("add_event", {
                "title": "Study Session",
                "start_time": "2026-10-20T10:30:00",
                "end_time": "2026-10-20T11:30:00"
            })
            print(r.content[0].text)

            print("\n=== Test 3: Find free slots on 2026-10-20 (60 min) ===")
            r = await session.call_tool("find_free_slots", {
                "date": "2026-10-20",
                "duration_minutes": 60
            })
            print(r.content[0].text)

            print("\n=== Test 4: Suggest resolution ===")
            r = await session.call_tool("suggest_resolution", {
                "conflicting_title": "Study Session",
                "start_time": "2026-10-20T10:30:00",
                "end_time": "2026-10-20T11:30:00",
                "date": "2026-10-20"
            })
            print(r.content[0].text)

            print("\n=== Test 5: Move the conflicting event (update_event) ===")
            r = await session.call_tool("update_event", {
                "event_id": 1,
                "new_start_time": "2026-10-20T14:00:00",
                "new_end_time": "2026-10-20T15:00:00"
            })
            print(r.content[0].text)

            print("\n=== Test 6: Now add Study Session (should succeed) ===")
            r = await session.call_tool("add_event", {
                "title": "Study Session",
                "start_time": "2026-10-20T10:30:00",
                "end_time": "2026-10-20T11:30:00"
            })
            print(r.content[0].text)

            print("\n=== Test 7: Get all events on 2026-10-20 ===")
            r = await session.call_tool("get_events", {"date": "2026-10-20"})
            print(r.content[0].text)

            print("\n=== Test 8: Free slots again (60 min) ===")
            r = await session.call_tool("find_free_slots", {
                "date": "2026-10-20",
                "duration_minutes": 60
            })
            print(r.content[0].text)

asyncio.run(main())