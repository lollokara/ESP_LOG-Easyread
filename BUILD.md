# Building the Mac App

To turn this script into a standalone Mac Application (`.app`), follow these steps on your Mac M1.

## Prerequisites

1.  Ensure you have Python installed (Python 3.10 or 3.11 is recommended for M1).
2.  Install the project dependencies including the build tools:

    ```bash
    pip install -r requirements.txt
    pip install pyinstaller
    ```

## Build

Run the build script:

```bash
python build_app.py
```

This process may take a minute or two.

## Output

Once finished, you will find your application in the `dist` folder:

`dist/ESP32_Monitor.app`

You can drag this to your Applications folder or run it directly.

## Troubleshooting

*   **"App is damaged"**: If macOS says the app is damaged, it is because it is not signed by Apple. You can bypass this by running:
    ```bash
    xattr -cr dist/ESP32_Monitor.app
    ```
*   **Native Window issues**: Ensure `pywebview` installed correctly.
