# Face Expression Analysis
# This project is created by Palash Jana

A simple machine learning project that detects facial expressions from a webcam feed or an uploaded image using Python, OpenCV, and the `fer` emotion recognition library.

## Features

- Detects faces in real time from a webcam
- Predicts the dominant facial expression for each detected face
- Supports still-image analysis
- Saves annotated output images with bounding boxes and emotion labels

## Project Structure

```text
face-expression-analysis/
|-- app.py
|-- emotion_detector.py
|-- requirements.txt
`-- README.md
```

## Tech Stack

- Python 3.10+
- OpenCV
- FER
- TensorFlow

## Setup

1. Clone your repository or copy this folder into your GitHub repo.
2. Open a terminal in `face-expression-analysis/`.
3. Create and activate a virtual environment.

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

4. Install dependencies.

```bash
pip install -r requirements.txt
```

## Run Live Webcam Analysis

```bash
python app.py --mode webcam
```

If your system has multiple cameras, try:

```bash
python app.py --mode webcam --camera-index 1
```

## Run Image Analysis

```bash
python app.py --mode image --image sample.jpg
```

To choose a custom output file:

```bash
python app.py --mode image --image sample.jpg --output result.jpg
```

The script will save an annotated image with the predicted expression label.

## Example Output

For each detected face, the model draws:

- A green bounding box around the face
- The most likely expression label
- The confidence score

Typical labels include:

- angry
- disgust
- fear
- happy
- sad
- surprise
- neutral

## Notes

- First-time setup can take a little longer because TensorFlow is a large dependency.
- Emotion predictions are approximate and can change with lighting, face angle, image quality, and occlusion.
- If no face is detected, the image is still saved but without labels.

## GitHub Upload Tips

After adding these files to your repo, you can push them with:

```bash
git add face-expression-analysis
git commit -m "Add face expression analysis ML project"
git push
```

## License

Use this code freely in your personal, academic, or portfolio projects.

## Creator: Palash Jana
## Creator GitHUb: https://github.com/Palash-Jana
