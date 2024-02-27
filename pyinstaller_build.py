"""
> python3.9 -m venv venv
> source venv/bin/activate
> python3.9 -m pip install -r requirements.txt
> python3.9 build.py

NOTES:
    1. extra steps before using multiprocessing might be required
        https://www.pyinstaller.org/en/stable/common-issues-and-pitfalls.html#why-is-calling-multiprocessing-freeze-support-required
    2. Change file reads accordingly
        https://pyinstaller.org/en/stable/runtime-information.html#placing-data-files-at-expected-locations-inside-the-bundle
    3. Code signing for MacOS
        https://github.com/pyinstaller/pyinstaller/wiki/Recipe-OSX-Code-Signing
        https://developer.apple.com/library/archive/technotes/tn2206/_index.html
        https://gist.github.com/txoof/0636835d3cc65245c6288b2374799c43
        https://github.com/txoof/codesign
        https://github.com/The-Nicholas-R-Barrow-Company-LLC/python3-pyinstaller-base-app-codesigning
"""

import os
import platform

import PyInstaller.__main__


def build():
    # Path to your main application script
    app_script = os.path.join('app', 'app.py')

    # Common PyInstaller options
    pyinstaller_options = [
        '--clean',
        '--noconfirm',

        # Debug
        # '--debug=all',

        # --- Basics --- #
        '--name=Open Interface',
        '--icon=app/resources/icon.png',
        '--onefile',  # NOTE: Might not work on Windows
        '--windowed',  # Remove this if your application is a console program, also helps to remove this while debugging

        # Where to find necessary packages to bundle (python3 -m pip show xxx)
        '--paths=./venv/lib/python3.9/site-packages',

        # Packaging fails without explicitly including these modules here as shown by the logs outputted by debug=all
        '--hidden-import=pyautogui',
        '--hidden-import=appdirs',
        '--hidden-import=pyparsing',
        # NOTE: This is the name of the directory that this package is in within ../site-packages/,
        # whereas the pypi name is SpeechRecognition (pip install SpeechRecognition).
        # This was hard to pin down and took a long time to debug.
        '--hidden-import=speech_recognition',

        # Static files and resources --add-data=src:dest
        # - File reads change accordingly - https://pyinstaller.org/en/stable/runtime-information.html#placing-data-files-at-expected-locations-inside-the-bundle
        '--add-data=app/resources/*:resources',

        # Manually including source code and submodules because app doesn't launch without it
        '--add-data=app/*.py:.',
        '--add-data=app/utils/*.py:utils',  # Submodules need to be included manually

        app_script
    ]

    """
    # Platform-specific options
    if platform.system() == 'Windows':
        pyinstaller_options.extend([
            '--onefile',  # Uncomment this if you want a single executable file
            # '--icon=someicon.ico'  # Path to an icon file for the Windows executable
        ])
    elif platform.system() == 'Darwin':  # macOS
        pyinstaller_options.extend([
            '--onefile',  # Uncomment this if you want a single executable file
            # '--icon=someicon.icns'  # Path to an icon file for the macOS executable
        ])
    elif platform.system() == 'Linux':
        pyinstaller_options.extend([
            '--onefile',  # Uncomment this if you want a single executable file
            # Additional Linux-specific options here
        ])
    """

    # Run PyInstaller with the specified options
    PyInstaller.__main__.run(pyinstaller_options)


if __name__ == "__main__":
    build()
