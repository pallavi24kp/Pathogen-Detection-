import sys
from PIL import Image
import numpy as np

# Add the current directory to the path to allow importing main
sys.path.append('.')

# It's important to import the function *after* updating the path
from main import guess_model_from_image, HEURISTIC_DEBUG

# --- Configuration ---
# IMPORTANT: These paths must be correct for the script to work.
IMAGE_PATHS = [
    r"C:\Users\Admin\OneDrive\pneumonia bacterial.jpg",
    r"C:\Users\Admin\OneDrive\C100P61ThinF_IMG_20150918_145422_cell_163.png"
]

def analyze_image(image_path):
    """
    Loads an image and runs the model guessing heuristic on it.
    """
    print(f"--- Analyzing Image: {image_path} ---")
    try:
        with Image.open(image_path) as img:
            # Ensure the debug flag is enabled for detailed output
            global HEURISTIC_DEBUG
            HEURISTIC_DEBUG = True
            
            print("Running heuristic analysis...")
            # The guess_model_from_image function will print its own debug info
            model_guess = guess_model_from_image(img)
            print("\n--- Heuristic Result ---")
            print(f"Guessed Model: '{model_guess}'")

    except FileNotFoundError:
        print(f"\n[ERROR] The file was not found at the specified path: {image_path}")
        print("Please make sure the path is correct and the file exists.")
    except Exception as e:
        print(f"\n[ERROR] An unexpected error occurred: {e}")

if __name__ == "__main__":
    for path in IMAGE_PATHS:
        analyze_image(path)
        print("-" * 40)
