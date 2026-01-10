# Malaria Detection - Fullstack Example

This repository contains a small full-stack example that serves a simple web UI and a FastAPI backend which loads a Keras `.h5` model (`malaria_detection_model.h5`) and returns predictions for uploaded cell images.

What was added
- `main.py` - FastAPI backend that loads `malaria_detection_model.h5` and exposes `/predict` to accept image uploads. It also serves the static frontend from the `frontend/` directory.
- `requirements.txt` - Python dependencies.
- `frontend/index.html`, `frontend/styles.css`, `frontend/app.js` - Simple web UI for uploading images and showing predictions.
- `.gitignore` - common ignores.

Quickstart (Windows PowerShell)

1. Make sure `malaria_detection_model.h5` is in the repository root (same folder as `main.py`).
2. Create and activate a virtual environment (recommended):

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
```

3. Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

4. Start the app:

```powershell
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

5. Open the frontend in your browser:

- Navigate to `http://127.0.0.1:8000/` — the static UI will load from the `frontend/` folder.

Notes and caveats
- The backend tries to infer the expected input size from the model's `input_shape`; if it can't, it defaults to 224x224.
- The frontend expects the prediction response JSON to contain `label`, `label_id`, and `probabilities`.
- TensorFlow installs can be large. If you only need CPU support, pick an appropriate TensorFlow package for your platform (the `requirements.txt` references `tensorflow` as a convenience).

Next steps (suggested)
- Add validation and stricter CORS rules for production.
- Add tests for the prediction endpoint using a small sample image and `pytest` + `httpx`.
- Containerize with Docker if you want reproducible deployment.
