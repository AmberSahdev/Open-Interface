import os
import shutil
import subprocess

def run_terminal_commands(commands):
    for command in commands:
        process = subprocess.Popen(command.split(), stdout=subprocess.PIPE)
        output, error = process.communicate()


# 1. Remove previous files
directories_to_remove = ["./build", "./dist"]
for dir in directories_to_remove:
    try:
        shutil.rmtree(dir)
    except:
        pass

# 2 Make necessary directories and copy over resources
# Copy over icon
commands = ["mkdir macos", "mkdir nudge/resources", "cp ../nudge_client/nudge/resources/icon.PNG nudge/resources/", "cp ../nudge_client/nudge/resources/taskbar.PNG nudge/resources/"]
run_commands(commands)
