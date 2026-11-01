# Researchly frontend starter

This is the first standalone HTML/CSS/JavaScript frontend for the Multi-Agent Research System.

## Files
- `index.html` — homepage, research workspace and sign-in modal markup
- `style.css` — responsive dark SaaS design
- `script.js` — navigation, demo chat flow, modal and preview download behaviour

## Run locally
The simplest option is to open `index.html` in your browser.

Recommended: from this folder, run a small static server:
```bash
python -m http.server 5500
```
Then open http://localhost:5500

## Important: current limitations
This is a **frontend prototype**. The research response is sample preview content. Google sign-in buttons are visual placeholders, and no account or chat history is stored yet.

The next implementation stage is to add a small FastAPI service that imports your existing LangGraph workflow and exposes a research endpoint. Then the JavaScript can send the topic to Python and render the real result. Authentication and persistent chat history will be added after that.

## Integration notes
- Keep the existing `agents.py` and `graph.py` unchanged for now.
- Do not delete the current Streamlit `app.py` yet. Keep it as a working fallback until the HTML frontend is connected and tested.
- This frontend intentionally does not include a PDF library or PDF upload feature.


## Research modes and PDF attachments

The workspace composer now includes three mode selectors:
- **Web Search** — intended for web-only research.
- **Ask My PDFs** — intended for questions grounded in uploaded PDFs (requires at least one PDF).
- **Web + PDFs** — intended to combine web research with uploaded PDF context (requires at least one PDF).

Use the **+** button to select one or more PDF files. Attached files appear as removable chips above the composer.

This is still a frontend prototype: the browser lets users select PDFs and choose a mode, but it does not yet upload files or invoke the Python RAG/web pipeline. In the FastAPI integration, send the selected mode and prompt with the files using `FormData` (multipart upload), then route the request to your existing web-search and/or RAG workflow.
