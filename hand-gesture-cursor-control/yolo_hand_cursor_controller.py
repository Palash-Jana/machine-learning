"""
Hand gesture cursor controller using OpenCV, YOLO and MediaPipe.

What this script can do
- Move the mouse cursor with your index finger
- Left click with a quick thumb-index pinch
- Right click with a quick thumb-middle pinch
- Drag or draw by holding the thumb-index pinch
- Scroll with a two-finger gesture
- Toggle pause/resume with an open palm
- Toggle precision mode with a fist
- Toggle sticky drawing mode with a peace sign

Notes
- YOLO is used to crop a likely hand region before landmark extraction.
- MediaPipe is used for finger landmarks because it is much more precise
  for fingertip tracking than generic object detection.
- "Handwritten notes" works best in apps that support drawing with a mouse,
  such as OneNote, Paint, Whiteboard, Excalidraw, or browser-based canvases.
  In Notepad, this script can still move, click, drag-select, and scroll, but
  Notepad itself does not support freehand ink strokes.

Install
    pip install -r requirements.txt

Run
    python yolo_hand_cursor_controller.py --camera 0 --weights hand_detection.pt

If you do not have a trained YOLO hand model yet, the script will still run
using the full frame as a fallback for MediaPipe.
"""

from __future__ import annotations

import argparse
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import pyautogui

try:
    import mediapipe as mp
except ImportError as exc:  # pragma: no cover - import guard
    raise SystemExit(
        "MediaPipe is required. Install dependencies with: pip install -r requirements.txt"
    ) from exc

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None


pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def distance(point_a: tuple[int, int], point_b: tuple[int, int]) -> float:
    return math.hypot(point_a[0] - point_b[0], point_a[1] - point_b[1])


@dataclass
class GestureConfig:
    camera_index: int = 0
    frame_width: int = 1280
    frame_height: int = 720
    min_detection_confidence: float = 0.65
    min_tracking_confidence: float = 0.60
    cursor_smoothing: float = 0.35
    precision_smoothing: float = 0.18
    roi_margin: float = 0.08
    click_pinch_ratio: float = 0.33
    release_pinch_ratio: float = 0.42
    drag_hold_seconds: float = 0.32
    click_cooldown_seconds: float = 0.25
    pause_cooldown_seconds: float = 1.2
    mode_cooldown_seconds: float = 1.0
    scroll_speed: float = 24.0
    scroll_deadzone: float = 0.015
    yolo_confidence: float = 0.20
    yolo_iou: float = 0.35
    handedness: str = "Right"


@dataclass
class RuntimeState:
    paused: bool = False
    precision_mode: bool = False
    sticky_draw_mode: bool = False
    dragging: bool = False
    last_left_click: float = 0.0
    last_right_click: float = 0.0
    last_pause_toggle: float = 0.0
    last_mode_toggle: float = 0.0
    pinch_started_at: Optional[float] = None
    right_pinch_active: bool = False
    last_scroll_y: Optional[float] = None
    smoothed_cursor: Optional[np.ndarray] = None
    status_message: str = "Ready"
    status_until: float = 0.0
    yolo_enabled: bool = False
    fps: float = 0.0
    fps_timer: float = field(default_factory=time.perf_counter)
    frame_counter: int = 0

    def flash(self, message: str, seconds: float = 1.3) -> None:
        self.status_message = message
        self.status_until = time.time() + seconds


class YoloHandRegionDetector:
    def __init__(self, weights_path: Optional[str], confidence: float, iou: float) -> None:
        self.model = None
        self.confidence = confidence
        self.iou = iou
        self.weights_path = Path(weights_path) if weights_path else None

        if YOLO is None or self.weights_path is None or not self.weights_path.exists():
            return

        self.model = YOLO(str(self.weights_path))

    def detect(self, frame: np.ndarray) -> Optional[tuple[int, int, int, int]]:
        if self.model is None:
            return None

        results = self.model.predict(
            source=frame,
            conf=self.confidence,
            iou=self.iou,
            verbose=False,
            imgsz=640,
        )
        if not results or results[0].boxes is None or len(results[0].boxes) == 0:
            return None

        boxes = results[0].boxes.xyxy.cpu().numpy()
        scores = results[0].boxes.conf.cpu().numpy()
        best_index = int(np.argmax(scores))
        x1, y1, x2, y2 = boxes[best_index].astype(int)
        return x1, y1, x2, y2


class HandGestureCursorController:
    def __init__(self, config: GestureConfig, weights_path: Optional[str]) -> None:
        self.config = config
        self.state = RuntimeState()
        self.screen_width, self.screen_height = pyautogui.size()
        self.region_detector = YoloHandRegionDetector(
            weights_path=weights_path,
            confidence=config.yolo_confidence,
            iou=config.yolo_iou,
        )
        self.state.yolo_enabled = self.region_detector.model is not None

        self.mp_hands = mp.solutions.hands
        self.mp_draw = mp.solutions.drawing_utils
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=config.min_detection_confidence,
            min_tracking_confidence=config.min_tracking_confidence,
            model_complexity=1,
        )

    def run(self) -> None:
        capture = cv2.VideoCapture(self.config.camera_index)
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.frame_width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.frame_height)

        if not capture.isOpened():
            raise SystemExit("Could not open the camera. Check the camera index and permissions.")

        try:
            while True:
                success, frame = capture.read()
                if not success:
                    continue

                frame = cv2.flip(frame, 1)
                processed_frame = self.process_frame(frame)
                cv2.imshow("YOLO Hand Cursor Controller", processed_frame)

                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")):
                    break
                if key == ord("p"):
                    self.toggle_pause()
                if key == ord("c"):
                    self.reset_tracking()
        finally:
            if self.state.dragging:
                pyautogui.mouseUp()
            capture.release()
            cv2.destroyAllWindows()

    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        annotated = frame.copy()
        hand_crop, offset = self.extract_hand_region(frame, annotated)

        rgb = cv2.cvtColor(hand_crop, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb)

        if results.multi_hand_landmarks and results.multi_handedness:
            handedness_label = results.multi_handedness[0].classification[0].label
            if handedness_label == self.config.handedness:
                landmarks = results.multi_hand_landmarks[0]
                full_landmarks = self.project_landmarks(landmarks, hand_crop.shape, offset)
                self.handle_gestures(full_landmarks, annotated, handedness_label)
                self.draw_landmarks(annotated, full_landmarks)
            else:
                self.state.last_scroll_y = None
                self.release_drag_if_needed()
                self.state.right_pinch_active = False
        else:
            self.state.last_scroll_y = None
            self.release_drag_if_needed()
            self.state.right_pinch_active = False

        self.draw_overlay(annotated)
        self.update_fps()
        return annotated

    def extract_hand_region(
        self,
        frame: np.ndarray,
        annotated: np.ndarray,
    ) -> tuple[np.ndarray, tuple[int, int]]:
        box = self.region_detector.detect(frame)
        if box is None:
            return frame, (0, 0)

        height, width = frame.shape[:2]
        x1, y1, x2, y2 = box
        margin_x = int((x2 - x1) * self.config.roi_margin)
        margin_y = int((y2 - y1) * self.config.roi_margin)

        x1 = clamp(x1 - margin_x, 0, width - 1)
        y1 = clamp(y1 - margin_y, 0, height - 1)
        x2 = clamp(x2 + margin_x, 0, width - 1)
        y2 = clamp(y2 + margin_y, 0, height - 1)

        x1_i, y1_i, x2_i, y2_i = map(int, (x1, y1, x2, y2))
        cv2.rectangle(annotated, (x1_i, y1_i), (x2_i, y2_i), (255, 178, 29), 2)
        cv2.putText(
            annotated,
            "YOLO hand ROI",
            (x1_i, max(20, y1_i - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 178, 29),
            2,
        )
        return frame[y1_i:y2_i, x1_i:x2_i], (x1_i, y1_i)

    def project_landmarks(
        self,
        landmarks: mp.framework.formats.landmark_pb2.NormalizedLandmarkList,
        crop_shape: tuple[int, int, int],
        offset: tuple[int, int],
    ) -> list[tuple[int, int]]:
        crop_height, crop_width = crop_shape[:2]
        offset_x, offset_y = offset

        points: list[tuple[int, int]] = []
        for landmark in landmarks.landmark:
            x = int(landmark.x * crop_width) + offset_x
            y = int(landmark.y * crop_height) + offset_y
            points.append((x, y))
        return points

    def handle_gestures(
        self,
        points: list[tuple[int, int]],
        frame: np.ndarray,
        handedness_label: str,
    ) -> None:
        fingers = self.get_finger_states(points, handedness_label)
        pinch_index = self.normalized_pinch(points, 4, 8)
        pinch_middle = self.normalized_pinch(points, 4, 12)
        now = time.time()

        open_palm = fingers == [1, 1, 1, 1, 1]
        fist = fingers == [0, 0, 0, 0, 0]
        peace_sign = fingers == [0, 1, 1, 0, 0]
        move_pose = fingers[1] == 1 and fingers[2] == 0 and fingers[3] == 0
        scroll_pose = fingers[1] == 1 and fingers[2] == 1 and fingers[3] == 0 and fingers[4] == 0

        if open_palm and now - self.state.last_pause_toggle > self.config.pause_cooldown_seconds:
            self.toggle_pause()
            self.state.last_pause_toggle = now
            return

        if fist and now - self.state.last_mode_toggle > self.config.mode_cooldown_seconds:
            self.state.precision_mode = not self.state.precision_mode
            self.state.last_mode_toggle = now
            self.state.flash(
                f"Precision mode {'ON' if self.state.precision_mode else 'OFF'}"
            )
            return

        if peace_sign and now - self.state.last_mode_toggle > self.config.mode_cooldown_seconds:
            self.state.sticky_draw_mode = not self.state.sticky_draw_mode
            self.state.last_mode_toggle = now
            self.state.flash(
                f"Sticky draw {'ON' if self.state.sticky_draw_mode else 'OFF'}"
            )
            return

        if self.state.paused:
            self.release_drag_if_needed()
            self.state.last_scroll_y = None
            self.state.right_pinch_active = False
            return

        if scroll_pose:
            self.handle_scroll(points, frame.shape)
            self.release_drag_if_needed(force=False)
            return

        self.state.last_scroll_y = None

        if move_pose or self.state.sticky_draw_mode:
            self.move_cursor(points[8], frame.shape)

        self.handle_left_click_and_drag(pinch_index, now)
        self.handle_right_click(pinch_middle, now)

    def move_cursor(self, index_tip: tuple[int, int], frame_shape: tuple[int, int, int]) -> None:
        frame_height, frame_width = frame_shape[:2]
        margin_x = int(frame_width * 0.07)
        margin_y = int(frame_height * 0.07)

        usable_x = clamp(index_tip[0], margin_x, frame_width - margin_x)
        usable_y = clamp(index_tip[1], margin_y, frame_height - margin_y)

        norm_x = (usable_x - margin_x) / max(1, (frame_width - margin_x * 2))
        norm_y = (usable_y - margin_y) / max(1, (frame_height - margin_y * 2))

        target = np.array(
            [norm_x * self.screen_width, norm_y * self.screen_height],
            dtype=np.float32,
        )

        smoothing = (
            self.config.precision_smoothing
            if self.state.precision_mode
            else self.config.cursor_smoothing
        )

        if self.state.smoothed_cursor is None:
            self.state.smoothed_cursor = target
        else:
            self.state.smoothed_cursor = (
                (1.0 - smoothing) * self.state.smoothed_cursor + smoothing * target
            )

        x, y = self.state.smoothed_cursor.astype(int)
        pyautogui.moveTo(x, y)

    def handle_left_click_and_drag(self, pinch_index: float, now: float) -> None:
        is_pinched = pinch_index < self.config.click_pinch_ratio
        released = pinch_index > self.config.release_pinch_ratio

        if is_pinched and self.state.pinch_started_at is None:
            self.state.pinch_started_at = now

        if is_pinched and self.state.pinch_started_at is not None:
            held_for = now - self.state.pinch_started_at
            if (
                held_for >= self.config.drag_hold_seconds
                and not self.state.dragging
            ):
                pyautogui.mouseDown()
                self.state.dragging = True
                self.state.flash("Drag/Draw active")

        if released:
            if self.state.dragging:
                pyautogui.mouseUp()
                self.state.dragging = False
                self.state.flash("Drag/Draw released")
            elif (
                self.state.pinch_started_at is not None
                and now - self.state.pinch_started_at < self.config.drag_hold_seconds
                and now - self.state.last_left_click > self.config.click_cooldown_seconds
            ):
                pyautogui.click()
                self.state.last_left_click = now
                self.state.flash("Left click")
            self.state.pinch_started_at = None

        if self.state.sticky_draw_mode and not self.state.dragging and is_pinched:
            pyautogui.mouseDown()
            self.state.dragging = True
            self.state.flash("Sticky drawing")

    def handle_right_click(self, pinch_middle: float, now: float) -> None:
        is_pinched = pinch_middle < self.config.click_pinch_ratio
        released = pinch_middle > self.config.release_pinch_ratio

        if (
            is_pinched
            and not self.state.right_pinch_active
            and now - self.state.last_right_click > self.config.click_cooldown_seconds
            and not self.state.dragging
        ):
            pyautogui.rightClick()
            self.state.last_right_click = now
            self.state.right_pinch_active = True
            self.state.flash("Right click")
        elif released:
            self.state.right_pinch_active = False

    def handle_scroll(
        self,
        points: list[tuple[int, int]],
        frame_shape: tuple[int, int, int],
    ) -> None:
        index_tip = points[8]
        current_y = index_tip[1] / max(1, frame_shape[0])

        if self.state.last_scroll_y is None:
            self.state.last_scroll_y = current_y
            return

        delta = self.state.last_scroll_y - current_y
        if abs(delta) > self.config.scroll_deadzone:
            pyautogui.scroll(int(delta * self.config.scroll_speed * 100))
            self.state.flash("Scrolling", seconds=0.3)
        self.state.last_scroll_y = current_y

    def toggle_pause(self) -> None:
        self.state.paused = not self.state.paused
        if self.state.paused:
            self.release_drag_if_needed()
        self.state.flash(f"{'Paused' if self.state.paused else 'Resumed'}")

    def release_drag_if_needed(self, force: bool = True) -> None:
        if self.state.dragging and force:
            pyautogui.mouseUp()
            self.state.dragging = False
        if not self.state.dragging:
            self.state.pinch_started_at = None

    def reset_tracking(self) -> None:
        self.release_drag_if_needed()
        self.state.last_scroll_y = None
        self.state.smoothed_cursor = None
        self.state.flash("Tracking reset")

    def normalized_pinch(
        self,
        points: list[tuple[int, int]],
        landmark_a: int,
        landmark_b: int,
    ) -> float:
        wrist = points[0]
        middle_knuckle = points[9]
        palm_size = max(1.0, distance(wrist, middle_knuckle))
        return distance(points[landmark_a], points[landmark_b]) / palm_size

    def get_finger_states(self, points: list[tuple[int, int]], handedness_label: str) -> list[int]:
        if handedness_label == "Right":
            thumb_open = 1 if points[4][0] > points[3][0] else 0
        else:
            thumb_open = 1 if points[4][0] < points[3][0] else 0
        index_open = 1 if points[8][1] < points[6][1] else 0
        middle_open = 1 if points[12][1] < points[10][1] else 0
        ring_open = 1 if points[16][1] < points[14][1] else 0
        pinky_open = 1 if points[20][1] < points[18][1] else 0
        return [thumb_open, index_open, middle_open, ring_open, pinky_open]

    def draw_landmarks(self, frame: np.ndarray, points: list[tuple[int, int]]) -> None:
        connections = (
            (0, 1), (1, 2), (2, 3), (3, 4),
            (0, 5), (5, 6), (6, 7), (7, 8),
            (5, 9), (9, 10), (10, 11), (11, 12),
            (9, 13), (13, 14), (14, 15), (15, 16),
            (13, 17), (17, 18), (18, 19), (19, 20),
            (0, 17),
        )

        for start, end in connections:
            cv2.line(frame, points[start], points[end], (74, 255, 168), 2)
        for idx, point in enumerate(points):
            radius = 8 if idx in (4, 8, 12) else 5
            color = (0, 255, 255) if idx == 8 else (255, 110, 87)
            cv2.circle(frame, point, radius, color, -1)

    def draw_overlay(self, frame: np.ndarray) -> None:
        top_h = 120
        cv2.rectangle(frame, (0, 0), (frame.shape[1], top_h), (18, 18, 18), -1)
        cv2.addWeighted(frame, 0.86, frame, 0.14, 0, frame)

        status = self.state.status_message
        if time.time() > self.state.status_until:
            status = "Paused" if self.state.paused else "Tracking"

        lines = [
            f"Status: {status}",
            f"YOLO ROI: {'ON' if self.state.yolo_enabled else 'OFF (fallback to full frame)'}",
            f"Precision: {'ON' if self.state.precision_mode else 'OFF'}  |  Sticky Draw: {'ON' if self.state.sticky_draw_mode else 'OFF'}",
            "Gestures: open palm=pause, fist=precision, peace sign=sticky draw, pinch=click/drag, two fingers=scroll",
            f"FPS: {self.state.fps:.1f}",
        ]

        for idx, text in enumerate(lines):
            cv2.putText(
                frame,
                text,
                (16, 24 + idx * 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.57,
                (240, 240, 240),
                2,
            )

        if self.state.paused:
            cv2.putText(
                frame,
                "PAUSED",
                (frame.shape[1] - 150, 40),
                cv2.FONT_HERSHEY_DUPLEX,
                1.0,
                (0, 0, 255),
                2,
            )

    def update_fps(self) -> None:
        self.state.frame_counter += 1
        now = time.perf_counter()
        elapsed = now - self.state.fps_timer
        if elapsed >= 1.0:
            self.state.fps = self.state.frame_counter / elapsed
            self.state.fps_timer = now
            self.state.frame_counter = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Control the mouse cursor using hand gestures with YOLO + OpenCV."
    )
    parser.add_argument("--camera", type=int, default=0, help="Camera index")
    parser.add_argument(
        "--weights",
        type=str,
        default="hand_detection.pt",
        help="Path to a YOLO hand-detection model. Fallback is full-frame tracking.",
    )
    parser.add_argument(
        "--hand",
        type=str,
        default="Right",
        choices=["Left", "Right"],
        help="Handedness to track.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = GestureConfig(camera_index=args.camera, handedness=args.hand)
    controller = HandGestureCursorController(config=config, weights_path=args.weights)
    controller.run()


if __name__ == "__main__":
    main()
