import tensorflow as tf
import os
import numpy as np

MODEL_PATH = 'malaria_detection_model.h5'
print('File exists:', os.path.exists(MODEL_PATH))
print('File size:', os.path.getsize(MODEL_PATH) if os.path.exists(MODEL_PATH) else 'N/A')

try:
    m = tf.keras.models.load_model(MODEL_PATH, compile=False)
    print('Loaded model class:', type(m))
    try:
        print('Input shape:', m.input_shape)
        print('Output shape:', m.output_shape)
    except Exception as e:
        print('Could not read shapes:', e)

    # Prepare dummy input based on input_shape
    inp_shape = None
    if hasattr(m, 'input_shape') and m.input_shape:
        ishape = m.input_shape
        # ishape may be (None, H, W, C) or similar
        if len(ishape) == 4:
            inp_shape = (1, ishape[1] or 64, ishape[2] or 64, ishape[3] or 3)
    if inp_shape is None:
        inp_shape = (1, 64, 64, 3)

    print('Using dummy input shape:', inp_shape)
    dummy = np.zeros(inp_shape, dtype=np.float32)
    try:
        preds = m.predict(dummy)
        print('Predictions shape:', preds.shape)
        print('Raw predictions:', preds)
    except Exception as e:
        print('Prediction failed:', e)

except Exception as e:
    print('Load failed:', e)
