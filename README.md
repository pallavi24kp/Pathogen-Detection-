# Multimodal Pathogen Detection & Analysis System (LabAssist)

LabAssist is a comprehensive, production-ready fullstack AI application for rapid pathogen screening and diagnostic assistance. It supports three distinct detection modalities leveraging deep learning and sequence classification:

1. **Malaria Detection**: Classifies cell images from thin blood smears as *Parasitized* (Malaria) or *Uninfected*.
2. **Tuberculosis (TB) Detection**: Identifies *Tuberculosis* vs. *Normal* chest X-rays.
3. **DNA Sequence Classification**: Analyzes genomic sequence FASTA/raw data via sliding-window k-mer analysis to detect viral and bacterial pathogens:
   - *Escherichia coli* (E. coli)
   - *Human Papillomavirus* (HPV)
   - *Human Smacovirus* (Smacovirus)
   - *Human Parvovirus* (Parvovirus B19)
   - *JC Polyomavirus* (JC virus)
   - *Human Background DNA* (Healthy)

The system features a clean, responsive HTML/CSS/JS web frontend that communicates with a high-performance FastAPI/Uvicorn backend. It also includes an integrated AI Chat Assistant powered by a Gemini-like RAG chatbot for treatment guidance and diagnostics question-answering.

---

## Architecture & Core Components

- **Backend (`main.py`)**: A FastAPI web server that handles requests, executes TensorFlow/Keras model inferences, performs sliding-window DNA genomic analysis, and hosts the chatbot APIs.
- **Frontend (`frontend/`)**: An elegant, dynamic, responsive dashboard designed for clinical utility:
  - `index.html`: Layout containing the analysis controls, results display, and interactive chat interface.
  - `styles.css`: Custom premium styling with vibrant modern palettes, clean layouts, and micro-animations.
  - `app.js`: Connects to backend API endpoints, handles file uploads, renders results dynamically, and maintains local report history.
- **Models & Serialized Configurations**:
  - `malaria_detection_model.h5` (Keras model for malaria)
  - `tb_detection_model.h5` (Keras model for chest X-rays)
  - `dna_kmer_classifier_model.h5` (Keras sequence classifier)
  - `tokenizer.pkl` & `label_encoder.pkl` (Preprocessing and classification mappings for DNA sequencing)
  - `disease_info.json`: Clinical metadata (pathogen names, treatment notes, threshold configurations) mapped to model outputs.
- **Diagnostic & Helper Scripts (`scripts/`)**: A collection of utility scripts for inspecting models, verifying layer structures, and calibrating image-processing heuristics:
  - `probe.py` & `inspect_model.py`: Inspect input/output shapes, model configurations, and layers.
  - `diagnose_image.py`: Test the model-guessing heuristic on local test images.
  - `test_model_load.py` & `test_malaria_load.py`: Verify the models load and run predictions with dummy data.

### Repository Structure

```text
.
├── .gitignore                      # Git configuration & file exclusion patterns
├── README.md                       # System documentation & quickstart guide
├── disease_info.json               # Pathogen metadata & classification thresholds
├── label_encoder.pkl               # DNA sequence label encoder
├── main.py                         # FastAPI backend server
├── malaria_detection_model.h5      # Deep learning model for Malaria detection
├── rag_tools.py                    # RAG chatbot web-search utility
├── requirements.txt                # Python dependencies list
├── tb_detection_model.h5           # Deep learning model for Tuberculosis detection
├── tokenizer.pkl                   # DNA sequence tokenization mapping
│
├── frontend/                       # Web interface assets
│   ├── app.js                      # Application controller & API integration
│   ├── index.html                  # Clinical dashboard template
│   ├── styles.css                  # Modern responsive dashboard styles
│   └── images/                     # Static styling image files
│
├── scripts/                        # Model diagnostics and helper utilities
│   ├── diagnose_image.py           # Model-guessing heuristic tester
│   ├── inspect_h5.py               # inspect H5 structure and metadata
│   ├── inspect_model.py            # inspect model weights, layers, shapes
│   ├── probe.py                    # Probe model properties
│   ├── test_malaria_load.py        # Malaria model prediction testing
│   └── test_model_load.py          # Tuberculosis model architecture testing
│
└── Test images and sequence/       # Clinical test samples (microscopy/FASTAs)
```

---

## Technical Solutions & Robustness Improvements

To run successfully in local developer environments, the following robustness fixes and features are integrated:

1. **API Quota Graceful Fallback**: If the configured Gemini API key in `.env` is rate-limited (`429 ResourceExhausted`) or fails to connect, the chat assistant automatically degrades gracefully to an offline clinician assistant, supplying mock diagnostic information without crashing the interface.
2. **Self-Contained Report History with Image Serialization**: Images uploaded for analysis are resized and encoded into Base64 data URLs on the backend. This allows them to be saved directly in the frontend's local report history (`localStorage`), ensuring that clicking on a historical report reconstructs the full analysis with its original image, even across browser restarts.
3. **Mutual-Exclusive Upload Validation**: The frontend prevents submitting overlapping modalities by clearing the image input when a DNA sequence is selected, and vice versa.
4. **Improved Global Pathogen Mapping**: The tolerant mapping algorithm searches through the nested `class_info` of all configured models in `disease_info.json` rather than performing a flat lookup, resolving mapping bugs for diagnostic classifications.

---

## Quickstart Guide (Windows PowerShell)

### 1. Set Up a Virtual Environment
Create and activate a virtual environment to manage dependencies:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install Dependencies
Install all required libraries including FastAPI, Uvicorn, TensorFlow, Pillow, and Scikit-Learn:
```powershell
python -m pip install -r requirements.txt
```

### 3. Start the Application Server
Run the FastAPI application locally:
```powershell
python -m uvicorn main:app --port 8000 --host 127.0.0.1
```

### 4. Access the Web Interface
Open your web browser and navigate to:
```
http://127.0.0.1:8000/
```
The static files from the `frontend/` directory are served automatically.
- **Root URL `/`**: Serves the main dashboard (`index.html`).
- **Static files `/static/*`**: Serves stylesheets and JS logic mounted from the `frontend` directory.
