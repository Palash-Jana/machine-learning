# Face Attendance System

Full-stack classroom attendance software with:

- React web interface with `Attendance Mode` and `Admin Mode`
- Python FastAPI backend
- OpenCV + face recognition for enrollment and attendance
- YOLO face detector support when `backend/models/yolov8n-face.pt` is added
- Admin login, editable admin credentials, student enrollment, attendance window control
- Daily CSV export for admin only
- SQLite local database for easy GitHub upload and local setup

## Default admin login

- Admin ID: `AdminID`
- Password: `admin@123`

## Features

- Student face enrollment from multiple camera captures
- Admin stores roll number, student name, father name, and address
- Attendance works only during the configured class time period
- Duplicate attendance for the same day is blocked automatically
- Late marking support with configurable grace minutes
- Dashboard cards for total, present, late, and absent students
- CSV download for a selected day endpoint, with frontend button for today's file
- Delete student support for cleanup

## Project structure

```text
face-attendance-system/
  backend/
    app/
    data/
    models/
    requirements.txt
  frontend/
    src/
  .gitignore
  README.md
```

## Backend setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend runs on `http://127.0.0.1:8000`.

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://127.0.0.1:5173`.

If you want the backend to serve the built frontend:

```bash
cd frontend
npm install
npm run build
```

Then start FastAPI again and it will serve `frontend/dist` automatically.

## YOLO model

The code includes YOLO face detection support using Ultralytics. Place a face model file here:

```text
backend/models/yolov8n-face.pt
```

If that file is not present, the system falls back to OpenCV Haar face detection so the app still works.

## Important notes

- Browser camera access requires user permission.
- Face recognition quality improves when you capture clear front, left, right, and slightly tilted face angles.
- `face_recognition` may need CMake/build tools on some systems during install.
- For production, change the JWT secret with environment variable `ATTENDANCE_SECRET_KEY`.

