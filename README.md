# Pathogen Detection & Medical AI Assistant

A multi-modal AI-powered diagnostic application for automated pathogen identification from microscopic cell images, chest X-rays, and DNA genomic sequences, coupled with an AI Medical Chatbot featuring Retrieval-Augmented Generation (RAG) and web search capabilities.

---

## Key Features

- **Microscopy Cell Image Analysis:** Detects malaria parasites (*Plasmodium vivax*) from blood smear images.
- **Chest X-Ray Diagnostic Engine:** Classifies chest X-rays for Tuberculosis (*Mycobacterium tuberculosis*) signs.
- **Genomic DNA Sequence Classifier:** Performs sliding-window k-mer analysis on FASTA/FASTQ sequence files to identify pathogens (e.g., *E. coli*, *HPV*, *Parvovirus*, *Polyomavirus*, *Smacovirus*).
- **RAG Medical Assistant:** AI chat assistant powered by Google Gemini, local medical knowledge base (`knowledge_base.txt`), and live web search capabilities (`rag_tools.py`).
- **Interactive Web Interface:** Modern, responsive frontend dashboard (`frontend/`) for uploading samples, visualizing diagnostic probabilities, and generating downloadable lab reports.

---

## Project Structure

```text
Pathogen_detection/
│
├── main.py                     # Primary FastAPI backend application
├── rag_tools.py                # Web search scraper and RAG helper tools
├── disease_info.json           # Disease metadata, labels, and model mappings
├── knowledge_base.txt          # Local RAG context documentation
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variables template
├── .gitignore                  # Git ignore rules (ignores .env, *.h5, *.pkl)
│
├── frontend/                   # Main Web Dashboard UI
│   ├── index.html              # Frontend application page
│   ├── styles.css              # Custom styling
│   └── app.js                  # Frontend logic & API fetch requests
│
├── gemini-chatbot/             # Standalone React + Vite Gemini Chatbot
│   ├── App.tsx                 # React application component
│   ├── components/             # UI components
│   └── package.json            # Node.js dependencies
│
└── Test images and sequence/   # Test samples (Microscopy PNGs, X-Rays, FASTA files)
```

---

## Prerequisites

- **Python 3.10+**
- **Node.js 18+** (optional, for running the standalone Vite `gemini-chatbot` app)
- **Google Gemini API Key** (optional, for live Gemini chat functionality; falls back to local assistant if not provided)

---

## Installation & Setup

### 1. Environment Setup

Clone the repository and create a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install backend dependencies:

```powershell
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the project root (copied from `.env.example`):

```ini
GEMINI_API_KEY=your_gemini_api_key_here
```

### 3. Model Files Placement

Model binaries (`*.h5`) and pickled encoders (`*.pkl`) are excluded from Git due to file size limits. Place your trained model files in the project root:

- `malaria_detection_model.h5`
- `tb_detection_model.h5`
- `dna_kmer_classifier_model.h5`
- `tokenizer.pkl`
- `label_encoder.pkl`

*(Note: If a model file is missing at runtime, the API gracefully handles the request and surfaces a clear status message).*

---

## Running the Application

### Start Backend & Web UI

Start the FastAPI application with Uvicorn:

```powershell
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Open your browser and navigate to:
- **Web Dashboard:** `http://127.0.0.1:8000/`
- **Interactive API Documentation:** `http://127.0.0.1:8000/docs`

---

## API Endpoints Overview

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `GET /` | `GET` | Serves the main static web frontend (`frontend/index.html`) |
| `POST /predict` | `POST` | Accepts an image file (`file`) and optional `model_key` (`malaria` / `chest_xray`) to return diagnostic prediction |
| `POST /analyze_multi` | `POST` | Multi-modal endpoint accepting image file or DNA FASTA file |
| `POST /analyze_dna` | `POST` | Accepts a FASTA/FASTQ sequence file for sliding window k-mer pathogen classification |
| `POST /map` | `POST` | Debug helper to look up disease metadata for a given label |
| `POST /api/chat` | `POST` | Streaming medical chat assistant powered by Gemini RAG & DuckDuckGo search |

---

## Testing

Sample test data is available under `Test images and sequence/`:
- **Malaria Microscopy:** `mra inf 10.png`, `mra u1.png`
- **Chest X-Ray:** `tb 2.jpg`, `tb n1.png`
- **DNA FASTA:** `Ecoli.fasta`, `Jc.fasta`, `human and hpv.fasta`

---

## License

This project is open-source and intended for diagnostic research and demonstration purposes.
