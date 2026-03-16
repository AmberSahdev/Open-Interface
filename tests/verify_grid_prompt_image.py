import base64
import io
import os
import re
import sys
import tempfile
import types
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw


ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "app"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


CURRENT_SCREENSHOT_SIZE = (2400, 1400)


def _build_screenshot_fixture(size: tuple[int, int]) -> Image.Image:
    width, height = size
    image = Image.new("RGB", (width, height), color=(247, 248, 250))
    draw = ImageDraw.Draw(image)
    draw.rectangle(
        (20, 20, max(21, width - 20), max(21, height - 20)),
        outline=(120, 140, 180),
        width=2,
    )
    draw.rectangle(
        (40, 80, max(41, min(width - 40, 640)), max(81, min(height - 80, 260))),
        fill=(255, 255, 255),
    )
    draw.rectangle(
        (60, 110, max(61, min(width - 60, 580)), max(111, min(height - 110, 170))),
        outline=(80, 80, 80),
        width=2,
    )
    draw.rectangle(
        (
            max(41, width - 260),
            max(41, height - 120),
            max(42, width - 80),
            max(42, height - 60),
        ),
        fill=(24, 118, 242),
    )
    return image


def _install_pyautogui_stub() -> None:
    if "pyautogui" in sys.modules:
        return

    module = types.ModuleType("pyautogui")
    module.PAUSE = 0
    module.FAILSAFE = False

    def _noop(*args, **kwargs):
        return None

    module.size = lambda: (1600, 900)
    module.position = lambda: (0, 0)
    module.screenshot = lambda *args, **kwargs: _build_screenshot_fixture(
        CURRENT_SCREENSHOT_SIZE
    )
    for name in (
        "moveTo",
        "click",
        "doubleClick",
        "rightClick",
        "dragTo",
        "scroll",
        "hotkey",
        "press",
        "write",
        "keyDown",
        "keyUp",
        "mouseDown",
        "mouseUp",
    ):
        setattr(module, name, _noop)

    sys.modules["pyautogui"] = module


_install_pyautogui_stub()

from utils.screen import Screen
from utils.settings import Settings


TIMESTAMP_PATTERN = re.compile(r"^\d{2}月\d{2}日_\d{2}时\d{2}分\d{2}秒(?:_\d+)?\.png$")


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _decode_payload_image(image_base64: str) -> Image.Image:
    raw_bytes = base64.b64decode(image_base64)
    return Image.open(io.BytesIO(raw_bytes)).convert("RGB")


def _is_dark_red(pixel: tuple[int, int, int]) -> bool:
    red, green, blue = pixel
    return red >= 100 and green <= 40 and blue <= 40


def _is_red(pixel: tuple[int, int, int]) -> bool:
    red, green, blue = pixel
    return red >= 180 and green <= 90 and blue <= 90


def _read_rgb_pixel(
    image: Image.Image, x_position: int, y_position: int
) -> tuple[int, int, int]:
    pixel = image.getpixel((x_position, y_position))
    if not isinstance(pixel, tuple) or len(pixel) < 3:
        raise AssertionError(f"Expected RGB pixel at ({x_position}, {y_position}).")
    return int(pixel[0]), int(pixel[1]), int(pixel[2])


def _region_contains_matching_pixel(
    image: Image.Image,
    left: int,
    top: int,
    right: int,
    bottom: int,
    matcher,
) -> bool:
    clamped_left = max(0, left)
    clamped_top = max(0, top)
    clamped_right = min(image.width, right)
    clamped_bottom = min(image.height, bottom)

    for y_position in range(clamped_top, clamped_bottom):
        for x_position in range(clamped_left, clamped_right):
            if matcher(_read_rgb_pixel(image, x_position, y_position)):
                return True

    return False


def _build_payload(
    *,
    screenshot_size: tuple[int, int],
    save_model_prompt_images: bool,
    archive_dir: Path | None,
    extra_patches: list,
) -> dict:
    global CURRENT_SCREENSHOT_SIZE
    CURRENT_SCREENSHOT_SIZE = screenshot_size

    class FakeSettings:
        def get_dict(self) -> dict[str, dict[str, bool]]:
            return {
                "advanced": {
                    "save_model_prompt_images": save_model_prompt_images,
                },
            }

        def get_settings_directory_path(self) -> str:
            return tempfile.gettempdir() + "/"

    with ExitStack() as stack:
        stack.enter_context(patch("utils.screen.Settings", FakeSettings))
        if archive_dir is not None:
            stack.enter_context(
                patch.object(
                    Screen,
                    "_get_prompt_image_archive_directory",
                    return_value=archive_dir,
                )
            )
        for item in extra_patches:
            stack.enter_context(item)

        return Screen().get_visual_prompt_payload()


def test_normal_path_grid_only_payload_and_archive() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        archive_dir = Path(temp_dir)
        payload = _build_payload(
            screenshot_size=(2400, 1400),
            save_model_prompt_images=True,
            archive_dir=archive_dir,
            extra_patches=[],
        )

        frame_context = payload["frame_context"]
        archived_files = sorted(archive_dir.glob("*.png"))
        assert_true(
            len(archived_files) == 1, "Expected exactly one archived prompt image."
        )
        archived_path = archived_files[0]

        violations: list[str] = []
        if TIMESTAMP_PATTERN.match(archived_path.name) is None:
            violations.append(
                "Archive filename should use MM月DD日_HH时MM分SS秒 format."
            )
        if frame_context.get("model_prompt_image_path") != str(archived_path):
            violations.append(
                "frame_context.model_prompt_image_path should point to archived prompt image."
            )

        encoded_bytes = base64.b64decode(payload["annotated_image_base64"])
        if archived_path.read_bytes() != encoded_bytes:
            violations.append(
                "Archived image should be the final prompt image before base64 encoding."
            )

        if "grid_reference" not in frame_context:
            violations.append(
                "frame_context should include grid_reference for pure grid coordinate contract."
            )
        disallowed_fields = [
            "anchors",
            "raw_visual_candidates",
            "ocr_text_blocks",
            "semantic_regions",
        ]
        leaked_fields = [field for field in disallowed_fields if field in frame_context]
        if leaked_fields:
            violations.append(
                f"Pure grid payload must not expose semantic fields: {leaked_fields}"
            )

        assert_true(not violations, "; ".join(violations))


def test_boundary_small_screen_must_still_expose_percent_tick_contract() -> None:
    payload = _build_payload(
        screenshot_size=(101, 99),
        save_model_prompt_images=False,
        archive_dir=None,
        extra_patches=[],
    )

    frame_context = payload["frame_context"]
    final_prompt_image = _decode_payload_image(payload["annotated_image_base64"])
    captured_screen = frame_context["captured_screen"]

    violations: list[str] = []
    grid_reference = frame_context.get("grid_reference")
    if not isinstance(grid_reference, dict):
        violations.append(
            "Boundary case should still provide grid_reference dictionary."
        )
    else:
        if grid_reference.get("major_tick_percent") != 3:
            violations.append("grid_reference.major_tick_percent should be 3.")
        if grid_reference.get("minor_tick_percent") != 3:
            violations.append("grid_reference.minor_tick_percent should be 3.")
        if grid_reference.get("coordinate_system") != "percent":
            violations.append("grid_reference.coordinate_system should be percent.")
        axes = set(grid_reference.get("axes") or [])
        if axes != {"top", "left"}:
            violations.append("grid_reference.axes should be exactly [top, left].")

        padding = grid_reference.get("padding") or {}
        origin_x = int(padding.get("left") or 0)
        origin_y = int(padding.get("top") or 0)
        content_right = origin_x + int(captured_screen.get("width") or 0)
        content_bottom = origin_y + int(captured_screen.get("height") or 0)
        x_3_percent = origin_x + int(
            round(int(captured_screen.get("width") or 0) * 0.03)
        )
        x_99_percent = origin_x + int(
            round(int(captured_screen.get("width") or 0) * 0.99)
        )
        y_3_percent = origin_y + int(
            round(int(captured_screen.get("height") or 0) * 0.03)
        )
        y_99_percent = origin_y + int(
            round(int(captured_screen.get("height") or 0) * 0.99)
        )

        if not _is_dark_red(
            _read_rgb_pixel(final_prompt_image, x_3_percent, origin_y + 10)
        ):
            violations.append("3% vertical grid line should render as dark red.")
        if not _is_dark_red(
            _read_rgb_pixel(final_prompt_image, origin_x + 10, y_3_percent)
        ):
            violations.append("3% horizontal grid line should render as dark red.")
        if not _is_dark_red(
            _read_rgb_pixel(final_prompt_image, x_99_percent, origin_y + 10)
        ):
            violations.append("99% vertical grid line should render as dark red.")
        if not _is_dark_red(
            _read_rgb_pixel(final_prompt_image, origin_x + 10, y_99_percent)
        ):
            violations.append("99% horizontal grid line should render as dark red.")
        if not _is_dark_red(
            _read_rgb_pixel(final_prompt_image, content_right, origin_y + 10)
        ):
            violations.append(
                "100% vertical endpoint tick should still render as dark red."
            )
        if not _is_dark_red(
            _read_rgb_pixel(final_prompt_image, origin_x + 10, content_bottom)
        ):
            violations.append(
                "100% horizontal endpoint tick should still render as dark red."
            )

        if not _region_contains_matching_pixel(
            final_prompt_image,
            0,
            0,
            final_prompt_image.width,
            origin_y,
            _is_red,
        ):
            violations.append("Top axis labels should render in red.")
        if not _region_contains_matching_pixel(
            final_prompt_image,
            0,
            0,
            origin_x,
            final_prompt_image.height,
            _is_red,
        ):
            violations.append("Left axis labels should render in red.")

    if final_prompt_image.width <= 0 or final_prompt_image.height <= 0:
        violations.append("Final prompt image dimensions should always be positive.")
    if final_prompt_image.width == int(
        captured_screen.get("width", 0)
    ) and final_prompt_image.height == int(captured_screen.get("height", 0)):
        violations.append(
            "Final prompt image dimensions should reflect prompt rendering result, not raw capture dimensions."
        )

    assert_true(not violations, "; ".join(violations))


def test_negative_ocr_pipeline_must_not_be_invoked() -> None:
    payload = _build_payload(
        screenshot_size=(1280, 720),
        save_model_prompt_images=False,
        archive_dir=None,
        extra_patches=[
            patch(
                "utils.screen.create_ocr_backend",
                side_effect=AssertionError(
                    "OCR backend must not be called in pure grid pipeline."
                ),
            )
        ],
    )

    frame_context = payload["frame_context"]
    assert_true(
        "ocr_text_blocks" not in frame_context,
        "Negative path: ocr_text_blocks must be removed from frame_context.",
    )
    assert_true(
        "semantic_regions" not in frame_context,
        "Negative path: semantic_regions must be removed from frame_context.",
    )


def test_sqlite_save_model_prompt_images_persistence() -> None:
    with tempfile.TemporaryDirectory() as temp_home:
        original_home = os.environ.get("HOME")
        os.environ["HOME"] = temp_home
        try:
            settings = Settings()
            first_saved = settings.save_settings(
                {"advanced": {"save_model_prompt_images": True}}
            )
            assert_true(
                first_saved.get("advanced", {}).get("save_model_prompt_images") is True,
                "save_settings should persist advanced.save_model_prompt_images=True.",
            )

            second_saved = settings.save_settings(
                {"advanced": {"save_model_prompt_images": False}}
            )
            assert_true(
                second_saved.get("advanced", {}).get("save_model_prompt_images")
                is False,
                "save_settings should persist advanced.save_model_prompt_images=False.",
            )

            reloaded = Settings().get_dict()
            assert_true(
                reloaded.get("advanced", {}).get("save_model_prompt_images") is False,
                "advanced.save_model_prompt_images should be reloaded from SQLite.",
            )
        finally:
            if original_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = original_home


TEST_CASES = [
    ("Category 1 - Normal Path", test_normal_path_grid_only_payload_and_archive),
    (
        "Category 2 - Boundary Conditions",
        test_boundary_small_screen_must_still_expose_percent_tick_contract,
    ),
    (
        "Category 3 - Error/Negative Path",
        test_negative_ocr_pipeline_must_not_be_invoked,
    ),
    ("Settings Persistence Coverage", test_sqlite_save_model_prompt_images_persistence),
]


def main() -> int:
    failed = 0
    for case_name, case in TEST_CASES:
        print(f"=== RUN {case_name}")
        try:
            case()
        except Exception as exc:
            failed += 1
            print(f"--- FAIL {case_name}: {exc}")
        else:
            print(f"--- PASS {case_name}")

    print("=== RED TEST SUMMARY ===")
    print(f"total={len(TEST_CASES)}")
    print(f"failed={failed}")
    print(f"passed={len(TEST_CASES) - failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
