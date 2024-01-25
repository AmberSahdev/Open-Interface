import os

"""
List the apps the user has locally, default browsers, etc. 
"""
locally_installed_apps = [app for app in os.listdir('/Applications') if app.endswith('.app')]
default_browser = "safari"  # "firefox"
