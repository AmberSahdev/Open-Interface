"""
PyInstaller build script

> python3.9 -m venv venv
> source venv/bin/activate
> python3.9 -m pip install -r requirements.txt
> python3.9 build.py

NOTES:
    1. For use in future projects, note that pyinstaller will print hundreds of unrelated error messages, but to find
        the critical error start scrolling upwards from the bottom and find the first error before it starts cleanup and
        destroying resources. It will likely be an import or a path error.
    2. Extra steps before using multiprocessing might be required
        https://www.pyinstaller.org/en/stable/common-issues-and-pitfalls.html#why-is-calling-multiprocessing-freeze-support-required
    3. Change file reads accordingly
        https://pyinstaller.org/en/stable/runtime-information.html#placing-data-files-at-expected-locations-inside-the-bundle
    4. Code signing for MacOS
        https://github.com/pyinstaller/pyinstaller/wiki/Recipe-OSX-Code-Signing
        https://developer.apple.com/library/archive/technotes/tn2206/_index.html
        https://gist.github.com/txoof/0636835d3cc65245c6288b2374799c43
        https://github.com/txoof/codesign
        https://github.com/The-Nicholas-R-Barrow-Company-LLC/python3-pyinstaller-base-app-codesigning
        https://pyinstaller.org/en/stable/feature-notes.html#macos-binary-code-signing
"""

import os
import platform

import PyInstaller.__main__
from app.version import version


def build():
    input("Did you remember to increment version.py?")

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
        '--windowed',  # Remove this if your application is a console program, also helps to remove this while debugging
        # '--onefile',  # NOTE: Might not work on Windows. Also discouraged to enable both windowed and one file on Mac.

        # Where to find necessary packages to bundle (python3 -m pip show xxx)
        '--paths=./venv/lib/python3.9/site-packages',

        # Packaging fails without explicitly including these modules here as shown by the logs outputted by debug=all
        '--hidden-import=pyautogui',
        '--hidden-import=appdirs',
        '--hidden-import=pyparsing',
        # NOTE: speech_recognition is the name of the directory that this package is in within ../site-packages/,
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
        pyinstaller_options.extend([])
    elif platform.system() == 'Darwin':  # MacOS
        pyinstaller_options.extend([])
    elif platform.system() == 'Linux':
        pyinstaller_options.extend([])
    """

    # Run PyInstaller with the specified options
    PyInstaller.__main__.run(pyinstaller_options)
    print('Done. Check dist/ for executables.')

    # Zip the app
    print('Zipping the executables')

    if platform.system() == 'Darwin':  # MacOS
        app_name = 'Open\\ Interface'
        zip_name = app_name + '-v' + str(version) + '-MacOS' + '.zip'
        zip_cli_command = 'cd dist/; zip -r9 ' + zip_name + ' ' + app_name + '.app'
        input(f'zip_cli_command - {zip_cli_command} \nExecute?')
        os.system(zip_cli_command)


if __name__ == "__main__":
    build()
