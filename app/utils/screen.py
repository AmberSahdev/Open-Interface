import base64
import io

import pyautogui
from PIL import Image


class Screen:
    def get_size(self) -> tuple[int, int]:
        screen_width, screen_height = pyautogui.size()  # Get the size of the primary monitor.
        return screen_width, screen_height

    def get_screenshot(self) -> Image.Image:
        # Enable screen recording from settings
        img = pyautogui.screenshot()  # Takes roughly 100ms # img.show()
        return img

    def get_screenshot_in_base64(self) -> str:
        img_bytes = io.BytesIO()
        img = self.get_screenshot()
        img.save(img_bytes, format='PNG')  # Save the screenshot to an in-memory file
        img_bytes.seek(0)

        # Encode this image file in base64
        encoded_image = base64.b64encode(img_bytes.read()).decode('utf-8')

        return encoded_image
