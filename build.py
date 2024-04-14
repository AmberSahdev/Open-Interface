"""
PyInstaller build script

> python3 -m venv env
> source env/bin/activate (env Scripts activate for Windows)
> python3 -m pip install -r requirements.txt
> python3 -m pip install pyinstaller
> python3 build.py


Platform specific libraries that MIGHT be needed for compiling binaries
Linux
- sudo apt install portaudio19-dev
- sudo apt-get install python3-tk python3-dev

MacOS
- brew install portaudio
- if you're using pyenv, you might also need to install tkinter manually. 
    I followed this guide https://dev.to/xshapira/using-tkinter-with-pyenv-a-simple-two-step-guide-hh5. 

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
import sys

import PyInstaller.__main__

from app.version import version


def build(signing_key=None):
    input("Did you remember to increment version.py? " + str(version))
    app_name = "Open\\ Interface"

    compile(signing_key)

    macos = platform.system() == 'Darwin'
    if macos and signing_key:  
        # Codesign
        os.system(
            f'codesign --deep --force --verbose --sign "{signing_key}" dist/{app_name}.app --options runtime')

    zip_name = zip()

    if macos and signing_key:  
        keychain_profile = signing_key.split('(')[0].strip()
        
        # Notarize
        os.system(f'xcrun notarytool submit --wait --keychain-profile "{keychain_profile}" --verbose dist/{zip_name}')
        input(f'Check whether notarization was successful. You can check further logs using "xcrun notarytool log --keychain-profile {keychain_profile} <run-id>"')

        # Staple
        os.system(f'xcrun stapler staple dist/{app_name}.app')

        # Zip the signed, stapled file
        zip_name = zip()


def compile(signing_key=None):
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

    # Platform-specific options
    if platform.system() == 'Darwin':  # MacOS
        pyinstaller_options.extend([
            f'--codesign-identity={signing_key}'
        ])

        # Apple Notarization has a problem because this binary used in speech_recognition is signed with too old an SDK
        from PyInstaller.utils.osx import set_macos_sdk_version
        set_macos_sdk_version('env/lib/python3.12/site-packages/speech_recognition/flac-mac', 10, 9, 0) # NOTE: Change the path according to where your binary is located

    elif platform.system() == 'Linux':
        pyinstaller_options.extend([
            '--hidden-import=PIL._tkinter_finder',
            '--hidden-import=openai',
            '--onefile'
        ])
    elif platform.system() == 'Windows':
        pyinstaller_options.extend([
            '--onefile'
        ])

    # Run PyInstaller with the specified options
    PyInstaller.__main__.run(pyinstaller_options)
    print('Done. Check dist/ for executables.')


def zip():
    # Zip the app
    print('Zipping the executables')
    app_name = 'Open\\ Interface'

    zip_name = 'Open-Interface-v' + str(version)
    if platform.system() == 'Darwin':  # MacOS
        if platform.processor() == 'arm':
            zip_name = zip_name + '-MacOS-M-Series' + '.zip'
        else:
            zip_name = zip_name + '-MacOS-Intel' + '.zip'
        
        # Special zip command for macos to keep the complex directory metadata intact to keep the codesigning valid 
        zip_cli_command = 'cd dist/; ditto -c -k --sequesterRsrc --keepParent ' + app_name + '.app ' + zip_name
    elif platform.system() == 'Linux':
        zip_name = zip_name + '-Linux.zip'
        zip_cli_command = 'cd dist/; zip -r9 ' + zip_name + ' ' + app_name
    elif platform.system() == 'Windows':
        zip_name = zip_name + '-Windows.zip'
        zip_cli_command = 'cd dist & powershell Compress-Archive -Path \'Open Interface.exe\' -DestinationPath ' + zip_name

    # input(f'zip_cli_command - {zip_cli_command} \nExecute?')
    os.system(zip_cli_command)
    return zip_name


if __name__ == "__main__":
    apple_code_signing_key = None
    if len(sys.argv) > 1:
        apple_code_signing_key = sys.argv[1]  # Developer ID Application: ... (...)
        print("apple_code_signing_key: ", apple_code_signing_key)

    build(apple_code_signing_key)
