# YOLO Hand Cursor Controller
This Project is created by Palash Jana

Control your mouse cursor with hand and finger gestures using Python, OpenCV, YOLO, and MediaPipe.

This project is built for webcam-based cursor control and is designed to work across common desktop scenarios such as:
- Moving the cursor smoothly across the screen
- Clicking buttons and selecting items
- Scrolling pages like YouTube, documents, and web pages
- Dragging and dropping files or windows
- Drawing or writing in apps that support mouse-based ink input such as Paint, OneNote, Whiteboard, Excalidraw, or browser canvases

## Features

- Index-finger based cursor movement
- Left click with a quick thumb-index pinch
- Right click with a quick thumb-middle pinch
- Drag and draw mode by holding the pinch
- Scrolling with a two-finger gesture
- Pause and resume gesture control with an open palm
- Precision mode for better fine control
- Sticky draw mode for longer writing or sketching sessions
- YOLO-based hand region detection with MediaPipe landmark fallback
- On-screen status overlay and FPS display
- Right-hand or left-hand tracking support

## Project Files

- `yolo_hand_cursor_controller.py` - main application
- `requirements.txt` - Python dependencies
- `.gitignore` - ignores cache, virtual environment, and model junk files

## Tech Stack

- Python
- OpenCV
- Ultralytics YOLO
- MediaPipe
- PyAutoGUI
- NumPy

## Installation

```powershell
cd C:\Users\PALAS\OneDrive\Documents\Playground\machine-learning\hand-gesture-cursor-control
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

```powershell
python yolo_hand_cursor_controller.py --camera 0 --weights hand_detection.pt
```

If you do not have a YOLO hand detection model yet, the script still runs and falls back to full-frame MediaPipe tracking.

## Command-Line Options

```powershell
python yolo_hand_cursor_controller.py --camera 0 --weights hand_detection.pt --hand Right
```

Available options:
- `--camera` webcam index, default is `0`
- `--weights` path to your YOLO hand detection model
- `--hand` choose `Right` or `Left`

## Gesture Guide

- Open palm: pause or resume control
- Fist: toggle precision mode
- Peace sign: toggle sticky draw mode
- Index finger up: move cursor
- Quick thumb + index pinch: left click
- Hold thumb + index pinch: drag or draw
- Quick thumb + middle pinch: right click
- Index + middle fingers up: scroll

## Best Results

- Use a well-lit room
- Keep the camera stable
- Keep only one hand inside the frame
- Use a plain background if possible
- Start with your hand centered and clearly visible
- For handwriting, use apps that support drawing with the mouse

## Important Note About Notepad

This project can control the cursor inside Notepad for clicking, selecting text, and scrolling.  
Freehand handwritten strokes are not possible in plain Notepad because Notepad does not support digital ink. For handwritten notes, use drawing-enabled apps such as Paint, OneNote, or Microsoft Whiteboard.

## YOLO Model Note

For best results, use a custom YOLO model trained to detect hands. The default command uses:

```powershell
--weights hand_detection.pt
```

If that file is missing, the script automatically falls back to MediaPipe-only tracking.

## Future Improvements

- Gesture-based keyboard shortcuts
- Multi-monitor awareness
- Custom gesture calibration screen
- Volume and brightness control
- Virtual air keyboard
- Saving user profiles for different sensitivity settings

## License

You can add your preferred license for this project before publishing it.

Creator: Palash Jana
Creator GitHub: https://github.com/Palash-Jana
