import subprocess

try:
    import pyperclip
except Exception:
    pyperclip = None

from platform_support.detector import get_platform_name


class ClipboardAdapter:
    def __init__(self, platform_name: str | None = None):
        if platform_name is None:
            platform_name = get_platform_name()
        self.platform_name = platform_name

    def read_text(self) -> str:
        if pyperclip is not None:
            return str(pyperclip.paste())

        if self.platform_name == 'macos':
            return self._run_and_read(['pbpaste'])
        if self.platform_name == 'windows':
            return self._run_and_read([
                'powershell',
                '-NoProfile',
                '-Command',
                'Get-Clipboard -Raw',
            ])

        raise RuntimeError('Clipboard backend is unavailable on this platform.')

    def write_text(self, text: str) -> None:
        if pyperclip is not None:
            pyperclip.copy(text)
            return

        if self.platform_name == 'macos':
            self._run_with_input(['pbcopy'], text)
            return

        if self.platform_name == 'windows':
            self._run_with_input(['clip'], text)
            return

        raise RuntimeError('Clipboard backend is unavailable on this platform.')

    def _run_and_read(self, command: list[str]) -> str:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            stderr = str(result.stderr or '').strip()
            command_name = command[0]
            raise RuntimeError(f'{command_name} exited with code {result.returncode}: {stderr}')
        return str(result.stdout)

    def _run_with_input(self, command: list[str], text: str) -> None:
        result = subprocess.run(
            command,
            input=text,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            stderr = str(result.stderr or '').strip()
            command_name = command[0]
            raise RuntimeError(f'{command_name} exited with code {result.returncode}: {stderr}')
