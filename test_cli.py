"""
CLI Test for ProcAgent - bypasses web server async issues
"""
import asyncio
import sys

# Windows needs ProactorEventLoop for subprocess support
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from claude_agent_sdk import query, ClaudeAgentOptions

async def test_simple():
    """Simple test without MCP servers."""
    print("Testing Claude Agent SDK (simple, no MCP)...")
    print("-" * 50)

    options = ClaudeAgentOptions(
        max_turns=1,
        system_prompt="You are ProcAgent, a helpful assistant. Be brief.",
    )

    try:
        async for msg in query(prompt="Say hello and identify yourself in one sentence", options=options):
            msg_type = type(msg).__name__
            print(f"[{msg_type}]")

            if hasattr(msg, 'content'):
                for block in msg.content:
                    if hasattr(block, 'text'):
                        print(f"  Text: {block.text}")
                    elif hasattr(block, 'name'):
                        print(f"  Tool: {block.name}")
            elif hasattr(msg, 'data'):
                print(f"  Model: {msg.data.get('model', 'unknown')}")
                print(f"  API Source: {msg.data.get('apiKeySource', 'unknown')}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

async def test_via_procagent():
    """Test via ProcAgentCore class."""
    print("\nTesting via ProcAgentCore...")
    print("-" * 50)

    sys.path.insert(0, '.')
    from procagent.agent.core import ProcAgentCore
    from procagent.models import ChatMessage

    agent = ProcAgentCore(session_id='cli-test')
    message = ChatMessage(message="Hello, who are you? what is the weather like tmr in singapore")

    try:
        async for response in agent.process_message(message):
            print(f"[{response.type}] {response.content or response.status or ''}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=" * 50)
    print("ProcAgent CLI Test (No MCP)")
    print("=" * 50)

    # Run simple test first
    asyncio.run(test_simple())

    # Test via ProcAgentCore
    asyncio.run(test_via_procagent())
