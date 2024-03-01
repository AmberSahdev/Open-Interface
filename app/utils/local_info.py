import os
import platform

"""
List the apps the user has locally, default browsers, etc. 
"""
try:
    locally_installed_apps: list[str] = [app for app in os.listdir('/Applications') if app.endswith('.app')]
except:
    locally_installed_apps: list[str] = ["Unknown"]

operating_system: str = platform.platform()
