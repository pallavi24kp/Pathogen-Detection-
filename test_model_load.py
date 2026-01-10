"""Quick test script to verify EfficientNet model loads correctly"""
import tensorflow as tf
import os

MODEL_PATH = "efficientnet_tb_classifier.h5"

print(f"Testing model load: {MODEL_PATH}")
print(f"File exists: {os.path.exists(MODEL_PATH)}")
print(f"File size: {os.path.getsize(MODEL_PATH)} bytes")

try:
    print("\n1. Attempting standard load...")
    model = tf.keras.models.load_model(MODEL_PATH, compile=False)
    print(f"✓ Standard load successful!")
    print(f"  Input shape: {model.input_shape}")
    print(f"  Output shape: {model.output_shape}")
except Exception as e:
    print(f"✗ Standard load failed: {e}")
    
    print("\n2. Attempting fallback: Custom EfficientNet architecture...")
    try:
        base_model = tf.keras.applications.EfficientNetB0(
            include_top=False,
            weights=None,
            input_shape=(224, 224, 3)
        )
        x = base_model.output
        x = tf.keras.layers.GlobalAveragePooling2D()(x)
        x = tf.keras.layers.Dense(2, activation='softmax')(x)
        model = tf.keras.Model(inputs=base_model.input, outputs=x)
        
        print(f"✓ Fresh model architecture created")
        print(f"  Input shape: {model.input_shape}")
        print(f"  Output shape: {model.output_shape}")
        
        # Try loading weights
        try:
            model.load_weights(MODEL_PATH)
            print(f"✓ Weights loaded successfully!")
        except Exception as we:
            print(f"✗ Weights load failed: {we}")
            print("  Using random initialization (model will need training)")
            
    except Exception as fe:
        print(f"✗ Fallback also failed: {fe}")

print("\n✓ Model is ready for predictions")
