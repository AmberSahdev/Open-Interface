import os
import re
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import patch

from PIL import Image


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../app")))

if "pyautogui" not in sys.modules:
    fake_pyautogui = types.ModuleType("pyautogui")
    setattr(fake_pyautogui, "size", lambda: (1600, 900))
    setattr(fake_pyautogui, "press", lambda *args, **kwargs: None)
    setattr(fake_pyautogui, "click", lambda *args, **kwargs: None)
    setattr(fake_pyautogui, "doubleClick", lambda *args, **kwargs: None)
    setattr(fake_pyautogui, "tripleClick", lambda *args, **kwargs: None)
    setattr(fake_pyautogui, "moveTo", lambda *args, **kwargs: None)
    setattr(fake_pyautogui, "dragTo", lambda *args, **kwargs: None)
    setattr(fake_pyautogui, "screenshot", lambda *args, **kwargs: None)
    sys.modules["pyautogui"] = fake_pyautogui

from utils.screen import Screen
from utils.settings import Settings


TIMESTAMP_PATTERN = re.compile(r"^\d{2}月\d{2}日_\d{2}时\d{2}分\d{2}秒(?:_\d+)?\.png$")


class FakeSettings:
    def get_dict(self) -> dict[str, dict[str, bool] | str | bool]:
        return {
            "advanced": {
                "save_model_prompt_images": True,
            },
        }

    def get_settings_directory_path(self) -> str:
        return tempfile.gettempdir() + "/"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    settings = Settings()
    normalized = settings._validate_and_normalize(
        {
            **settings.get_dict(),
            "advanced": {
                **settings.get_dict().get("advanced", {}),
                "save_model_prompt_images": True,
            },
        }
    )
    assert_true(
        normalized["advanced"]["save_model_prompt_images"] is True,
        "Settings should persist advanced.save_model_prompt_images.",
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        screen = Screen()
        annotated_image = Image.new("RGB", (2400, 1400), color="white")
        frame_context = {
            "logical_screen": {"width": 1600, "height": 900},
            "captured_screen": {"width": 2400, "height": 1400},
            "anchors": [],
            "raw_visual_candidates": [],
            "ocr_text_blocks": [],
            "semantic_regions": [],
            "screen_state": {},
        }

        with (
            patch("utils.screen.Settings", FakeSettings),
            patch.object(
                Screen,
                "_build_annotated_frame",
                return_value=(annotated_image, frame_context),
            ),
            patch.object(
                Screen,
                "_get_prompt_image_archive_directory",
                return_value=Path(temp_dir),
            ),
        ):
            payload = screen.get_visual_prompt_payload()

        archive_files = sorted(Path(temp_dir).glob("*.png"))
        assert_true(
            len(archive_files) == 1,
            "Exactly one archived prompt image should be created.",
        )
        archive_file = archive_files[0]
        assert_true(
            TIMESTAMP_PATTERN.match(archive_file.name) is not None,
            "Archive file name should use month-day-hour-minute-second format.",
        )
        assert_true(
            payload["frame_context"].get("model_prompt_image_path")
            == str(archive_file),
            "frame_context should expose archived prompt image path.",
        )

        with Image.open(archive_file) as saved_image:
            assert_true(
                saved_image.width == 2400,
                "Archived prompt image should preserve the final prompt image width when it is already within the configured limit.",
            )
            assert_true(
                saved_image.height == 1400,
                "Archived prompt image should preserve the final prompt image height when it is already within the configured limit.",
            )

            print(f"archived prompt image: {archive_file}")
            print(
                f"archived prompt image size: {saved_image.width}x{saved_image.height}"
            )
        print("prompt image archive verification passed")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"prompt image archive verification failed: {exc}")
        sys.exit(1)
    sys.exit(0)
