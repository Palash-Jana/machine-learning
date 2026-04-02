from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import cv2
import face_recognition
import numpy as np

try:
    from ultralytics import YOLO
except Exception:  # pragma: no cover
    YOLO = None


BASE_DIR = Path(__file__).resolve().parents[3]
MODEL_PATH = BASE_DIR / "backend" / "models" / "yolov8n-face.pt"


class FaceService:
    def __init__(self) -> None:
        self.yolo_model = None
        if YOLO is not None and MODEL_PATH.exists():
            self.yolo_model = YOLO(str(MODEL_PATH))
        self.haar = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

    @staticmethod
    def decode_image_bytes(image_bytes: bytes) -> np.ndarray:
        np_buffer = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(np_buffer, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Could not decode image")
        return image

    def detect_faces(self, image: np.ndarray) -> list[tuple[int, int, int, int]]:
        if self.yolo_model is not None:
            results = self.yolo_model.predict(image, verbose=False)
            boxes = []
            for result in results:
                for box in result.boxes.xyxy.tolist():
                    x1, y1, x2, y2 = [int(v) for v in box[:4]]
                    boxes.append((y1, x2, y2, x1))
            if boxes:
                return boxes

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        detected = self.haar.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4)
        return [(y, x + w, y + h, x) for (x, y, w, h) in detected]

    def encoding_from_image_bytes(self, image_bytes: bytes) -> list[float]:
        image = self.decode_image_bytes(image_bytes)
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        boxes = self.detect_faces(image)
        if not boxes:
            raise ValueError("No face detected. Please keep the face clear in the frame.")

        encodings = face_recognition.face_encodings(rgb, known_face_locations=boxes)
        if not encodings:
            raise ValueError("Face detected but encoding failed. Try another angle.")
        return encodings[0].tolist()

    def average_encodings(self, encodings: Iterable[list[float]]) -> list[float]:
        np_encodings = np.array(list(encodings), dtype=np.float64)
        if len(np_encodings) == 0:
            raise ValueError("No facial encodings were generated")
        return np.mean(np_encodings, axis=0).tolist()

    @staticmethod
    def encoding_to_json(encoding: list[float]) -> str:
        return json.dumps(encoding)

    @staticmethod
    def encoding_from_json(value: str) -> np.ndarray:
        return np.array(json.loads(value), dtype=np.float64)

    def compare(
        self, probe_encoding: list[float], known_encoding: np.ndarray
    ) -> tuple[bool, float]:
        distance = face_recognition.face_distance([known_encoding], np.array(probe_encoding))[0]
        confidence = max(0.0, min(1.0, 1.0 - float(distance)))
        return distance < 0.48, confidence


face_service = FaceService()
