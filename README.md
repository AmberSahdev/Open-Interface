# Open Interface

<picture>
	<img src="app/resources/icon.png" align="right" alt="Open Interface Logo" width="120" height="120">
</picture>

### Operate Your Computer Using LLMs
#### Complete Tedious Everyday-Tasks with No Effort 

Open Interface can
- Think for itself.
- Simulate keyboard and mouse input. 
- Take user requests through text or voice.
- Figure out how to execute user requests by sending the request and a current screenshot to a LLM backend (GPT-4V).
- Automatically execute the steps received from the LLM to operate your computer, periodically sending back a screenshot of the updated state. 


[![Github All Releases](https://img.shields.io/github/downloads/AmberSahdev/Open-Interface/total.svg)]()
![GitHub code size in bytes](https://img.shields.io/github/languages/code-size/AmberSahdev/Open-Interface)
![GitHub](https://img.shields.io/github/license/AmberSahdev/Open-Interface)
[![Code Coverage](https://img.shields.io/codecov/c/github/AmberSahdev/Open-Interface)](https://codecov.io/github/AmberSahdev/Open-Interface)


### Installation
<details>
    <summary><b>MacOS</b></summary>
    <ul>
        <li>Download the MacOS binary from the latest <a href="https://github.com/AmberSahdev/Open-Interface/releases/latest">release</a>.</li>
    </ul>
</details>
<details>
    <summary><b>Linux</b></summary>
    <ul>
        <li>Linux binary has been tested on Ubuntu 20.04 so far.</li>
        <li>Download the Linux binary from the latest <a href="https://github.com/AmberSahdev/Open-Interface/releases/latest">release</a>.</li>
        <li>Extract the executable and run it from the Terminal via <br>
        <code>./Open\ Interface</code></li>
    </ul>
</details>
<details>
    <summary><b>Windows</b></summary>
    The Windows executable build is still under progress.
</details>
<details>
    <summary><b>Setup</b></summary>
    - Set OpenAI Key
    - SETUP.md
</details>

### Demo
[Video](Video)


### Many of the Things it's Bad at

- Accurate spatial-reasoning and hence clicking buttons.
- Keeping track of itself in tabular contexts like excel and google sheets for similar reasons as stated above.
- Navigating complex GUI-rich applications like iMovie, Garage Band, etc.


### Future 
(*with better models trained on video walkthroughs like Youtube tutorials*)
- "Find my friends' music taste from Spotify and create a party playlist for tonight's event."
- "Create a couple of bass samples for me in Garage Band for my latest project."
- "Take the pictures from my Tahoe trip and make a White Lotus type montage in iMovie."

### Notes
- Cost: $0.05 - $0.20 per request. <br>(This will be much lower in the near future once GPT-4V enables assistant/stateful mode) 

### System Diagram 
```
+----------------------------------------------------+
| App                                                |
|                                                    |
|    +-------+                                       |
|    |  GUI  |                                       |
|    +-------+                                       |
|        ^                                           |
|        |                                           |
|        v                                           |
|  +-----------+  (Screenshot + Goal)  +-----------+ |
|  |           | --------------------> |           | |
|  |    Core   |                       |    LLM    | |
|  |           | <-------------------- |  (GPT-4V) | |
|  +-----------+    (Instructions)     +-----------+ |
|        |                                           |
|        v                                           |
|  +-------------+                                   |
|  | Interpreter |                                   |
|  +-------------+                                   |
|        |                                           |
|        v                                           |
|  +-------------+                                   |
|  |   Executor  |                                   |
|  +-------------+                                   |
+----------------------------------------------------+
```

### Links
