## Running it in GitHub Codespaces

The project is configured to set itself up automatically in GitHub Codespaces.

### 1. Open the repository

Open the repository on GitHub and select:

**Code → Codespaces → Create codespace on main**

### 2. Wait for setup

Codespaces automatically:

- creates the Python environment
- installs the dependencies from `requirements.txt`
- starts the Streamlit application
- forwards port `8501`

No manual Python installation, virtual environment creation, or `pip install` commands are required.

### 3. Open the application

When the setup is complete, Codespaces will automatically forward port `8501`.

Open the **Literary Deletion Detector** port in your browser.

If it does not open automatically:

1. Open the **Ports** tab.
2. Find port `8501`.
3. Click the globe/open-in-browser button.

### 4. Use the application

The application opens in your browser.

1. Paste the ORIGINAL text.
2. Paste the EDITED text.
3. Adjust the settings if necessary.
4. Click **COMPARE**.
5. Review the detected deletions.
6. Copy or save the result.

### Troubleshooting

If the application does not start automatically, open a terminal and run:

```bash
streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
