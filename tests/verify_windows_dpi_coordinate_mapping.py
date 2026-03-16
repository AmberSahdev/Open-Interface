import os
import sys

from PIL import Image, ImageDraw


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
APP_DIR = os.path.join(ROOT_DIR, 'app')

if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)


from verifier import StepVerifier


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def build_windows_scaled_images() -> tuple[Image.Image, Image.Image]:
    before = Image.new('RGB', (2000, 1000), color='white')
    after = before.copy()
    draw_after = ImageDraw.Draw(after)
    draw_after.rectangle((920, 420, 1080, 580), fill='blue', outline='black', width=2)
    return before, after


def verify_windows_dpi_scaled_local_region_mapping() -> None:
    before, after = build_windows_scaled_images()
    verifier = StepVerifier()
    result = verifier.verify_step(
        {
            'function': 'click',
            'expected_outcome': 'The target region should visibly change.',
        },
        {
            'x': 500,
            'y': 250,
            'coordinate_resolution': {
                'logical_screen': {
                    'width': 1000,
                    'height': 500,
                }
            },
        },
        before,
        after,
    )

    assert_true(
        result['status'] == 'passed',
        'Verifier should still detect local change when logical and captured screen sizes differ.',
    )


def main() -> None:
    verify_windows_dpi_scaled_local_region_mapping()
    print('windows DPI coordinate mapping verification passed')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'windows DPI coordinate mapping verification failed: {exc}')
        sys.exit(1)
    sys.exit(0)
