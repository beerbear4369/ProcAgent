"""
ProcAgent E2E Regression Tests using Playwright MCP

These tests run against a live ProcAgent server with ProMax.
Run with: python tests/e2e/test_mcp_tools.py

Prerequisites:
- ProcAgent server running on http://127.0.0.1:8000
- ProMax installed and licensed
- Playwright MCP available
"""

import asyncio
import time
from dataclasses import dataclass
from typing import List, Optional

# Test scenarios as playbooks
PLAYBOOKS = {
    "separator_basic": {
        "name": "Basic Separator Test",
        "description": "Create a 2-phase separator with feed, vapor, and liquid streams",
        "prompt": """Create a new ProMax project called "Separator Test".
Add components: Methane, Ethane, Propane, Water.
Create a Feed stream at position (50, 105) mm.
Create a Vapor stream at position (250, 150) mm.
Create a Liquid stream at position (250, 60) mm.
Create a separator block at position (150, 105) mm.
Connect Feed to the separator inlet (point 1).
Connect Vapor to the separator vapor outlet (point 2).
Connect Liquid to the separator liquid outlet (point 3).
Set Feed properties: T=40°C, P=3500kPa, F=100kmol/hr.
Set Feed composition: Methane=0.70, Ethane=0.15, Propane=0.10, Water=0.05.
Flash the Feed stream.
Run the simulation.
List all streams and blocks to confirm setup.""",
        "expected_tools": [
            "connect_promax",
            "create_project",
            "add_components",
            "create_stream",  # x3
            "create_block",
            "connect_stream",  # x3
            "set_stream_properties",
            "set_stream_composition",
            "flash_stream",
            "run_simulation",
            "list_streams",
            "list_blocks",
        ],
        "success_indicators": [
            "Connected to ProMax",
            "Created project",
            "Added 4 components",
            "Created stream",
            "Created separator block",
            "Connected",
            "Set Feed properties",
            "Set Feed composition",
            "Flash calculation completed",
            "Simulation converged",
        ],
    },

    "staged_column_amine": {
        "name": "Amine Treater Column Test",
        "description": "Create a staged column (amine treater) with 4 streams",
        "prompt": """Create a new ProMax project called "Amine Treater Test".
Add components: Methane, Hydrogen Sulfide, Carbon Dioxide, Water, MDEA.
Create a Sour Gas stream at position (40, 80) mm.
Create a Lean Amine stream at position (40, 140) mm.
Create a Treated Gas stream at position (260, 140) mm.
Create a Rich Amine stream at position (260, 80) mm.
Create a staged_column block at position (150, 110) mm.
Connect Sour Gas to column bottom-left inlet (point 5).
Connect Lean Amine to column top-left inlet (point 3).
Connect Treated Gas from column top-right outlet (point 4) as outlet.
Connect Rich Amine from column bottom-right outlet (point 6) as outlet.
List all streams and blocks.""",
        "expected_tools": [
            "connect_promax",
            "create_project",
            "add_components",
            "create_stream",  # x4
            "create_block",
            "connect_stream",  # x4
            "list_streams",
            "list_blocks",
        ],
        "success_indicators": [
            "Connected to ProMax",
            "Created project",
            "Added 5 components",
            "Created stream",
            "staged_column block",
            "Connected",
        ],
    },

    "stream_properties": {
        "name": "Stream Properties Test",
        "description": "Test stream creation, properties, composition, flash, and results",
        "prompt": """Create a new ProMax project.
Add components: Hydrogen, Methane, Ethane, Carbon Dioxide, Water.
Create a Test stream at position (100, 100) mm.
Set Test stream properties: T=50°C, P=5000kPa, F=200kmol/hr.
Set Test stream composition: Hydrogen=0.10, Methane=0.60, Ethane=0.15, Carbon Dioxide=0.10, Water=0.05.
Flash the Test stream.
Get the results for Test stream.""",
        "expected_tools": [
            "connect_promax",
            "create_project",
            "add_components",
            "create_stream",
            "set_stream_properties",
            "set_stream_composition",
            "flash_stream",
            "get_stream_results",
        ],
        "success_indicators": [
            "Connected to ProMax",
            "Added 5 components",
            "Created stream 'Test'",
            "Set Test properties",
            "Set Test composition",
            "Flash calculation completed",
            "temperature_c",
        ],
    },

    "list_operations": {
        "name": "List Operations Test",
        "description": "Test list_streams and list_blocks after creating multiple items",
        "prompt": """Create a new ProMax project.
Add components: Methane, Ethane.
Create streams: Stream1 at (50, 100), Stream2 at (100, 100), Stream3 at (150, 100).
Create a separator block at (200, 100).
Create a mixer block at (250, 100).
List all streams.
List all blocks.""",
        "expected_tools": [
            "connect_promax",
            "create_project",
            "add_components",
            "create_stream",  # x3
            "create_block",  # x2
            "list_streams",
            "list_blocks",
        ],
        "success_indicators": [
            "Streams (3)",
            "Blocks (2)",
        ],
    },
}


@dataclass
class TestResult:
    """Result of a single test run."""
    playbook_name: str
    passed: bool
    duration_seconds: float
    tools_called: List[str]
    errors: List[str]
    response_text: str


def print_playbook_info():
    """Print available playbooks."""
    print("\n" + "=" * 60)
    print("ProcAgent E2E Test Playbooks")
    print("=" * 60)
    for key, playbook in PLAYBOOKS.items():
        print(f"\n[{key}] {playbook['name']}")
        print(f"    {playbook['description']}")
    print("\n" + "=" * 60)


def get_test_prompt(playbook_key: str) -> Optional[str]:
    """Get the test prompt for a playbook."""
    if playbook_key not in PLAYBOOKS:
        print(f"Unknown playbook: {playbook_key}")
        print(f"Available: {', '.join(PLAYBOOKS.keys())}")
        return None
    return PLAYBOOKS[playbook_key]["prompt"]


def check_success_indicators(response: str, playbook_key: str) -> tuple[bool, List[str]]:
    """Check if response contains expected success indicators."""
    indicators = PLAYBOOKS[playbook_key]["success_indicators"]
    missing = []
    for indicator in indicators:
        if indicator.lower() not in response.lower():
            missing.append(indicator)
    return len(missing) == 0, missing


# For manual CLI testing
if __name__ == "__main__":
    print_playbook_info()
    print("\nTo run a test, use the prompt from a playbook in the ProcAgent chat UI.")
    print("Or use Playwright MCP to automate the test.")

    # Print first playbook prompt as example
    print("\n" + "-" * 60)
    print("Example - 'separator_basic' prompt:")
    print("-" * 60)
    print(PLAYBOOKS["separator_basic"]["prompt"])
