import platform

from platform_support.local_apps import get_installed_apps_sample

"""
List the apps the user has locally and basic OS information.
"""
try:
    locally_installed_apps: list[str] = get_installed_apps_sample()
except Exception as exc:
    print(f'Warning: failed to inspect locally installed apps: {exc}')
    locally_installed_apps = []

operating_system: str = platform.platform()
