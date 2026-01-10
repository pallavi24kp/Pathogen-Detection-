<div align="center">
<img width="1200" height="475" alt="GHBanner" src="https://github.com/user-attachments/assets/0aa67016-6eaf-458a-adb2-6e31a0763ed6" />
</div>

# Run and deploy your AI Studio app

This contains everything you need to run your app locally.

View your app in AI Studio: https://ai.studio/apps/drive/12ztpzhnGONwW9W2VSRnPW4FDavpjZcmV

## Run Locally

**Prerequisites:**  Node.js


1. Install dependencies:
   `npm install`
2. Set the `GEMINI_API_KEY` in [.env.local](.env.local) to your Gemini API key
3. Run the app:
   `npm run dev`

### Run the Python backend (optional, recommended for local testing)

This repo includes a simple FastAPI backend (`main.py`) that the React frontend expects at `/api/chat`.

1. Install Python dependencies (use a venv):

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Create a `.env` or set the `GEMINI_API_KEY` env var before running the server (or leave empty to use a mock responder):

```powershell
setx GEMINI_API_KEY "your-key-here"
# then restart your shell or set for current session:
$env:GEMINI_API_KEY = 'your-key-here'
```

3. Run the backend:

```powershell
uvicorn main:app --reload --port 8000
```

4. In development, start the frontend (separate terminal):

```powershell
npm install
npm run dev
```

The frontend is configured to POST to `/api/chat`. When running the backend on port 8000, you can either configure a proxy in Vite or run the frontend so that requests to `/api/chat` are proxied to `http://localhost:8000/api/chat`. Alternatively, change the fetch URL in `components/Chatbot.tsx` to `http://localhost:8000/api/chat` for local development.
