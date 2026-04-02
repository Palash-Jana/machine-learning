# This code is part of the Face Expression Analysis project.
# Created by Palash Jana on 2025-06-01.
from __future__ import annotations

import argparse

import cv2

from emotion_detector import EmotionDetector


def run_webcam(camera_index: int) -> None:
    detector = EmotionDetector()
    capture = cv2.VideoCapture(camera_index)

    if not capture.isOpened():
        raise RuntimeError("Unable to open webcam. Check camera permissions or camera index.")

    print("Press 'q' to quit the live emotion analysis window.")

    while True:
        has_frame, frame = capture.read()
        if not has_frame:
            print("Skipping an empty frame from the webcam.")
            continue

        detections = detector.detect(frame)
        annotated = detector.annotate(frame, detections)
        cv2.imshow("Face Expression Analysis", annotated)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    capture.release()
    cv2.destroyAllWindows()


def run_image(image_path: str, output_path: str | None) -> None:
    detector = EmotionDetector()
    saved_to = detector.process_image(image_path=image_path, output_path=output_path)
    print(f"Annotated image saved to: {saved_to}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze facial expressions from a webcam feed or a still image."
    )
    parser.add_argument(
        "--mode",
        choices=["webcam", "image"],
        default="webcam",
        help="Choose webcam for live analysis or image for a single file.",
    )
    parser.add_argument(
        "--image",
        help="Path to the input image when using --mode image.",
    )
    parser.add_argument(
        "--output",
        help="Optional output path for the annotated image.",
    )
    parser.add_argument(
        "--camera-index",
        type=int,
        default=0,
        help="Webcam index to open when using webcam mode.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.mode == "image":
        if not args.image:
            parser.error("--image is required when --mode image is used.")
        run_image(args.image, args.output)
        return

    run_webcam(args.camera_index)


if __name__ == "__main__":
    main()
