from time import sleep

import pyautogui


class Interpreter:
    def __init__(self):
        pass

    def process(self, json_commands):
        for command in json_commands:
            function_name = command["function"]
            parameters = command.get('parameters', {})
            print(f"Now performing - {function_name} - {command.get('human_readable_justification')}")
            self.execute_function(function_name, parameters)

    def execute_function(self, function_name, parameters):
        """
            We are expecting only two types of function calls below
            1. time.sleep() - to wait for web pages, applications, and other things to load.
            2. pyautogui calls to interact with system's mouse and keyboard.
        """
        if function_name == "sleep" and parameters.get("secs"):
            sleep(parameters.get("secs"))
        elif hasattr(pyautogui, function_name):
            # Execute the corresponding pyautogui function i.e. Keyboard or Mouse commands.
            function_to_call = getattr(pyautogui, function_name)

            # Special handling for the 'write' function
            if function_name == 'write' and ('string' in parameters or 'text' in parameters):
                # 'write' function expects a string, not a 'text' keyword argument. LLM sometimes gets confused on what to send.
                string_to_write = parameters.get('string') or parameters.get('text')
                interval = parameters.get('interval', 0.0)
                function_to_call(string_to_write, interval=interval)
            elif function_name == 'press' and ('keys' in parameters or 'key' in parameters):
                # 'press' can take a list of keys or a single key
                keys_to_press = parameters.get('keys') or parameters.get('key')
                presses = parameters.get('presses', 1)
                interval = parameters.get('interval', 0.0)

                """
                if isinstance(keys_to_press, list):
                    for key in keys_to_press:
                        function_to_call(key, presses=presses, interval=interval)
                else:
                    function_to_call(keys_to_press, presses=presses, interval=interval)
                """
                for key in keys_to_press:
                    function_to_call(key, presses=presses, interval=interval)

            elif function_name == 'hotkey':
                # 'hotkey' function expects multiple key arguments, not a list
                function_to_call(*parameters['keys'])
            else:
                # For other functions, pass the parameters as they are
                function_to_call(**parameters)
        else:
            print(f"No such function {function_name} in our interface's interpreter")
