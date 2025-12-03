"""
Computer Use MCP Server

Provides Claude Computer Use fallback tools for screen capture,
mouse clicks, keyboard input when COM API cannot accomplish a task.

Uses pyautogui for GUI automation and mss for screen capture.
"""

import base64
import io
from typing import Any, Dict, List, Literal, Optional, Tuple

from ..logging_config import get_logger

logger = get_logger("cua.computer_use")

# Default screen dimensions
DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080


class ComputerUseState:
    """State for Computer Use executor."""

    _instance: Optional["ComputerUseState"] = None

    def __new__(cls) -> "ComputerUseState":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.screen_width = DEFAULT_WIDTH
            self.screen_height = DEFAULT_HEIGHT
            self._initialized = True

    def configure(self, width: int, height: int) -> None:
        """Configure screen dimensions."""
        self.screen_width = width
        self.screen_height = height


# Global state
_state = ComputerUseState()


def get_computer_use_state() -> ComputerUseState:
    """Get the Computer Use state instance."""
    return _state


def create_computer_use_tools() -> Dict[str, callable]:
    """
    Create Computer Use MCP tools dictionary.

    Returns a dictionary of tool functions for screen capture and GUI automation.
    """
    state = get_computer_use_state()

    async def screenshot() -> Dict[str, Any]:
        """
        Capture the current screen.

        Returns:
            Dictionary with base64-encoded PNG screenshot
        """
        try:
            import mss
            from PIL import Image

            with mss.mss() as sct:
                # Capture primary monitor
                monitor = sct.monitors[1]
                img = sct.grab(monitor)

                # Convert to PIL Image
                pil_img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")

                # Resize if larger than configured dimensions
                if pil_img.width > state.screen_width or pil_img.height > state.screen_height:
                    pil_img.thumbnail((state.screen_width, state.screen_height))

                # Convert to base64 PNG
                buffer = io.BytesIO()
                pil_img.save(buffer, format="PNG")
                img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

                logger.info(f"Screenshot captured: {pil_img.width}x{pil_img.height}")
                return {
                    "type": "image",
                    "media_type": "image/png",
                    "data": img_base64,
                    "width": pil_img.width,
                    "height": pil_img.height,
                }

        except ImportError as e:
            logger.error(f"Missing dependency: {e}")
            return {"error": f"Missing dependency: {e}"}
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return {"error": str(e)}

    async def click(
        x: int,
        y: int,
        button: Literal["left", "right", "middle"] = "left",
        clicks: int = 1
    ) -> str:
        """
        Click at specified screen coordinates.

        Args:
            x: X coordinate
            y: Y coordinate
            button: Mouse button (left, right, middle)
            clicks: Number of clicks (1 for single, 2 for double)

        Returns:
            Click status message
        """
        try:
            import pyautogui

            pyautogui.click(x=x, y=y, button=button, clicks=clicks)
            click_type = "double-click" if clicks == 2 else "click"
            logger.info(f"{button} {click_type} at ({x}, {y})")
            return f"Clicked {button} button at ({x}, {y})"

        except Exception as e:
            logger.error(f"Click failed: {e}")
            return f"Click failed: {str(e)}"

    async def type_text(text: str) -> str:
        """
        Type text at the current cursor position.

        Args:
            text: Text to type

        Returns:
            Typing status message
        """
        try:
            import pyautogui

            pyautogui.typewrite(text, interval=0.02)
            logger.info(f"Typed {len(text)} characters")
            return f"Typed: {text[:50]}{'...' if len(text) > 50 else ''}"

        except Exception as e:
            logger.error(f"Type failed: {e}")
            return f"Type failed: {str(e)}"

    async def key(keys: str) -> str:
        """
        Press a key or key combination.

        Args:
            keys: Key(s) to press (e.g., "enter", "ctrl+s", "alt+f4")

        Returns:
            Key press status message
        """
        try:
            import pyautogui

            if "+" in keys:
                # Key combination
                key_list = keys.split("+")
                pyautogui.hotkey(*key_list)
            else:
                # Single key
                pyautogui.press(keys)

            logger.info(f"Pressed key(s): {keys}")
            return f"Pressed: {keys}"

        except Exception as e:
            logger.error(f"Key press failed: {e}")
            return f"Key press failed: {str(e)}"

    async def move(x: int, y: int) -> str:
        """
        Move mouse to specified coordinates.

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            Move status message
        """
        try:
            import pyautogui

            pyautogui.moveTo(x, y)
            logger.info(f"Moved mouse to ({x}, {y})")
            return f"Moved to ({x}, {y})"

        except Exception as e:
            logger.error(f"Move failed: {e}")
            return f"Move failed: {str(e)}"

    async def scroll(
        direction: Literal["up", "down", "left", "right"],
        amount: int = 3
    ) -> str:
        """
        Scroll in specified direction.

        Args:
            direction: Scroll direction
            amount: Number of scroll units

        Returns:
            Scroll status message
        """
        try:
            import pyautogui

            if direction == "up":
                pyautogui.scroll(amount)
            elif direction == "down":
                pyautogui.scroll(-amount)
            elif direction == "left":
                pyautogui.hscroll(-amount)
            elif direction == "right":
                pyautogui.hscroll(amount)

            logger.info(f"Scrolled {direction} by {amount}")
            return f"Scrolled {direction} by {amount}"

        except Exception as e:
            logger.error(f"Scroll failed: {e}")
            return f"Scroll failed: {str(e)}"

    async def drag(
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        button: Literal["left", "right", "middle"] = "left"
    ) -> str:
        """
        Drag from one point to another.

        Args:
            start_x: Starting X coordinate
            start_y: Starting Y coordinate
            end_x: Ending X coordinate
            end_y: Ending Y coordinate
            button: Mouse button to hold during drag

        Returns:
            Drag status message
        """
        try:
            import pyautogui

            pyautogui.moveTo(start_x, start_y)
            pyautogui.drag(end_x - start_x, end_y - start_y, button=button)
            logger.info(f"Dragged from ({start_x}, {start_y}) to ({end_x}, {end_y})")
            return f"Dragged from ({start_x}, {start_y}) to ({end_x}, {end_y})"

        except Exception as e:
            logger.error(f"Drag failed: {e}")
            return f"Drag failed: {str(e)}"

    async def get_mouse_position() -> Dict[str, int]:
        """
        Get current mouse position.

        Returns:
            Dictionary with x and y coordinates
        """
        try:
            import pyautogui

            pos = pyautogui.position()
            return {"x": pos.x, "y": pos.y}

        except Exception as e:
            logger.error(f"Get position failed: {e}")
            return {"error": str(e)}

    # Return tool dictionary
    return {
        "screenshot": screenshot,
        "click": click,
        "type": type_text,
        "key": key,
        "move": move,
        "scroll": scroll,
        "drag": drag,
        "get_mouse_position": get_mouse_position,
    }
