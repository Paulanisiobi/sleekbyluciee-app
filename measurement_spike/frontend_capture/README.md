Frontend Capture UI

This is a simple browser-based capture UI that:
- Opens the device camera (facing user)
- Shows an overlay box with guidance
- Captures a cropped image inside the guidance box
- Sends the cropped photo to the spike `/measure` endpoint

Run locally
1. Run a simple static server from the `measurement_spike/frontend_capture` folder (camera access requires `http`/`https`, not file://):

```bash
cd measurement_spike/frontend_capture
python -m http.server 8000
# then open http://127.0.0.1:8000 in a browser that supports getUserMedia
```

2. Start the Flask measurement spike (see `measurement_spike/README.md`).
3. Open the capture UI and press `Capture Photo`, then `Send to /measure`.

Notes & improvements
- The UI crops to the guidance box before sending to reduce payload and improve landmark detection.
- For production, implement capture retries, automatic orientation handling, face/body alignment feedback, and a consent modal before camera access.
