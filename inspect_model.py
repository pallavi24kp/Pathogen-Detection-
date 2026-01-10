import tensorflow as tf
import os
import sys

MODEL_PATH = os.path.join(os.path.dirname(__file__), "malaria_detection_model.h5")
if not os.path.exists(MODEL_PATH):
    print("MODEL_NOT_FOUND", MODEL_PATH)
    sys.exit(2)

print("tensorflow", tf.__version__)
print("Loading model:", MODEL_PATH)
try:
    model = tf.keras.models.load_model(MODEL_PATH)
except Exception as e:
    print("MODEL_LOAD_FAILED")
    import traceback
    traceback.print_exc()
    sys.exit(3)

print("--- Model summary top-level ---")
try:
    model.summary(line_length=120, max_depth=2)
except Exception:
    print("(couldn't print full summary)")

print("input_shape:", getattr(model, 'input_shape', None))
print("output_shape:", getattr(model, 'output_shape', None))

# List first 20 layers with type and config
print('\n--- First 40 layers (name, class, output_shape) ---')
for i, layer in enumerate(model.layers[:40]):
    cls = layer.__class__.__name__
    try:
        outsh = layer.output_shape
    except Exception:
        outsh = None
    print(i, layer.name, cls, outsh)

# Look for preprocessing layers
preproc_candidates = []
for layer in model.layers:
    cls = layer.__class__.__name__
    if cls in ('Rescaling', 'Normalization', 'Resizing', 'CenterCrop'):
        preproc_candidates.append((layer.name, cls))
    # also check config for layers that might do scaling
    cfg = layer.get_config()
    if 'scale' in cfg or 'mean' in cfg or 'std' in cfg:
        preproc_candidates.append((layer.name, cls, cfg))

print('\n--- Detected preprocessing-like layers ---')
if preproc_candidates:
    for item in preproc_candidates:
        print(item)
else:
    print('None detected')

# Inspect output layer activation and shape
try:
    out_layer = model.layers[-1]
    print('\nOutput layer:', out_layer.name, out_layer.__class__.__name__)
    cfg = out_layer.get_config()
    print('Output layer config sample keys:', list(cfg.keys())[:10])
    if 'activation' in cfg:
        print('Output activation:', cfg['activation'])
except Exception:
    pass

# Heuristic suggestion for preprocessing
ishape = getattr(model, 'input_shape', None)
if ishape:
    # input shape format: (None, H, W, C) or (None, C, H, W)
    if len(ishape) == 4:
        _, h, w, c = ishape
        print(f"\nSuggested resize: {w}x{h} (width x height), channels: {c}")
    elif len(ishape) == 3:
        h, w, c = ishape
        print(f"\nSuggested resize: {w}x{h} (width x height), channels: {c}")
    else:
        print('\nCould not infer target spatial size from input_shape')

print('\nDone')
