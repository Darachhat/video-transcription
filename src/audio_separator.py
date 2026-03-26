import os
import subprocess
from pathlib import Path
from typing import Dict

def separate_audio(audio_path: str, output_dir: str = "temp_assets/separated") -> Dict[str, str]:
    """
    Separate audio into vocals and background music using audio-separator CLI.
    """
    audio_file = Path(audio_path)
    if not audio_file.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"[SEPARATOR] Separating {audio_file.name} using audio-separator...")

    # audio-separator command
    # Using MDX-Net model by default as it's very high quality
    # Model 'UVR-MDX-NET-Voc_FT' is a good choice for vocals/instrumental
    command = [
        "audio-separator",
        str(audio_file),
        "--output_dir", str(output_path),
        "--model_filename", "UVR-MDX-NET-Voc_FT.onnx",
        "--output_format", "WAV"
    ]

    try:
        # Run audio-separator
        process = subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"[SEPARATOR] audio-separator output: {process.stdout}")
    except subprocess.CalledProcessError as e:
        print(f"[SEPARATOR] Error running audio-separator: {e.stderr}")
        raise RuntimeError(f"Audio separation failed: {e.stderr}")

    # audio-separator naming convention: 
    # {filename}_(Vocals)_{model}.wav
    # {filename}_(Instrumental)_{model}.wav
    
    track_name = audio_file.stem
    model_name = "UVR-MDX-NET-Voc_FT"
    
    vocals_path = None
    music_path = None
    
    # List files to find the exact names as they might vary slightly
    for f in output_path.glob("*.wav"):
        if track_name in f.name:
            if "Vocals" in f.name:
                vocals_path = f
            elif "Instrumental" in f.name:
                music_path = f
                
    if not vocals_path or not music_path:
        # Fallback search if naming is different
        files = list(output_path.glob(f"{track_name}*.wav"))
        print(f"[SEPARATOR] Found files: {[f.name for f in files]}")
        raise RuntimeError(f"Separation succeeded but output files not found in {output_path}")

    return {
        "vocals": str(vocals_path),
        "music": str(music_path)
    }

if __name__ == "__main__":
    # Test separation
    import sys
    if len(sys.argv) > 1:
        result = separate_audio(sys.argv[1])
        print(f"Separation result: {result}")
