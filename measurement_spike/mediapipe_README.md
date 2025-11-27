MediaPipe Measurement POC

Purpose
- Quick prototype using MediaPipe Pose to extract body landmarks and estimate basic measurements.

Requirements
- Python 3.8+
- Install dependencies in `measurement_spike/requirements.txt`:

```bash
python -m venv .venv
source .venv/Scripts/activate   # windows bash
pip install -r requirements.txt
```

Run example

```bash
python mediapipe_poc.py --images front.jpg side.jpg --height 165
```

Output
- JSON printed to stdout with per-image estimated measurements and a confidence score.

Notes & Next Steps
- This POC uses heuristic scaling to convert px → cm using a user-supplied height; production should use calibrated reference markers or a 3D approach.
- Add front/side alignment checks, overlay guidance in the mobile UI, and a manual correction flow for low confidence results.
- Consider 3rd-party SDKs if more accurate anthropometric extraction is required.
