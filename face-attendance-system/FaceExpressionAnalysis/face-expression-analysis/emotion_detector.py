from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import cv2
from fer import FER


@dataclass
class DetectionResult:
    box: Tuple[int, int, int, int]
    emotion: str
    score: float


class EmotionDetector:
    def __init__(self) -> None:
        self.model = FER(mtcnn=False)
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.face_cascade = cv2.CascadeClassifier(cascade_path)

    def _find_faces(self, frame) -> List[Tuple[int, int, int, int]]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(48, 48),
        )
        return [tuple(map(int, face)) for face in faces]

    def detect(self, frame) -> List[DetectionResult]:
        results: List[DetectionResult] = []

        for x, y, w, h in self._find_faces(frame):
            face_region = frame[y : y + h, x : x + w]
            if face_region.size == 0:
                continue

            emotions = self.model.detect_emotions(face_region)
            if not emotions:
                continue

            emotion_scores = emotions[0]["emotions"]
            top_emotion = max(emotion_scores, key=emotion_scores.get)
            top_score = float(emotion_scores[top_emotion])
            results.append(
                DetectionResult(
                    box=(x, y, w, h),
                    emotion=top_emotion,
                    score=top_score,
                )
            )

        return results

    @staticmethod
    def annotate(frame, detections: List[DetectionResult]):
        annotated = frame.copy()

        for detection in detections:
            x, y, w, h = detection.box
            label = f"{detection.emotion} ({detection.score:.2f})"
            cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 200, 0), 2)
            cv2.rectangle(annotated, (x, y - 28), (x + w, y), (0, 200, 0), -1)
            cv2.putText(
                annotated,
                label,
                (x + 6, y - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 0, 0),
                2,
                cv2.LINE_AA,
            )

        return annotated

    def process_image(self, image_path: str, output_path: str | None = None) -> Path:
        input_path = Path(image_path)
        frame = cv2.imread(str(input_path))
        if frame is None:
            raise FileNotFoundError(f"Could not read image: {input_path}")

        detections = self.detect(frame)
        annotated = self.annotate(frame, detections)

        destination = Path(output_path) if output_path else input_path.with_name(
            f"{input_path.stem}_annotated{input_path.suffix}"
        )
        cv2.imwrite(str(destination), annotated)
        return destination
