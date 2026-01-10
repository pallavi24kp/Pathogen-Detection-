import tensorflow as tf, traceback, os, sys
p = os.path.abspath("resnet_model.h5")
print("Model file:", p)
print("Exists:", os.path.exists(p))
try:
    m = tf.keras.models.load_model(p, compile=False)
    print("Loaded model successfully")
    print("Model inputs:")
    for i, inp in enumerate(m.inputs):
        print(f"  input[{i}]: name={getattr(inp, \"name\", None)}, shape={getattr(inp, \"shape\", None)}, dtype={getattr(inp, \"dtype\", None)}")
    print("Model outputs:")
    for j, out in enumerate(m.outputs):
        print(f"  output[{j}]: name={getattr(out, \"name\", None)}, shape={getattr(out, \"shape\", None)}, dtype={getattr(out, \"dtype\", None)}")
    print("\\nModel summary:")
    m.summary()
except Exception:
    print("ERROR while loading model:", file=sys.stderr)
    traceback.print_exc()
    sys.exit(2)
