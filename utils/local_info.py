import os
import platform

"""
List the apps the user has locally, default browsers, etc. 
"""
try:
    locally_installed_apps = [app for app in os.listdir('/Applications') if app.endswith('.app')]
except:
    locally_installed_apps = "Unknown"

default_browser = "firefox"  # "safari" # TODO: Get it from settings
operating_system = platform.platform()  # "MacOS"
