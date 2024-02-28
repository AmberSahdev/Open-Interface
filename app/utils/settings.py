import base64
import json
import os
from pathlib import Path


class Settings:
    def __init__(self):
        self.settings_file_path = str(Path.home()) + "/.open-interface/settings.json"
        os.makedirs(os.path.dirname(self.settings_file_path), exist_ok=True)
        self.settings = self.load_settings_from_file()

    def get_dict(self):
        return self.settings

    def save_settings_to_file(self, settings_dict):
        settings = {}

        if os.path.exists(self.settings_file_path):
            with open(self.settings_file_path, 'r') as file:
                try:
                    settings = json.load(file)
                except:
                    settings = {}

        for setting_name in settings_dict:
            setting_val = settings_dict[setting_name]
            if setting_val:
                if setting_name == "api_key":
                    api_key = settings_dict["api_key"]
                    os.environ["OPENAI_API_KEY"] = api_key  # Set environment variable
                    encoded_api_key = base64.b64encode(api_key.encode()).decode()
                    settings['api_key'] = encoded_api_key
                else:
                    settings[setting_name] = setting_val

        with open(self.settings_file_path, 'w+') as file:
            json.dump(settings, file, indent=4)

    def load_settings_from_file(self):
        if os.path.exists(self.settings_file_path):
            with open(self.settings_file_path, 'r') as file:
                try:
                    settings = json.load(file)
                except:
                    return {}

                # Decode the API key
                if 'api_key' in settings:
                    decoded_api_key = base64.b64decode(settings['api_key']).decode()
                    settings['api_key'] = decoded_api_key

                return settings
        else:
            return {}
