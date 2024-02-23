"""
Usage:
    python3.9 setup.py py2app
"""

from setuptools import setup


PACKAGES = ['urllib3', 'requests', 'openai', 'pyautogui']
print(f'PACKAGES = {PACKAGES}')



APP = ['app/app.py']
DATA_FILES = ['app/resources/icon.png', 'app/resources/microphone.png', 'app/resources/context.txt']

OPTIONS = {
    'argv_emulation': True,
    'iconfile': 'app/resources/icon.PNG',
    'plist': {
        'LSUIElement': True,
    },
    'packages': PACKAGES,
    'excludes': ['rubicon', 'pyobjc-core']
}

setup(
    app=APP,
    name='Open Interface',
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
    install_requires=PACKAGES
)

"""
def get_packages_from_requirements():
    packages = []
    with open('requirements.txt', 'r') as file:
        for line in file:
            # Split on the first occurrence of ==, >=, or <= and take the first part
            package = line.split('==')[0].split('>=')[0].split('<=')[0].strip()
            if package:  
                if package == "SpeechRecognition":
                    # Some modules don't follow the style guide for pip install <lowercase>
                    packages.append(package)
                else:
                    packages.append(package.lower())

    return packages

PACKAGES = get_packages_from_requirements()
"""
