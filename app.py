"""
app.py

Browser-based (Streamlit) GUI for the existing `deletion_detector.py`
program, replacing the Tkinter desktop GUI so the app can run headless
inside GitHub Codespaces and be used through a forwarded port.

This file is a thin presentation layer only. It imports and calls the
existing, unmodified comparison function:

    from deletion_detector import find_removed_text

and never reimplements, rewrites, or alters the detection algorithm.

Run with:

    streamlit run app.py
"""

from __future__ import annotations

import html
import json
import re

import streamlit as st
import streamlit.components.v1 as components

from deletion_detector import find_removed_text

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

APP_OWNER_TITLE = "Άρτεμις Λεπτοκαροπούλου - Βοηθός Σκηνοθέτη"
APP_MAIN_TITLE = "Επεξεργασία Κειμένου - Δράκουλας"

DEFAULT_SIM_THRESHOLD = "0.6"
DEFAULT_MOVE_MIN_TOKENS = "2"

# Same marker convention documented in deletion_detector.py: "[text]X".
# This regex is used ONLY by the GUI layer to re-scan the algorithm's
# already-computed output for presentation purposes (highlighting); it
# never influences what the algorithm itself detects.
_DELETION_MARKER_RE = re.compile(r"\[(.*?)\]X", re.DOTALL)


# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

st.set_page_config(page_title=APP_OWNER_TITLE, layout="wide")

st.markdown(
    """
    <style>
    .deletion {
        color: #c0392b;
        text-decoration: underline;
        background-color: #fdecea;
        padding: 0 1px;
        border-radius: 2px;
    }
    .output-box {
        white-space: pre-wrap;
        word-wrap: break-word;
        font-family: Georgia, "Times New Roman", serif;
        font-size: 1.02rem;
        line-height: 1.6;
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 18px;
        max-height: 520px;
        overflow-y: auto;
        background-color: #ffffff;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

def _init_state() -> None:
    defaults = {
        "original_text_input": "",
        "edited_text_input": "",
        "sim_threshold_input": DEFAULT_SIM_THRESHOLD,
        "move_min_tokens_input": DEFAULT_MOVE_MIN_TOKENS,
        "output": None,
        "status_message": "Ready.",
        "status_kind": "info",  # "info" | "success" | "error" | "warning"
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


_init_state()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_settings(sim_raw: str, move_raw: str) -> tuple[float, int]:
    """Validate and parse the two algorithm settings.

    Raises ValueError with a user-facing message on invalid input. This
    validation lives in the GUI layer only -- it does not touch how
    `find_removed_text` itself behaves.
    """
    try:
        sim_threshold = float(sim_raw)
    except (TypeError, ValueError):
        raise ValueError("Similarity threshold must be a number (e.g. 0.6).")
    if not (0.0 <= sim_threshold <= 1.0):
        raise ValueError("Similarity threshold must be between 0 and 1.")

    try:
        move_min_tokens = int(move_raw)
    except (TypeError, ValueError):
        raise ValueError("Minimum moved tokens must be a whole number (e.g. 2).")
    if move_min_tokens < 1:
        raise ValueError("Minimum moved tokens must be at least 1.")

    return sim_threshold, move_min_tokens


def _render_highlighted_html(text: str) -> str:
    """Build a safe HTML rendering of `text`, wrapping every `[..]X`
    deletion span in a styled <span> for visual highlighting.

    All text is HTML-escaped before being placed in the markup (including
    the content inside the deletion markers), so pasted literary text can
    never inject HTML/JS into the page. This is presentation-only: the
    underlying text -- including the `[ ]X` markers themselves -- is left
    completely untouched, exactly as returned by `find_removed_text`.
    """
    parts: list[str] = []
    last = 0
    for match in _DELETION_MARKER_RE.finditer(text):
        parts.append(html.escape(text[last:match.start()]))
        parts.append(f'<span class="deletion">{html.escape(match.group(0))}</span>')
        last = match.end()
    parts.append(html.escape(text[last:]))
    return "".join(parts)


def _copy_to_clipboard_button(text: str) -> None:
    """Renders a browser 'Copy to clipboard' button.

    Streamlit's Python code runs on the server, so clipboard access has to
    happen in the browser. This embeds a small, self-contained HTML/JS
    snippet that calls the standard Clipboard API (`navigator.clipboard`)
    -- the browser-native equivalent of the old
    `root.clipboard_append(...)` call in the Tkinter GUI. The text is
    passed through `json.dumps` so it is safely escaped for embedding
    inside a `<script>` tag.
    """
    safe_text = json.dumps(text)
    components.html(
        f"""
        <button id="copy-btn" style="
            width:100%; padding:0.6em 1em; font-size:1rem;
            border-radius:6px; border:1px solid #ccc; cursor:pointer;
            background-color:#f0f2f6;">
            COPY OUTPUT
        </button>
        <script>
        const btn = document.getElementById("copy-btn");
        btn.addEventListener("click", async () => {{
            try {{
                await navigator.clipboard.writeText({safe_text});
                btn.innerText = "Copied!";
                setTimeout(() => {{ btn.innerText = "COPY OUTPUT"; }}, 1500);
            }} catch (err) {{
                btn.innerText = "Copy failed - select & copy manually";
                setTimeout(() => {{ btn.innerText = "COPY OUTPUT"; }}, 2000);
            }}
        }});
        </script>
        """,
        height=50,
    )


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown(
    f"<h4 style='text-align:center;color:#666;margin-bottom:0;'>{html.escape(APP_OWNER_TITLE)}</h4>",
    unsafe_allow_html=True,
)
st.markdown(
    f"<h1 style='text-align:center;margin-top:4px;'>{html.escape(APP_MAIN_TITLE)}</h1>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

with st.expander("Settings", expanded=True):
    set_col1, set_col2 = st.columns(2)
    with set_col1:
        st.text_input("Similarity threshold", key="sim_threshold_input")
    with set_col2:
        st.text_input("Minimum moved tokens", key="move_min_tokens_input")

# ---------------------------------------------------------------------------
# Original / Edited text areas
# ---------------------------------------------------------------------------

text_col1, text_col2 = st.columns(2)
with text_col1:
    st.subheader("Πρωτότυπο Κείμενο")
    st.text_area(
        "Original text", key="original_text_input", height=380,
        label_visibility="collapsed",
    )
with text_col2:
    st.subheader("Επεξεργασμένο Κείμενο")
    st.text_area(
        "Edited text", key="edited_text_input", height=380,
        label_visibility="collapsed",
    )

# ---------------------------------------------------------------------------
# COMPARE / CLEAR
# ---------------------------------------------------------------------------

btn_col1, btn_col2 = st.columns(2)
compare_clicked = btn_col1.button("COMPARE", use_container_width=True, type="primary")
clear_clicked = btn_col2.button("CLEAR", use_container_width=True)

if clear_clicked:
    # Widgets bound to session_state via `key=` can only be reassigned
    # *before* they are instantiated again, so we set the values here and
    # immediately rerun the script from the top.
    st.session_state["original_text_input"] = ""
    st.session_state["edited_text_input"] = ""
    st.session_state["sim_threshold_input"] = DEFAULT_SIM_THRESHOLD
    st.session_state["move_min_tokens_input"] = DEFAULT_MOVE_MIN_TOKENS
    st.session_state["output"] = None
    st.session_state["status_message"] = "Ready."
    st.session_state["status_kind"] = "info"
    st.rerun()

if compare_clicked:
    original = st.session_state["original_text_input"]
    edited = st.session_state["edited_text_input"]

    if not original.strip() or not edited.strip():
        st.session_state["output"] = None
        st.session_state["status_message"] = "Please provide both ORIGINAL and EDITED text."
        st.session_state["status_kind"] = "warning"
    else:
        try:
            sim_threshold, move_min_tokens = _parse_settings(
                st.session_state["sim_threshold_input"],
                st.session_state["move_min_tokens_input"],
            )
        except ValueError as exc:
            st.session_state["output"] = None
            st.session_state["status_message"] = str(exc)
            st.session_state["status_kind"] = "warning"
        else:
            # Streamlit's script model is single-threaded and synchronous:
            # the browser tab already shows a running spinner/progress
            # indicator while the server executes this block, so no
            # explicit background thread (as used in the Tkinter version)
            # is necessary here.
            try:
                with st.spinner("Comparing... please wait."):
                    result = find_removed_text(
                        original, edited, sim_threshold, move_min_tokens
                    )
            except Exception as exc:  # noqa: BLE001 - surfaced to the user below
                st.session_state["output"] = None
                st.session_state["status_message"] = f"Comparison failed: {exc}"
                st.session_state["status_kind"] = "error"
            else:
                st.session_state["output"] = result
                st.session_state["status_message"] = "Comparison complete."
                st.session_state["status_kind"] = "success"

# ---------------------------------------------------------------------------
# Status message
# ---------------------------------------------------------------------------

_status_kind = st.session_state["status_kind"]
_status_message = st.session_state["status_message"]
if _status_kind == "success":
    st.success(_status_message)
elif _status_kind == "error":
    st.error(_status_message)
elif _status_kind == "warning":
    st.warning(_status_message)
else:
    st.info(_status_message)

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

st.subheader("Αποτέλεσμα")

_output = st.session_state["output"]
if _output:
    st.markdown(
        f'<div class="output-box">{_render_highlighted_html(_output)}</div>',
        unsafe_allow_html=True,
    )

    action_col1, action_col2 = st.columns(2)
    with action_col1:
        _copy_to_clipboard_button(_output)
    with action_col2:
        st.download_button(
            "SAVE OUTPUT",
            data=_output.encode("utf-8"),
            file_name="output.txt",
            mime="text/plain",
            use_container_width=True,
        )
else:
    st.caption("No output yet. Paste both texts above and click COMPARE.")
