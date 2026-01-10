"""Inspect the EfficientNet .h5 file structure"""
import h5py
import json

MODEL_PATH = "efficientnet_tb_classifier.h5"

print(f"Inspecting: {MODEL_PATH}\n")

with h5py.File(MODEL_PATH, 'r') as f:
    print("=== Top-level keys ===")
    for key in f.keys():
        print(f"  - {key}")
    
    print("\n=== Model Config ===")
    if 'model_config' in f.attrs:
        config = json.loads(f.attrs['model_config'])
        print(f"Class: {config.get('class_name')}")
        print(f"Backend: {config.get('backend', 'N/A')}")
        
        if 'config' in config:
            cfg = config['config']
            print(f"Name: {cfg.get('name', 'N/A')}")
            
            if 'layers' in cfg:
                print(f"\nLayers ({len(cfg['layers'])} total):")
                for i, layer in enumerate(cfg['layers'][:5]):  # First 5 layers
                    print(f"  {i}: {layer.get('class_name')} - {layer.get('config', {}).get('name')}")
                if len(cfg['layers']) > 5:
                    print(f"  ... ({len(cfg['layers']) - 5} more layers)")
    
    print("\n=== Weight Keys ===")
    if 'model_weights' in f:
        mw = f['model_weights']
        print(f"Model weights group keys: {list(mw.keys())[:10]}")
        
        # Count total layers with weights
        layer_count = 0
        for key in mw.keys():
            if isinstance(mw[key], h5py.Group):
                layer_count += 1
        print(f"Total layers with weights: {layer_count}")
    
    print("\n=== Trying to extract layer structure ===")
    if 'model_weights' in f:
        print("Layer names with weights:")
        for i, key in enumerate(list(f['model_weights'].keys())[:10]):
            print(f"  {i}: {key}")
        if len(list(f['model_weights'].keys())) > 10:
            print(f"  ... ({len(list(f['model_weights'].keys())) - 10} more)")
