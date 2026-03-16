import sys


def get_platform_name() -> str:
    if sys.platform == 'darwin':
        return 'macos'
    if sys.platform.startswith('win'):
        return 'windows'
    if sys.platform.startswith('linux'):
        return 'linux'
    return 'unknown'


def is_macos() -> bool:
    return get_platform_name() == 'macos'


def is_windows() -> bool:
    return get_platform_name() == 'windows'


def is_linux() -> bool:
    return get_platform_name() == 'linux'
