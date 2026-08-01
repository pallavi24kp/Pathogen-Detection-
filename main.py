from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import numpy as np
from PIL import Image, ImageStat
import io
import os
import traceback
import json
from typing import Optional, List, Dict, Any, AsyncIterator
from pydantic import BaseModel
import google.generativeai as genai
from google.generativeai import protos
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from dotenv import load_dotenv
import asyncio
from rag_tools import search_web

app = FastAPI(title="Malaria Detection API")

# Enable CORS for all origins (for development)
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load environment variables from .env file
# Explicitly load the .env file from the project root.
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=dotenv_path)

# Configure Gemini API
try:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("WARNING: GEMINI_API_KEY not found. Chatbot will use mock responses.")
    else:
        genai.configure(api_key=api_key)
        print("Gemini API key configured successfully.")
except Exception as e:
    print(f"Error configuring Gemini API: {e}")


# Load knowledge base
KNOWLEDGE_BASE_PATH = os.path.join(os.path.dirname(__file__), "knowledge_base.txt")
knowledge_base = ""
try:
    if os.path.exists(KNOWLEDGE_BASE_PATH):
        with open(KNOWLEDGE_BASE_PATH, 'r', encoding='utf-8') as f:
            knowledge_base = f.read()
        print("Knowledge base loaded successfully.")
    else:
        print("WARNING: knowledge_base.txt not found.")
except Exception as e:
    print(f"Error loading knowledge base: {e}")

# Allow requests from any origin (use more strict CORS in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the frontend static files from the `frontend` directory
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
if not os.path.isdir(frontend_dir):
    # Directory may be missing during initial editing; create if absent when running.
    try:
        os.makedirs(frontend_dir, exist_ok=True)
    except Exception:
        pass

# Serve static assets under /static and serve index.html at root.
# Mounting StaticFiles at "/" can intercept other routes (such as POST /predict)
# so we mount at /static and return the index explicitly.
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

# --- Debug Flags ---
# Set to True to get detailed console output for specific features
HEURISTIC_DEBUG = True  # For model selection heuristic
REQUEST_DEBUG = True    # For incoming request details
MODEL_DEBUG = True      # For Keras model loading/prediction steps
# -------------------


@app.get("/")
async def read_index():
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return JSONResponse({"detail": "Frontend not found. Place files in frontend/"}, status_code=404)

MODEL_PATH = os.path.join(os.path.dirname(__file__), "malaria_detection_model.h5")
model = None
# Cache for multiple models when using multi-model predict
models_cache: Dict[str, Any] = {}

# Load disease -> info mapping from JSON if present
DISEASE_INFO_PATH = os.path.join(os.path.dirname(__file__), "disease_info.json")
disease_info = {}
try:
    if os.path.exists(DISEASE_INFO_PATH):
        with open(DISEASE_INFO_PATH, 'r', encoding='utf-8') as f:
            disease_info = json.load(f)
except Exception:
    disease_info = {}

# Precompute a casefold->key map to speed and stabilize lookups (case-insensitive)
disease_info_key_map = {k.casefold(): k for k in disease_info.keys()} if disease_info else {}


def map_label_to_disease(label_name: Optional[str], label_id: Optional[int], labels: Optional[List[str]] = None):
    """Map a predicted label (name or id) to the `disease_info` mapping.
    Returns a dict with keys:
      - info: {disease, pathogen}
      - matched_key: the key in `disease_info` that matched (or None)
    The lookup is tolerant: checks class_info mappings, exact match, case-insensitive match.
    """
    info = {"disease": "Unknown", "pathogen": "Unknown"}
    matched = None
    try:
        if label_name is not None:
            norm = label_name.strip()
            # 1. Search class_info sub-dictionaries inside all disease_info models
            for model_key, model_cfg in disease_info.items():
                if isinstance(model_cfg, dict) and "class_info" in model_cfg:
                    cinfo = model_cfg["class_info"]
                    if norm in cinfo:
                        info = cinfo[norm]
                        matched = norm
                        break
                    for k, v in cinfo.items():
                        if k.lower() == norm.lower():
                            info = v
                            matched = k
                            break
                    if matched:
                        break

            # 2. Search top-level disease_info keys if not matched yet
            if matched is None:
                if norm in disease_info:
                    info = disease_info[norm]
                    matched = norm
                else:
                    folded = norm.casefold()
                    if folded in disease_info_key_map:
                        matched = disease_info_key_map[folded]
                        info = disease_info[matched]
                    else:
                        lower_lookup = norm.lower()
                        for k in disease_info.keys():
                            if k.lower() == lower_lookup:
                                matched = k
                                info = disease_info[k]
                                break

        # 3. Fallback to labels[label_id] if available
        if matched is None and label_id is not None and labels:
            try:
                fallback_label = labels[label_id]
                for model_key, model_cfg in disease_info.items():
                    if isinstance(model_cfg, dict) and "class_info" in model_cfg:
                        cinfo = model_cfg["class_info"]
                        if fallback_label in cinfo:
                            info = cinfo[fallback_label]
                            matched = fallback_label
                            break
            except Exception:
                pass
    except Exception:
        info = {"disease": "Unknown", "pathogen": "Unknown"}
        matched = None

    return {"info": info, "matched_key": matched}


class MapRequest(BaseModel):
    label_id: Optional[int] = None
    label_name: Optional[str] = None
    # optional raw model output for context
    raw_pred: Optional[List[float]] = None


@app.post('/map')
async def map_endpoint(req: MapRequest):
    """Debug endpoint: provide a label_name or label_id (or both) and get back the mapped disease info.
    Useful for testing mapping without running an actual prediction.
    """
    # Use the same default labels as /predict to keep behavior consistent
    labels = ["Parasitized", "Uninfected"]
    res = map_label_to_disease(req.label_name, req.label_id, labels)
    return JSONResponse(content={"disease_info": res.get('info'), "matched_key": res.get('matched_key'), "requested": req.dict()})


class ChatRequest(BaseModel):
	prompt: str
	history: List[Dict[str, Any]] = []


async def mock_stream_response(prompt: str) -> AsyncIterator[bytes]:
	"""A simple streaming generator that yields chunks of text with a short delay."""
	response_text = f"You said: {prompt}\nThis is a mock reply because the Gemini API key is not configured."
	chunk_size = 12
	for i in range(0, len(response_text), chunk_size):
		chunk = response_text[i : i + chunk_size]
		await asyncio.sleep(0.06)
		yield chunk.encode("utf-8")


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    """Handles chat requests using Gemini's function calling feature."""
    prompt = req.prompt
    api_key = os.getenv("GEMINI_API_KEY")

    if not prompt or not prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt is required")

    if not api_key:
        print("Returning mock response due to missing API key.")
        return StreamingResponse(mock_stream_response(prompt), media_type="text/plain; charset=utf-8")

    try:
        # Single-call RAG strategy:
        # To avoid making multiple Gemini API calls (which can easily hit low free-tier quotas),
        # we prefetch web results locally when the user's prompt clearly asks for up-to-date info
        # (keywords like 'latest', 'in 2025', 'recent', etc.), then make a single call to Gemini
        # that includes those search results in the prompt. This ensures one generate_content
        # request per user query.

        def needs_web_search(text: str) -> bool:
            keywords = ["latest", "recent", "in 2025", "new research", "new treatments", "current", "update", "news", "recent studies"]
            t = text.lower()
            return any(k in t for k in keywords)

        # Build a simple chat history (treat tool responses as plain text to avoid structured parts)
        chat_history = []
        for item in req.history:
            role = item.get("role")
            content = item.get("content")
            if not content:
                continue
            # Represent everything as simple text parts for the single-call strategy
            chat_history.append({"role": role if role in ("user", "model") else "user", "parts": [str(content)]})

        # Decide whether to run a local web search before calling Gemini
        search_results = None
        if needs_web_search(prompt):
            print(f"RAG_TOOL: Prompt indicates a need for fresh web info. Running local search for: '{prompt}'")
            # Perform the web search off the event loop
            search_results = await asyncio.to_thread(search_web, prompt, 3)
            if search_results and search_results.startswith("Error:"):
                # If the scraper returned an error, treat it as no results
                print(f"RAG_TOOL_WARNING: search_web returned error: {search_results}")
                search_results = None

        # Construct the system instruction and user message. If we have web results, include them inline.
        system_instr = (
            "You are a specialized medical assistant. Provide accurate answers and when web results are provided, "
            "use them as the primary source for time-sensitive information. For general questions, answer from your knowledge.\n\n"
            "--- LOCAL KNOWLEDGE BASE ---\n"
            f"{knowledge_base}\n"
            "--- END LOCAL KNOWLEDGE BASE ---"
        )

        model = genai.GenerativeModel(
            model_name='gemini-pro-latest',
            system_instruction=system_instr,
        )

        chat = model.start_chat(history=chat_history)

        async def stream_generator():
            try:
                # Prepare the single prompt to send to Gemini. If we have web results, attach them.
                if search_results:
                    user_message = (
                        f"User question: {prompt}\n\n---WEB_SEARCH_RESULTS---\n{search_results}\n---END_WEB_SEARCH---\n"
                    )
                else:
                    user_message = prompt

                # Make a single call to the model and stream its response back to the client.
                streamed_response = await chat.send_message_async(user_message, stream=True)
                async for chunk in streamed_response:
                    if chunk.text:
                        yield chunk.text.encode('utf-8')
                        await asyncio.sleep(0.02)

            except Exception as e:
                error_message = f"Gemini API unavailable ({e}). Falling back to local assistant response:\n"
                print(error_message)
                yield error_message.encode('utf-8')
                async for chunk in mock_stream_response(prompt):
                    yield chunk

        return StreamingResponse(stream_generator(), media_type="text/plain; charset=utf-8")

    except Exception as e:
        tb = traceback.format_exc()
        print(f"Error in /api/chat: {e}\n{tb}")
        raise HTTPException(status_code=500, detail=f"Failed to process chat request: {e}")


def load_model(path: str):
    """Load the Keras model. Import TensorFlow lazily so we can show clearer errors
    if TensorFlow isn't available in the environment.
    """
    try:
        import tensorflow as tf
    except Exception as e:
        # Re-raise so callers can handle and return a helpful message
        raise

    global model
    model = tf.keras.models.load_model(path)
    return model


def guess_model_from_image(pil_img: Image.Image) -> Optional[str]:
    """Heuristic to guess which model should handle the image, prioritizing color characteristics.

    Returns a model key present in `disease_info` (for example 'malaria' or 'chest_xray'),
    or None if the heuristic is not confident.
    """
    try:
        w, h = pil_img.size
        max_dim = max(w, h)

        # --- Color Analysis (Primary Factor) ---
        # Convert to RGB for consistent stats
        rgb = pil_img.convert('RGB')
        stat = ImageStat.Stat(rgb)
        
        # 1. Saturation: The most reliable indicator for grayscale vs. color.
        hsv = pil_img.convert('HSV')
        hsv_stat = ImageStat.Stat(hsv)
        # HSV channels are H, S, V. We care about S (saturation).
        sat_mean = (hsv_stat.mean[1] if hsv_stat.mean and len(hsv_stat.mean) > 1 else 0)

        # 2. Channel Difference: Another strong indicator of grayscale.
        # In a grayscale image, the R, G, and B values are nearly identical.
        means = stat.mean or [0, 0, 0]
        ch_diff = (abs(means[0] - means[1]) + abs(means[0] - means[2]) + abs(means[1] - means[2])) / 3.0

        # --- Heuristic Logic (Color-First) ---
        if HEURISTIC_DEBUG:
            print(f"HEURISTIC_DEBUG: size={w}x{h} max_dim={max_dim} ch_diff={ch_diff:.2f} sat_mean={sat_mean:.2f}")

        # Rule 1: If the image is essentially grayscale, it's an X-ray.
        # We use a low threshold for saturation and channel difference.
        if sat_mean < 15 and ch_diff < 10:
            return 'chest_xray'

        # Rule 2: If the image has significant color, it's a microscopy image.
        if sat_mean > 20 or ch_diff > 15:
            return 'malaria'

        # If ambiguous, use size as a tie-breaker.
        # Large images are more likely to be X-rays.
        if max_dim > 400:
            return 'chest_xray'
        else:
            return 'malaria'

    except Exception:
        # If any error occurs during analysis, return None to let the fallback handle it.
        return None


def fallback_choose_model(pil_img: Image.Image, configured_models: Dict[str, Any]) -> Optional[str]:
    """Deterministic fallback: when the primary heuristic is ambiguous, pick the most likely model.

    Uses a slightly more permissive threshold so the system always chooses one model instead of running all.
    """
    try:
        w, h = pil_img.size
        max_dim = max(w, h)
        
        rgb = pil_img.convert('RGB')
        stat = ImageStat.Stat(rgb)
        stddev = stat.stddev or [0, 0, 0]
        color_std = sum(stddev) / 3.0
        means = stat.mean or [0, 0, 0]
        ch_diff = (abs(means[0] - means[1]) + abs(means[0] - means[2]) + abs(means[1] - means[2])) / 3.0

        hsv = pil_img.convert('HSV')
        hsv_stat = ImageStat.Stat(hsv)
        sat_mean = (hsv_stat.mean[1] if hsv_stat.mean and len(hsv_stat.mean) > 1 else 0)

        if HEURISTIC_DEBUG:
            print(f"FALLBACK_DEBUG: max_dim={max_dim} color_std={color_std:.2f} ch_diff={ch_diff:.2f} sat_mean={sat_mean:.2f}")

        # Stricter fallback: Prefer chest_xray for large, low-color images.
        # An X-ray will have very low saturation and channel differences.
        if 'chest_xray' in configured_models and (sat_mean < 15 and ch_diff < 10 and max_dim >= 500):
            return 'chest_xray'

        # Fallback for malaria: requires some color and smaller size.
        if 'malaria' in configured_models and (sat_mean >= 20 or color_std >= 15 or max_dim < 500):
            return 'malaria'

        # Last resort: if still ambiguous, prefer the model that handles larger images if size is a factor.
        if 'chest_xray' in configured_models and max_dim >= 500:
            return 'chest_xray'
        if 'malaria' in configured_models:
            return 'malaria'

        return None
    except Exception:
        return None


@app.on_event("startup")
async def startup_event():
    """At startup, check for all configured models and print their status."""
    print("--- Verifying Model Configurations at Startup ---")
    
    # Determine which models are configured in disease_info.json
    configured_models = {k: v for k, v in disease_info.items() if isinstance(v, dict) and v.get('model_path')}
    
    if not configured_models:
        print("WARNING: No models are configured in disease_info.json with a 'model_path' key.")
        print("Place your .h5 files in the project directory and update disease_info.json.")
        return

    print(f"Found {len(configured_models)} model(s) configured in disease_info.json.")
    for key, info in configured_models.items():
        path = info.get('model_path')
        if not path:
            continue
        
        model_file = os.path.join(os.path.dirname(__file__), path)
        if os.path.exists(model_file):
            print(f"  - Model '{key}': OK. File found at '{path}'. Will be loaded on first prediction.")
        else:
            print(f"  - Model '{key}': NOT FOUND. Expected file at '{path}'.")
    
    print("--- Verification Complete ---")
    # We intentionally do not force TensorFlow to import at startup. Importing TF can
    # fail on some developer machines (missing redistributable, incompatible Python
    # version, GPU driver issues). We'll load the model lazily on the first request
    # and return a clear error if import fails.


@app.post("/predict")
async def predict(file: UploadFile = File(...), model_key: Optional[str] = None, preprocess_override: Optional[str] = None):
    """Accept an uploaded image file and return prediction results from one or more configured models.

    If `model_key` is provided (must match a top-level key in `disease_info.json` that has a `model_path`),
    the endpoint will run only that model. If omitted, the endpoint will run all configured models and
    return a combined response.
    """
    if REQUEST_DEBUG:
        print(f"REQUEST_DEBUG: /predict called; model_key='{model_key}'")

    contents = await file.read()
    try:
        src_image = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image file: {e}")

    # Reload disease_info.json on each request to pick up config changes without server restart
    try:
        global disease_info, disease_info_key_map
        if os.path.exists(DISEASE_INFO_PATH):
            with open(DISEASE_INFO_PATH, 'r', encoding='utf-8') as f:
                disease_info = json.load(f)
            disease_info_key_map = {k.casefold(): k for k in disease_info.keys()} if disease_info else {}
            if REQUEST_DEBUG:
                print("REQUEST_DEBUG: disease_info reloaded for /predict")
    except Exception as _e:
        if REQUEST_DEBUG:
            print(f"REQUEST_DEBUG: Failed to reload disease_info.json: {_e}")

    # Determine which models are configured in disease_info.json
    configured_models = {k: v for k, v in disease_info.items() if isinstance(v, dict) and v.get('model_path')}
    if not configured_models:
        raise HTTPException(status_code=500, detail="No models configured in disease_info.json with 'model_path'.")

    # If a specific model is requested, filter the list to just that one
    if model_key:
        if model_key not in configured_models:
            raise HTTPException(status_code=400, detail=f"Unknown model_key '{model_key}'. Valid keys: {list(configured_models.keys())}")
        models_to_run = {model_key: configured_models[model_key]}
        if MODEL_DEBUG:
            print(f"MODEL_DEBUG: Running single model as requested: '{model_key}'")
    else:
        models_to_run = configured_models
        if MODEL_DEBUG:
            print(f"MODEL_DEBUG: No model_key provided, running all configured models: {list(models_to_run.keys())}")

    # Use the consolidated helper function to perform predictions
    results = await _perform_predictions_for_image(src_image, models_to_run, preprocess_override)

    if MODEL_DEBUG:
        # Log which models returned results or errors
        successful_models = [k for k, v in results.items() if 'error' not in v]
        failed_models = [k for k, v in results.items() if 'error' in v]
        print(f"MODEL_DEBUG: Prediction complete. Success: {successful_models}, Failures: {failed_models}")

    return JSONResponse(content={"results": results})


def load_keras_model(path: str):
    """Helper to load a keras model (per-path) and cache it with safe fallbacks."""
    if path in models_cache:
        return models_cache[path]
    try:
        import tensorflow as tf
        
        if MODEL_DEBUG:
            print(f"MODEL_DEBUG: Loading model: {os.path.basename(path)}")
        
        try:
            m = tf.keras.models.load_model(path, compile=False)
            
            # Ensure the model is built by calling build() if it hasn't been built yet
            if not m.built:
                if hasattr(m, 'input_shape') and m.input_shape:
                    m.build(m.input_shape)
                if MODEL_DEBUG:
                    print(f"MODEL_DEBUG: Model built with input shape: {m.input_shape}")
            
            if MODEL_DEBUG:
                print(f"MODEL_DEBUG: Model loaded successfully with standard load")
                print(f"MODEL_DEBUG: Model input shape: {m.input_shape}")
                print(f"MODEL_DEBUG: Model output shape: {m.output_shape}")
        
        except Exception as load_err:
            if MODEL_DEBUG:
                print(f"MODEL_DEBUG: Standard load failed: {load_err}")
                print(f"MODEL_DEBUG: Attempting weights-only load / JSON patch fallback...")
            
            try:
                import h5py
                loaded_via_json = False
                try:
                    with h5py.File(path, 'r') as f:
                        config_raw = f.attrs.get('model_config')
                        if isinstance(config_raw, bytes):
                            config_raw = config_raw.decode('utf-8')
                    if config_raw:
                        config_dict = json.loads(config_raw)
                        def fix_config(obj):
                            if isinstance(obj, dict):
                                if obj.get('class_name') == 'DTypePolicy' and isinstance(obj.get('config'), dict):
                                    return obj['config'].get('name', 'float32')
                                if 'batch_shape' in obj:
                                    obj['batch_input_shape'] = obj.pop('batch_shape')
                                return {k: fix_config(v) for k, v in obj.items()}
                            elif isinstance(obj, list):
                                return [fix_config(x) for x in obj]
                            return obj
                        fixed = fix_config(config_dict)
                        m = tf.keras.models.model_from_json(json.dumps(fixed))
                        m.load_weights(path)
                        loaded_via_json = True
                        if MODEL_DEBUG:
                            print("MODEL_DEBUG: Loaded model successfully via patched JSON + load_weights")
                except Exception as json_err:
                    if MODEL_DEBUG:
                        print(f"MODEL_DEBUG: Patched JSON load failed: {json_err}")

                if not loaded_via_json:
                    if 'efficientnet' in path.lower():
                        base_model = tf.keras.applications.EfficientNetB0(
                            include_top=False,
                            weights=None,
                            input_shape=(224, 224, 3)
                        )
                        x = base_model.output
                        x = tf.keras.layers.GlobalAveragePooling2D()(x)
                        x = tf.keras.layers.Dense(2, activation='softmax')(x)
                        m = tf.keras.Model(inputs=base_model.input, outputs=x)
                        m.load_weights(path)
                        if MODEL_DEBUG:
                            print("MODEL_DEBUG: Loaded weights into fresh EfficientNet architecture")
                    elif 'malaria' in path.lower() or 'resnet' in path.lower():
                        base_model = tf.keras.applications.ResNet50(
                            include_top=False,
                            weights=None,
                            input_shape=(128, 128, 3)
                        )
                        x = tf.keras.layers.GlobalAveragePooling2D()(base_model.output)
                        x = tf.keras.layers.Dense(1, activation='sigmoid')(x)
                        m = tf.keras.Model(inputs=base_model.input, outputs=x)
                        m.load_weights(path)
                        if MODEL_DEBUG:
                            print("MODEL_DEBUG: Loaded weights into fresh ResNet50 + Dense(1) architecture")
                    else:
                        raise load_err
            
            except Exception as fallback_err:
                if MODEL_DEBUG:
                    print(f"MODEL_DEBUG: Fallback also failed: {fallback_err}")
                raise load_err

        models_cache[path] = m
        return m
    except Exception as e:
        raise


async def _perform_predictions_for_image(pil_image: Image.Image, configured_models: Dict[str, Any], preprocess_override: Optional[str] = None) -> Dict[str, Any]:
    """Helper that runs all configured models on a PIL image and returns the results dict.
    This encapsulates the prediction loop so it can be reused by multiple endpoints (e.g., /analyze_multi).
    """
    results: Dict[str, Any] = {}

    for key, info in configured_models.items():
        path = info.get('model_path')
        model_file = os.path.join(os.path.dirname(__file__), path)
        
        if MODEL_DEBUG:
            print(f"MODEL_DEBUG: Processing model '{key}'")
            print(f"MODEL_DEBUG: Model path from config: {path}")
            print(f"MODEL_DEBUG: Full model file path: {model_file}")
            print(f"MODEL_DEBUG: File exists: {os.path.exists(model_file)}")
            if os.path.exists(model_file):
                print(f"MODEL_DEBUG: File size: {os.path.getsize(model_file)} bytes")
        
        if not os.path.exists(model_file):
            results[key] = {"error": f"Model file not found: {model_file}. Place the .h5 file at this path."}
            continue

        try:
            keras_model = load_keras_model(model_file)
            if MODEL_DEBUG:
                print(f"MODEL_DEBUG: Model loaded successfully from {model_file}")
                print(f"MODEL_DEBUG: Model input shape: {keras_model.input_shape}")
                print(f"MODEL_DEBUG: Model output shape: {keras_model.output_shape}")
        except Exception as e:
            tb = traceback.format_exc()
            print(f"ERROR_STACK_TRACE: Failed to load model {key}: {e}\n{tb}") # Explicitly print to console
            results[key] = {"error": f"Failed to load model {key}: {e}\n{tb}"}
            continue

        # Determine model input size and preprocess image accordingly
        try:
            ishape = getattr(keras_model, 'input_shape', None)
            channels_last = True
            target_size = (224, 224)
            if isinstance(ishape, tuple) and len(ishape) >= 3:
                # Detect whether the model expects channels_last (NHWC) or channels_first (NCHW)
                if len(ishape) == 4:
                    # common shapes: (None, H, W, C) or (None, C, H, W)
                    if ishape[-1] in (1, 3):
                        channels_last = True
                        h = ishape[1] or 224
                        w = ishape[2] or 224
                    elif ishape[1] in (1, 3):
                        channels_last = False
                        h = ishape[2] or 224
                        w = ishape[3] or 224
                    else:
                        # fallback
                        h = ishape[1] or 224
                        w = ishape[2] or 224
                else:
                    # length 3 or other: assume (H, W, C)
                    h = ishape[0] or 224
                    w = ishape[1] or 224
                target_size = (int(w), int(h))
        except Exception:
            target_size = (224, 224)

        # If model expects single-channel input, convert to grayscale
        try:
            expected_channels = None
            if isinstance(ishape, tuple):
                if len(ishape) == 4:
                    expected_channels = ishape[-1] if channels_last else ishape[1]
                elif len(ishape) == 3:
                    expected_channels = ishape[2]
            if expected_channels == 1:
                prep_img = pil_image.convert('L').resize(target_size)
            else:
                prep_img = pil_image.convert('RGB').resize(target_size)
        except Exception:
            prep_img = pil_image.convert('RGB').resize(target_size)
        # Convert to numpy array (float32). For some architectures (ResNet etc.)
        # we need to apply the corresponding ImageNet preprocessing function.
        arr = np.asarray(prep_img).astype(np.float32)
        # Determine preprocessing type from model config (optional)
        preprocess_type = info.get('preprocess')
        # Allow request-level override for debugging/calibration: imagenet | scale | none
        if isinstance(preprocess_override, str) and preprocess_override.strip():
            ov = preprocess_override.strip().lower()
            if ov in ("imagenet", "scale", "none"):
                if MODEL_DEBUG:
                    print(f"MODEL_DEBUG: Overriding preprocess for model '{key}' to '{ov}' (was '{preprocess_type}')")
                preprocess_type = ov
        if preprocess_type == 'imagenet':
            # Use the appropriate Keras preprocessing function (ResNet-style)
            try:
                from tensorflow.keras.applications.resnet50 import preprocess_input as _resnet_preprocess
                arr = _resnet_preprocess(arr)
                if MODEL_DEBUG:
                    print("MODEL_DEBUG: Applied ImageNet (ResNet50) preprocessing")
            except Exception:
                # If import or preprocessing fails, fall back to simple scaling
                if MODEL_DEBUG:
                    print("MODEL_DEBUG: Failed to apply ImageNet preprocess; falling back to /255 normalization")
                arr = arr / 255.0
        elif preprocess_type in ('scale', 'scaled', '/255', 'normalize'):
            arr = arr / 255.0
            if MODEL_DEBUG:
                print("MODEL_DEBUG: Applied simple /255 scaling preprocess")
        elif preprocess_type == 'none':
            # leave as raw float32 pixel values 0..255
            if MODEL_DEBUG:
                print("MODEL_DEBUG: No preprocessing applied (raw pixel values)")
        else:
            # default normalization for non-ImageNet models
            arr = arr / 255.0
        # Ensure batch and channel ordering match model expectation
        if arr.ndim == 2:
            # grayscale single image -> (H, W) -> add channel
            arr = np.expand_dims(arr, -1)

        if not channels_last:
            # transpose HWC -> CHW
            arr = np.transpose(arr, (2, 0, 1))

        # finally add batch dim
        if arr.ndim == 3:
            arr = np.expand_dims(arr, 0)
            # Debug: Print image array stats for chest_xray
            if key == 'chest_xray':
                try:
                    print(f"ARR_DEBUG: Model '{key}' input array shape: {arr.shape}, dtype: {arr.dtype}, min: {np.min(arr)}, max: {np.max(arr)}, mean: {np.mean(arr)}")
                except Exception as e:
                    print(f"ARR_DEBUG: Error printing array stats for '{key}': {e}")

        try:
            # Predict using a single image tensor; avoid touching model.input on unbuilt models
            if MODEL_DEBUG:
                try:
                    print(f"MODEL_DEBUG: Prepared input for '{key}': shape={arr.shape}, dtype={arr.dtype}, channels_last={channels_last}, target_size={target_size}")
                except Exception:
                    pass

            # Ensure model is built if possible to prevent property access errors
            try:
                if hasattr(keras_model, 'built') and not keras_model.built:
                    keras_model.build(arr.shape)
            except Exception:
                pass

            preds = keras_model.predict(arr)
            if MODEL_DEBUG:
                print(f"MODEL_DEBUG: Raw predictions from {key}: {preds}")
                print(f"MODEL_DEBUG: Prediction shape: {preds.shape}")
        except Exception as e:
            tb = traceback.format_exc()
            if MODEL_DEBUG or REQUEST_DEBUG:
                try:
                    print(f"PREDICT_ERROR: Prediction failed for model '{key}': {e}\n{tb}")
                except Exception:
                    pass
            results[key] = {"error": f"Prediction failed for {key}: {e}\n{tb}"}
            continue

        preds = np.array(preds)

        # Determine labels and predicted class
        labels = info.get('labels') or []
        label_id = None
        label_name = None
        probs = []
        top_prob = None
        invert_binary_cfg = bool(info.get('invert_binary', False))
        try:
            if preds.ndim == 2 and preds.shape[1] > 1:
                probs = preds[0].tolist()
                label_id = int(np.argmax(probs))
                label_name = labels[label_id] if label_id < len(labels) else str(label_id)
                try:
                    top_prob = float(max(probs))
                except Exception:
                    top_prob = None
            else:
                val = float(preds.ravel()[0])
                prob_pos = 1.0 / (1.0 + np.exp(-val)) if (val < 0 or val > 1) else val
                probs = [float(1.0 - prob_pos), float(prob_pos)]
                label_id = 1 if prob_pos >= 0.5 else 0
                label_name = labels[label_id] if label_id < len(labels) else str(label_id)
                try:
                    top_prob = float(max(probs))
                except Exception:
                    top_prob = None
        except Exception:
                probs = preds[0].tolist() if preds.ndim > 0 else [float(preds)]
                label_id = int(np.argmax(probs)) if len(probs) > 1 else 0
                label_name = labels[label_id] if label_id < len(labels) else str(label_id)
                try:
                    top_prob = float(max(probs)) if isinstance(probs, list) and probs else None
                except Exception:
                    top_prob = None

        # Optional: invert binary outputs if model was trained with reversed label order
        invert_applied = False
        try:
            if invert_binary_cfg and isinstance(probs, list) and len(probs) == 2:
                probs = [probs[1], probs[0]]
                if isinstance(label_id, int) and label_id in (0, 1):
                    label_id = 1 - label_id
                label_name = labels[label_id] if isinstance(label_id, int) and label_id < len(labels) else str(label_id)
                try:
                    top_prob = float(max(probs))
                except Exception:
                    pass
                invert_applied = True
                if MODEL_DEBUG:
                    print(f"MODEL_DEBUG: invert_binary applied for model '{key}'; swapped probabilities and label mapping")
        except Exception:
            pass

        # Map to class_info for this model using the tolerant mapper
        class_info = info.get('class_info', {})
        
        # Look up disease info in this model's class_info first
        disease_entry = {"disease": "Unknown", "pathogen": "Unknown"}
        if label_name and label_name in class_info:
            disease_entry = class_info[label_name]
        elif class_info:
            # Try case-insensitive match
            for k, v in class_info.items():
                if k.lower() == (label_name or '').lower():
                    disease_entry = v
                    break

        # Fallback: try global disease_info mapping if class_info didn't yield a meaningful result
        try:
            if not disease_entry or (disease_entry.get('disease') in (None, '', 'Unknown')):
                mapped = map_label_to_disease(label_name, label_id, labels)
                global_map = mapped.get('info') or {}
                if global_map.get('disease') and global_map.get('disease') != 'Unknown':
                    # merge but prefer class_info fields if they existed
                    disease_entry = {**global_map, **{k: v for k, v in (disease_entry or {}).items() if v}}
        except Exception:
            pass

        if MODEL_DEBUG:
            print(f"MODEL_DEBUG: Predicted class for '{key}': {label_name} (index: {label_id})")
            print(f"MODEL_DEBUG: All probabilities: {probs}")
            print(f"MODEL_DEBUG: Disease info: {disease_entry}")
            try:
                print(f"MAPPING_DEBUG: model='{key}', label='{label_name}', label_id={label_id}, mapped={disease_entry}")
            except Exception:
                pass

        # Build a helpful mapping of label->probability when labels are available
        probabilities_by_label = None
        try:
            if labels and isinstance(probs, list) and len(labels) == len(probs):
                probabilities_by_label = {str(lbl): float(p) for lbl, p in zip(labels, probs)}
        except Exception:
            probabilities_by_label = None

        results[key] = {
            "display_name": info.get('display_name'),
            "model_path": path,
            "label": label_name,
            "label_id": label_id,
            "probabilities": probs,
            "top_probability": top_prob,
            "probabilities_by_label": probabilities_by_label,
            "invert_binary_used": invert_applied,
            "thresholds": info.get('thresholds'),
            "preprocess_used": preprocess_type,
            "disease": disease_entry.get('disease'),
            "pathogen": disease_entry.get('pathogen'),
            "notes": disease_entry.get('notes'),
            "disease_info": disease_entry,
        }

    return results


@app.post('/analyze_multi')
async def analyze_multi(image_file: Optional[UploadFile] = File(None), file: Optional[UploadFile] = File(None), dna_file: Optional[UploadFile] = File(None), pathogen_type: Optional[str] = None, preprocess_override: Optional[str] = None):
    """Compatibility endpoint for older frontend clients that POST to /analyze_multi.
    Accepts form fields: image_file, dna_file (optional), pathogen_type (optional).
    This will use the same prediction helper as `/predict` and return the same JSON shape.
    """
    global disease_info, disease_info_key_map
    if (image_file or file) and dna_file:
        raise HTTPException(status_code=400, detail="Please provide either an image file or a DNA file, not both.")

    # --- Handle DNA file if provided ---
    if dna_file:
        if REQUEST_DEBUG:
            print(f"REQUEST_DEBUG: DNA file provided: {dna_file.filename}")
        try:
            if os.path.exists(DISEASE_INFO_PATH):
                with open(DISEASE_INFO_PATH, 'r', encoding='utf-8') as f:
                    disease_info = json.load(f)
            dna_model_info = None
            dna_model_key = None
            for key, info in disease_info.items():
                if isinstance(info, dict) and info.get('type') == 'dna':
                    dna_model_info = info
                    dna_model_key = key
                    break
            if not dna_model_info:
                raise HTTPException(status_code=500, detail="No DNA model configured with `\"type\": \"dna\"` in disease_info.json")
            dna_contents = await dna_file.read()
            dna_sequence = ""
            try:
                decoded_contents = dna_contents.decode('utf-8')
                lines = decoded_contents.strip().split('\n')
                if lines and lines[0].startswith('>'):
                    dna_sequence = "".join(lines[1:]).replace('\n', '').replace('\r', '')
                elif lines and lines[0].startswith('@'):
                    dna_sequence = lines[1] if len(lines) > 1 else ""
                else:
                    dna_sequence = decoded_contents.replace('\n', '').replace('\r', '')
            except Exception as parse_err:
                dna_sequence = dna_contents.decode('utf-8').strip().replace('\n', '').replace('\r', '')
            if not dna_sequence:
                return JSONResponse(content={"error": "No valid DNA sequence found in the file."}, status_code=400)
            dna_pred = dna_preprocess_and_predict(dna_sequence, dna_model_info)
            if 'error' in dna_pred:
                return JSONResponse(content={"error": f"DNA analysis failed: {dna_pred['error']}"}, status_code=500)
            # Build JSON result for frontend
            result = {
                "detection": "DETECTED" if dna_pred.get('label', '').lower() == 'pathogenic' else "NOT DETECTED",
                "label": dna_pred.get('label', 'Unknown'),
                "probability": f"{max(dna_pred.get('probabilities', [0]))*100:.2f}%",
                "disease": dna_pred.get('disease', 'Unknown'),
                "notes": dna_pred.get('notes', ''),
                "status": "success",
                "type": "dna"
            }
            return JSONResponse(content={"results": result, "full_results": {dna_model_key: dna_pred}})
        except Exception as e:
            return JSONResponse(content={"error": f"DNA analysis failed: {str(e)}"}, status_code=500)

    # --- Handle Image file if provided ---
    elif image_file or file:
        upload = image_file if image_file is not None else file
        if REQUEST_DEBUG:
            print(f"REQUEST_DEBUG: Image file provided: {upload.filename}")
        contents = await upload.read()
        try:
            src_image = Image.open(io.BytesIO(contents)).convert('RGB')
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid image file")

        # Reload disease_info.json
        try:
            if os.path.exists(DISEASE_INFO_PATH):
                with open(DISEASE_INFO_PATH, 'r', encoding='utf-8') as f:
                    disease_info = json.load(f)
                disease_info_key_map = {k.casefold(): k for k in disease_info.keys()} if disease_info else {}
        except Exception:
            pass

        # Determine which models are configured
        configured_models = {k: v for k, v in disease_info.items() if isinstance(v, dict) and v.get('model_path') and v.get('type') != 'dna'}
        if not configured_models:
            raise HTTPException(status_code=500, detail="No image models configured in disease_info.json.")

        # Select model based on pathogen_type or auto-detection
        selected_key = None
        if pathogen_type:
            if pathogen_type in configured_models:
                selected_key = pathogen_type
            else:
                folded = pathogen_type.casefold()
                if folded in disease_info_key_map and disease_info_key_map[folded] in configured_models:
                    selected_key = disease_info_key_map[folded]
        
        if not selected_key:
            guessed = guess_model_from_image(src_image)
            if guessed and guessed in configured_models:
                selected_key = guessed
            else:
                fb = fallback_choose_model(src_image, configured_models)
                if fb and fb in configured_models:
                    selected_key = fb
        
        if selected_key:
            models_to_run = {selected_key: configured_models[selected_key]}
        else:
            # If no specific model could be chosen, run all available image models
            models_to_run = configured_models

        image_results = await _perform_predictions_for_image(src_image, models_to_run, preprocess_override)
        all_results = image_results

    else:
        raise HTTPException(status_code=400, detail="An image file or a DNA file is required for analysis.")

    if REQUEST_DEBUG:
        print(f"REQUEST_DEBUG: analyze_multi returning results keys: {all_results.keys()}")

    # Create a frontend-friendly summary
    summary = {}
    if all_results:
        # Pick the first result to summarize
        summary_key = next(iter(all_results.keys()), None)
        if summary_key:
            first = all_results[summary_key]
            is_error = isinstance(first, dict) and ('error' in first)
            label = first.get('label', 'Unknown')
            probs = first.get('probabilities', [])
            prob_str = 'N/A'
            numeric_conf = None
            if isinstance(probs, list) and len(probs) > 0:
                top = max(probs)
                numeric_conf = float(top)
                prob_str = f"{top*100:.1f}%"

            # Detection Logic
            detection = 'NOT DETECTED'
            if is_error:
                detection = 'UNKNOWN'
            else:
                # DNA model detection logic
                if first.get('type') == 'dna' or (summary_key and 'dna' in summary_key):
                    if label.lower() == 'pathogenic':
                        detection = 'DETECTED'
                # Image model detection logic
                else:
                    thresholds = first.get('thresholds') or {}
                    probs_by_label = first.get('probabilities_by_label') or {}
                    tb_prob = None
                    tb_label_key = None
                    for k in probs_by_label.keys():
                        if k.lower() in ('tuberculosis', 'tb', 'tuberculous'):
                            tb_label_key = k
                            break
                    if tb_label_key:
                        tb_prob = float(probs_by_label.get(tb_label_key, 0.0))
                        tb_threshold = float(thresholds.get('Tuberculosis', 0.5))
                        detection = 'DETECTED' if tb_prob >= tb_threshold else 'NOT DETECTED'
                    else:
                        # Fallback for non-TB image models
                        if label and label.lower() not in ('uninfected', 'normal', 'healthy', 'none', 'unknown'):
                            detection = 'DETECTED'
            
            summary = {
                'model_used': summary_key,
                'detection': detection,
                'label': label,
                'probability': prob_str,
                'prediction': label,
                'predicted_label': label,
                'confidence': numeric_conf,
                'score': numeric_conf,
                'label_id': first.get('label_id'),
                'probabilities': probs,
                'probabilities_by_label': first.get('probabilities_by_label'),
                'disease': first.get('disease'),
                'pathogen': first.get('pathogen'),
                'preprocess_used': first.get('preprocess_used'),
                'notes': first.get('notes') or '',
                'status': 'error' if is_error else 'success',
                'error': first.get('error') if is_error else None
            }

    # Return both a legacy-friendly `results` summary and the full detailed results
    if REQUEST_DEBUG:
        try:
            print(f"REQUEST_DEBUG: legacy summary: {summary}")
        except Exception:
            pass
    return JSONResponse(content={"results": summary, "full_results": all_results})



def load_pickle_with_compat(filepath: str):
    """Load a pickle file with backward compatibility aliases for legacy Keras module paths."""
    import sys
    import pickle
    try:
        import keras
        if 'keras.src.legacy' not in sys.modules:
            class DummyModule:
                pass
            legacy_mod = DummyModule()
            legacy_mod.preprocessing = getattr(keras, 'preprocessing', None)
            sys.modules['keras.src.legacy'] = legacy_mod
            sys.modules['keras.src.legacy.preprocessing'] = getattr(keras, 'preprocessing', None)
            if hasattr(keras, 'preprocessing') and hasattr(keras.preprocessing, 'text'):
                sys.modules['keras.src.legacy.preprocessing.text'] = keras.preprocessing.text
    except Exception:
        pass

    with open(filepath, 'rb') as f:
        return pickle.load(f)


def sliding_window_dna_analysis(dna_sequence: str, model_info: Dict[str, Any], window_size: int = 200, step_size: int = 50):
    """Analyze DNA using sliding windows, aggregate pathogen predictions."""
    import tensorflow as tf
    import numpy as np

    base_dir = os.path.dirname(__file__)
    tokenizer_cfg = model_info.get('tokenizer_path')
    le_cfg = model_info.get('label_encoder_path')
    model_cfg = model_info.get('model_path')
    tokenizer_path = os.path.join(base_dir, tokenizer_cfg) if tokenizer_cfg else None
    le_path = os.path.join(base_dir, le_cfg) if le_cfg else None
    model_path = os.path.join(base_dir, model_cfg) if model_cfg else None

    tokenizer = load_pickle_with_compat(tokenizer_path)
    label_encoder = load_pickle_with_compat(le_path)
    model = load_keras_model(model_path)

    seq = dna_sequence.strip().upper()
    windows = [seq[i:i+window_size] for i in range(0, len(seq)-window_size+1, step_size)]
    if not windows:
        windows = [seq]

    pathogen_counts = {}
    total_windows = len(windows)
    for window in windows:
        kmers = [window[j:j+6] for j in range(len(window)-5)] if len(window) >= 6 else [window]
        sequences = tokenizer.texts_to_sequences([" ".join(kmers)]) if hasattr(tokenizer, 'texts_to_sequences') else tokenizer.texts_to_sequences([kmers])
        pad_len = model.input_shape[1] if hasattr(model, 'input_shape') and isinstance(model.input_shape, tuple) and len(model.input_shape) >= 2 else max(len(s) for s in sequences)
        from keras.preprocessing.sequence import pad_sequences as _pad
        padded_sequences = _pad(sequences, maxlen=pad_len)
        preds = model.predict(padded_sequences)
        preds = np.array(preds)
        if preds.ndim == 2 and preds.shape[1] > 1:
            probabilities = preds[0].tolist()
            label_index = int(np.argmax(probabilities))
        else:
            val = float(preds.ravel()[0])
            prob_pos = 1.0 / (1.0 + np.exp(-val)) if (val < 0 or val > 1) else val
            probabilities = [1.0 - prob_pos, prob_pos]
            label_index = 1 if prob_pos >= 0.5 else 0
        try:
            label_name = label_encoder.inverse_transform([label_index])[0]
        except Exception:
            try:
                label_name = label_encoder.classes_[label_index]
            except Exception:
                label_name = str(label_index)
        pathogen_counts[label_name] = pathogen_counts.get(label_name, 0) + 1

    percentages = {k: (v/total_windows)*100 for k, v in pathogen_counts.items()}
    return {
        "type": "dna",
        "window_size": window_size,
        "step_size": step_size,
        "total_windows": total_windows,
        "percentages_by_pathogen": percentages,
        "raw_counts": pathogen_counts,
        "status": "success"
    }


def dna_preprocess_and_predict(dna_sequence: str, model_info: Dict[str, Any]) -> Dict[str, Any]:
    """Preprocesses a DNA sequence and predicts using the k-mer model."""
    try:
        import pickle
        import tensorflow as tf
        from keras.preprocessing.sequence import pad_sequences

        # Resolve configured paths relative to project
        base_dir = os.path.dirname(__file__)
        tokenizer_cfg = model_info.get('tokenizer_path')
        le_cfg = model_info.get('label_encoder_path')
        model_cfg = model_info.get('model_path')

        tokenizer_path = os.path.join(base_dir, tokenizer_cfg) if tokenizer_cfg else None
        le_path = os.path.join(base_dir, le_cfg) if le_cfg else None
        model_path = os.path.join(base_dir, model_cfg) if model_cfg else None

        if MODEL_DEBUG:
            print(f"MODEL_DEBUG: DNA model config -> model_path={model_path}, tokenizer_path={tokenizer_path}, label_encoder_path={le_path}")

        # Load tokenizer and label encoder with clear error messages
        if not tokenizer_path or not os.path.exists(tokenizer_path):
            raise FileNotFoundError(f"Tokenizer file not found: {tokenizer_path}")
        if not le_path or not os.path.exists(le_path):
            raise FileNotFoundError(f"Label encoder file not found: {le_path}")

        tokenizer = load_pickle_with_compat(tokenizer_path)
        label_encoder = load_pickle_with_compat(le_path)

        model = load_keras_model(model_path)

        # --- Preprocess DNA sequence into k-mers and numeric sequences ---
        def get_kmers(sequence, k=6):
            seq = sequence.strip().upper()
            return [seq[i:i+k] for i in range(len(seq) - k + 1)] if len(seq) >= k else [seq]

        kmers = get_kmers(dna_sequence)
        # tokenizer expected to be fitted on k-mer strings; texts_to_sequences accepts list of strings
        sequences = tokenizer.texts_to_sequences([" ".join(kmers)]) if hasattr(tokenizer, 'texts_to_sequences') else tokenizer.texts_to_sequences([kmers])
        # Determine pad length; prefer model.input_shape if available
        pad_len = None
        try:
            if hasattr(model, 'input_shape') and isinstance(model.input_shape, tuple):
                # handle shapes like (None, length) or (None, length, channels)
                if len(model.input_shape) >= 2:
                    pad_len = int(model.input_shape[1])
        except Exception:
            pad_len = None
        from keras.preprocessing.sequence import pad_sequences as _pad
        if pad_len is None:
            padded_sequences = _pad(sequences, maxlen=max(len(s) for s in sequences))
        else:
            padded_sequences = _pad(sequences, maxlen=pad_len)

        # --- Predict ---
        preds = model.predict(padded_sequences)
        preds = np.array(preds)

        if preds.ndim == 2 and preds.shape[1] > 1:
            probabilities = preds[0].tolist()
            label_index = int(np.argmax(probabilities))
        else:
            # handle single-output models
            val = float(preds.ravel()[0])
            prob_pos = 1.0 / (1.0 + np.exp(-val)) if (val < 0 or val > 1) else val
            probabilities = [1.0 - prob_pos, prob_pos]
            label_index = 1 if prob_pos >= 0.5 else 0

        # Attempt to decode label name using label encoder
        try:
            label_name = label_encoder.inverse_transform([label_index])[0]
        except Exception:
            # fallback to using classes_ if available
            try:
                label_name = label_encoder.classes_[label_index]
            except Exception:
                label_name = str(label_index)

        probabilities_by_label = {}
        try:
            classes = list(label_encoder.classes_)
            probabilities_by_label = {str(c): float(p) for c, p in zip(classes, probabilities)}
        except Exception:
            probabilities_by_label = {str(label_index): float(max(probabilities))}

        # Map to disease info
        class_info = model_info.get('class_info', {})
        disease_entry = class_info.get(label_name, {"disease": "Unknown", "pathogen": "Unknown"})

        return {
            "type": "dna",
            "model_path_used": model_path,
            "tokenizer_path_used": tokenizer_path,
            "label_encoder_path_used": le_path,
            "label": label_name,
            "label_id": int(label_index),
            "probabilities": probabilities,
            "probabilities_by_label": probabilities_by_label,
            "disease": disease_entry.get('disease'),
            "pathogen": disease_entry.get('pathogen'),
            "notes": disease_entry.get('notes'),
            "status": "success"
        }

    except Exception as e:
        tb = traceback.format_exc()
        print(f"ERROR in dna_preprocess_and_predict: {e}\n{tb}")
        return {"error": f"DNA analysis failed: {e}", "trace": tb}


@app.post("/analyze_dna")
async def analyze_dna(dna_file: UploadFile = File(...)):
    """Analyze an uploaded DNA sequence file and return prediction results.

    The file should contain a raw DNA sequence (e.g., from a FASTA file).
    """
    contents = await dna_file.read()
    try:
        decoded_contents = contents.decode('utf-8').strip()
        lines = decoded_contents.split('\n')
        if lines and lines[0].startswith('>'):
            dna_sequence = "".join(lines[1:]).replace('\n', '').replace('\r', '')
        elif lines and lines[0].startswith('@'):
            dna_sequence = lines[1] if len(lines) > 1 else ""
        else:
            dna_sequence = decoded_contents.replace('\n', '').replace('\r', '')
    except Exception:
        dna_sequence = contents.decode('utf-8', errors='ignore').strip().replace('\n', '').replace('\r', '')

    # Reload disease_info.json on each request to pick up config changes without server restart
    try:
        global disease_info, disease_info_key_map
        if os.path.exists(DISEASE_INFO_PATH):
            with open(DISEASE_INFO_PATH, 'r', encoding='utf-8') as f:
                disease_info = json.load(f)
            disease_info_key_map = {k.casefold(): k for k in disease_info.keys()} if disease_info else {}
    except Exception:
        pass

    # Determine which models are configured in disease_info.json
    configured_models = {k: v for k, v in disease_info.items() if isinstance(v, dict) and v.get('model_path')}
    if not configured_models:
        raise HTTPException(status_code=500, detail="No models configured in disease_info.json with 'model_path'.")

    # For DNA analysis, we expect a specific model configuration
    dna_model_key = None
    for key, info in configured_models.items():
        if info.get('type') == 'dna':
            dna_model_key = key
            break

    if not dna_model_key:
        raise HTTPException(status_code=500, detail="No suitable DNA analysis model configured.")

    # Run prediction using the DNA preprocessing function
    model_info = configured_models[dna_model_key]
    # Use sliding window analysis for mixed pathogen detection
    result = sliding_window_dna_analysis(dna_sequence, model_info, window_size=200, step_size=50)
    return JSONResponse(content={"results": result})
