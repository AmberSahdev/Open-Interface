import base64
import json
import os
from pathlib import Path


class Settings:
    API_KEYS = {
        "api_key": "OPENAI_API_KEY",
        "gemini_api_key": "GEMINI_API_KEY"
    }

    def __init__(self):
        self.settings_file_path = self.get_settings_directory_path() + 'settings.json'
        os.makedirs(os.path.dirname(self.settings_file_path), exist_ok=True)
        self.settings = self.load_settings_from_file()

    def get_settings_directory_path(self):
        return str(Path.home()) + '/.open-interface/'

    def get_dict(self) -> dict[str, str]:
        return self.settings

    def _read_settings_file(self) -> dict[str, str]:
        if os.path.exists(self.settings_file_path):
            with open(self.settings_file_path, 'r') as file:
                try:
                    return json.load(file)
                except Exception:
                    return {}
        return {}

    def save_settings_to_file(self, settings_dict) -> None:
        settings = self._read_settings_file()

        for setting_name, setting_val in settings_dict.items():
            if setting_val is not None:
                if setting_name in self.API_KEYS:
                    os.environ[self.API_KEYS[setting_name]] = setting_val  # Set environment variable
                    settings[setting_name] = base64.b64encode(setting_val.encode()).decode()  # Encode key
                else:
                    settings[setting_name] = setting_val

        with open(self.settings_file_path, 'w+') as file:
            json.dump(settings, file, indent=4)

    def load_settings_from_file(self) -> dict[str, str]:
        settings = self._read_settings_file()

        # Decode the API keys
        for key in self.API_KEYS:
            if key in settings:
                settings[key] = base64.b64decode(settings[key]).decode()

        return settings
