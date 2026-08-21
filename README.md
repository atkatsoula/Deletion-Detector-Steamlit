# Literary Deletion Detector — Web (Streamlit) version

Detects passages genuinely **removed** from an ORIGINAL literary text compared
to an EDITED version, and marks them as `[deleted text]X`.

The detection algorithm lives entirely in `deletion_detector.py` and is
**unchanged**. `app.py` is only a presentation layer (a browser-based GUI
built with [Streamlit](https://streamlit.io)) that collects input from the
user and calls the existing:

```python
from deletion_detector import find_removed_text
find_removed_text(original, edited, sim_threshold, move_min_tokens)
```

## Project structure

```text
project/
│
├── deletion_detector.py   # existing, unmodified comparison algorithm
├── app.py                 # Streamlit web GUI (calls find_removed_text only)
├── requirements.txt
└── README.md
```

## Why the old Tkinter `gui.py` can't run directly in a Codespace

`gui.py` opens a native desktop window using Tkinter, which needs an X11
display server (or an equivalent windowing system) to draw to. A GitHub
Codespace is a headless Linux container with no display, no X server, and no
desktop environment — there's nothing for Tkinter to draw a window onto, so
it fails to start (or requires extra infrastructure like a VNC server just to
view a virtual desktop, which is unnecessary overhead here).

`app.py` avoids this entirely: it's a normal Python web server (Streamlit)
that renders the interface as HTML in **your own browser**, using GitHub
Codespaces' built-in port forwarding. No display, X11, VNC, or desktop
environment is required inside the container.

## Running it in GitHub Codespaces

1. **Open a terminal** in your Codespace (Terminal → New Terminal).

2. **(Optional) Create and activate a virtual environment:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Start the app:**

   ```bash
   streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
   ```

   - `--server.address 0.0.0.0` lets the container accept connections from
     the forwarded port (not just `localhost` inside the container).
   - `--server.headless true` stops Streamlit from trying to open a local
     browser window (there isn't one inside the container) and from
     prompting for an email on first run.

5. **Open the forwarded port:**

   - Codespaces will detect port `8501` and show a notification/popup —
     click **"Open in Browser"**.
   - Or go to the **"Ports"** tab (next to the Terminal tab), find port
     `8501`, and click the globe icon to open it.
   - If the port is marked "Private", right-click it and set visibility to
     "Public" or "Private (your account)" so you can open it in your
     browser.

6. Use the app: paste the ORIGINAL and EDITED text, adjust settings if
   needed, and click **COMPARE**.

## Verifying the app compiles / starts correctly

```bash
python -m py_compile app.py
streamlit run app.py --server.headless true
```

The first command checks the file has no syntax errors. The second starts
the server; you should see a `Local URL` / `Network URL` printed in the
terminal with no Tkinter-related output, since this version never imports
`tkinter`.

## Notes

- **Deletion highlighting**: the output is rendered as escaped HTML with the
  `[deleted text]X` spans wrapped in a styled `<span>` (red text, underline,
  light red background) — the same visual convention as the old Tkinter GUI,
  implemented with CSS instead of a Tkinter text tag. The `[ ]X` markers
  themselves always stay visible in both the highlighted view and the copied
  / downloaded text.
- **Copy Output**: uses the browser's Clipboard API (`navigator.clipboard`)
  via a small embedded HTML/JS snippet, since Tkinter's clipboard functions
  aren't available (or meaningful) in a web app.
- **Save Output**: uses Streamlit's `st.download_button`, which triggers a
  normal browser file download (`output.txt`, UTF-8) instead of a desktop
  "Save As" dialog.
- **Large texts**: the comparison runs once per click of COMPARE (no
  duplicate processing), and Streamlit's synchronous script model means the
  browser tab already shows a spinner while the server computes — no manual
  background threading (as used in the Tkinter version) is needed.
