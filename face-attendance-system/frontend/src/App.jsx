import { useEffect, useRef, useState } from "react";
import { API_BASE, apiRequest } from "./api";

function StatusPill({ active }) {
  return (
    <span className={`pill ${active ? "pill-live" : "pill-closed"}`}>
      {active ? "Attendance Window Live" : "Attendance Closed"}
    </span>
  );
}

function VideoCard({ videoRef, started }) {
  return (
    <div className="video-card">
      <video ref={videoRef} autoPlay muted playsInline className="video-feed" />
      {!started && <div className="video-overlay">Camera permission is required</div>}
    </div>
  );
}

async function captureFrame(video, canvas) {
  if (!video || !canvas) {
    throw new Error("Camera not ready");
  }
  const width = video.videoWidth || 640;
  const height = video.videoHeight || 480;
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  context.drawImage(video, 0, 0, width, height);
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) {
        resolve(blob);
      } else {
        reject(new Error("Capture failed"));
      }
    }, "image/jpeg", 0.95);
  });
}

function AttendanceMode({ settings }) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const [cameraStarted, setCameraStarted] = useState(false);
  const [message, setMessage] = useState("Waiting for attendance window.");
  const [attendanceResult, setAttendanceResult] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let stream;
    async function setup() {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: true });
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
        setCameraStarted(true);
      } catch (error) {
        setMessage("Unable to access camera. Please allow webcam permission.");
      }
    }
    setup();
    return () => {
      if (stream) {
        stream.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  async function markAttendance() {
    if (!videoRef.current || !canvasRef.current || !settings.window_active) {
      return;
    }
    setSubmitting(true);
    try {
      const blob = await captureFrame(videoRef.current, canvasRef.current);
      const formData = new FormData();
      formData.append("image", blob, "attendance.jpg");
      const result = await apiRequest("/api/attendance/recognize", {
        method: "POST",
        body: formData
      });
      setAttendanceResult(result);
      setMessage(result.message);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setSubmitting(false);
    }
  }

  useEffect(() => {
    if (!settings.window_active || !cameraStarted) {
      return undefined;
    }
    const timer = setInterval(() => {
      markAttendance();
    }, 5000);
    return () => clearInterval(timer);
  }, [settings.window_active, cameraStarted]);

  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2>Attendance Mode</h2>
          <p>Students just look at the camera during the allowed class time.</p>
        </div>
        <StatusPill active={settings.window_active} />
      </div>
      <VideoCard videoRef={videoRef} started={cameraStarted} />
      <canvas ref={canvasRef} hidden />
      <div className="actions">
        <button className="primary-button" onClick={markAttendance} disabled={!settings.window_active || submitting}>
          {submitting ? "Recognizing..." : "Mark Attendance Now"}
        </button>
      </div>
      <div className="result-card">
        <p className="result-message">{message}</p>
        {attendanceResult?.student && (
          <div className="result-grid">
            <span>{attendanceResult.student.name}</span>
            <span>{attendanceResult.student.roll_no}</span>
            <span>{attendanceResult.status}</span>
            <span>{Math.round((attendanceResult.confidence || 0) * 100)}% confidence</span>
          </div>
        )}
      </div>
    </section>
  );
}

function AdminMode({ settings, refreshSettings }) {
  const initialExportDate = new Date(Date.now() - new Date().getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 10);
  const [loginForm, setLoginForm] = useState({ admin_id: "AdminID", password: "admin@123" });
  const [studentForm, setStudentForm] = useState({ roll_no: "", name: "", father_name: "", address: "" });
  const [credentialsForm, setCredentialsForm] = useState({
    current_password: "",
    new_admin_id: settings.admin_id,
    new_password: ""
  });
  const [windowForm, setWindowForm] = useState({
    attendance_start: settings.attendance_start,
    attendance_end: settings.attendance_end,
    late_grace_minutes: settings.late_grace_minutes
  });
  const [students, setStudents] = useState([]);
  const [dashboard, setDashboard] = useState(null);
  const [todayRecords, setTodayRecords] = useState([]);
  const [adminMessage, setAdminMessage] = useState("Admin login required.");
  const [capturedPhotos, setCapturedPhotos] = useState([]);
  const [exportDate, setExportDate] = useState(initialExportDate);
  const [isAdmin, setIsAdmin] = useState(Boolean(localStorage.getItem("adminToken")));
  const videoRef = useRef(null);
  const canvasRef = useRef(null);

  useEffect(() => {
    if (!isAdmin) {
      return undefined;
    }
    loadAdminData();
    let stream;
    async function setup() {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: true });
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
      } catch (error) {
        setAdminMessage("Camera access is required for face enrollment.");
      }
    }
    setup();
    return () => {
      if (stream) {
        stream.getTracks().forEach((track) => track.stop());
      }
    };
  }, [isAdmin]);

  useEffect(() => {
    setCredentialsForm((prev) => ({ ...prev, new_admin_id: settings.admin_id }));
    setWindowForm({
      attendance_start: settings.attendance_start,
      attendance_end: settings.attendance_end,
      late_grace_minutes: settings.late_grace_minutes
    });
  }, [settings]);

  async function loadAdminData() {
    try {
      const [studentRows, attendanceRows, dashboardData] = await Promise.all([
        apiRequest("/api/students"),
        apiRequest("/api/attendance/today"),
        apiRequest("/api/dashboard")
      ]);
      setStudents(studentRows);
      setTodayRecords(attendanceRows.records);
      setDashboard(dashboardData);
    } catch (error) {
      setAdminMessage(error.message);
    }
  }

  async function loginAdmin(event) {
    event.preventDefault();
    try {
      const result = await apiRequest("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(loginForm)
      });
      localStorage.setItem("adminToken", result.access_token);
      setIsAdmin(true);
      setAdminMessage("Admin logged in successfully.");
    } catch (error) {
      setAdminMessage(error.message);
    }
  }

  async function captureStudentPhoto() {
    try {
      const blob = await captureFrame(videoRef.current, canvasRef.current);
      setCapturedPhotos((prev) => [...prev, blob].slice(0, 8));
      setAdminMessage("Photo captured. Take front, left, right, and slightly tilted angles.");
    } catch (error) {
      setAdminMessage("Could not capture image.");
    }
  }

  async function enrollStudent(event) {
    event.preventDefault();
    if (capturedPhotos.length < 3) {
      setAdminMessage("Please capture at least 3 photos from different angles.");
      return;
    }

    try {
      const formData = new FormData();
      Object.entries(studentForm).forEach(([key, value]) => formData.append(key, value));
      capturedPhotos.forEach((blob, index) => formData.append("images", blob, `student-${index}.jpg`));
      const result = await apiRequest("/api/students/enroll", {
        method: "POST",
        body: formData
      });
      setAdminMessage(result.message);
      setStudentForm({ roll_no: "", name: "", father_name: "", address: "" });
      setCapturedPhotos([]);
      await loadAdminData();
    } catch (error) {
      setAdminMessage(error.message);
    }
  }

  async function saveWindow(event) {
    event.preventDefault();
    try {
      const result = await apiRequest("/api/settings/attendance-window", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(windowForm)
      });
      setAdminMessage(result.message);
      refreshSettings();
      loadAdminData();
    } catch (error) {
      setAdminMessage(error.message);
    }
  }

  async function saveCredentials(event) {
    event.preventDefault();
    try {
      const result = await apiRequest("/api/settings/change-credentials", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(credentialsForm)
      });
      setAdminMessage(result.message);
      setLoginForm({ admin_id: credentialsForm.new_admin_id, password: credentialsForm.new_password });
      setCredentialsForm((prev) => ({ ...prev, current_password: "", new_password: "" }));
      refreshSettings();
    } catch (error) {
      setAdminMessage(error.message);
    }
  }

  async function deleteStudent(studentId) {
    try {
      await apiRequest(`/api/students/${studentId}`, { method: "DELETE" });
      setAdminMessage("Student deleted successfully.");
      loadAdminData();
    } catch (error) {
      setAdminMessage(error.message);
    }
  }

  async function downloadCsv() {
    try {
      const response = await fetch(`${API_BASE}/api/attendance/export?date=${exportDate}`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("adminToken")}` }
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Could not download CSV");
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `attendance-${exportDate}.csv`;
      link.click();
      URL.revokeObjectURL(url);
      setAdminMessage("Attendance CSV downloaded.");
    } catch (error) {
      setAdminMessage(error.message);
    }
  }

  function logout() {
    localStorage.removeItem("adminToken");
    setIsAdmin(false);
    setStudents([]);
    setTodayRecords([]);
    setDashboard(null);
    setAdminMessage("Admin logged out.");
  }

  if (!isAdmin) {
    return (
      <section className="panel">
        <div className="panel-head">
          <div>
            <h2>Admin Mode</h2>
            <p>Use the admin credentials to manage students, time windows, and downloads.</p>
          </div>
        </div>
        <form className="form-grid" onSubmit={loginAdmin}>
          <label>
            <span>Admin ID</span>
            <input value={loginForm.admin_id} onChange={(e) => setLoginForm({ ...loginForm, admin_id: e.target.value })} />
          </label>
          <label>
            <span>Password</span>
            <input type="password" value={loginForm.password} onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })} />
          </label>
          <button className="primary-button" type="submit">Login</button>
        </form>
        <p className="helper-text">{adminMessage}</p>
      </section>
    );
  }

  return (
    <section className="panel admin-stack">
      <div className="panel-head">
        <div>
          <h2>Admin Mode</h2>
          <p>Enroll students, control the attendance window, and export records.</p>
        </div>
        <div className="row">
          <input type="date" value={exportDate} onChange={(e) => setExportDate(e.target.value)} />
          <button className="secondary-button" onClick={downloadCsv}>Download CSV</button>
          <button className="ghost-button" onClick={logout}>Logout</button>
        </div>
      </div>

      {dashboard && (
        <div className="stats-grid">
          <div className="stat-card"><strong>{dashboard.total_students}</strong><span>Total Students</span></div>
          <div className="stat-card"><strong>{dashboard.present_today}</strong><span>Present Today</span></div>
          <div className="stat-card"><strong>{dashboard.late_today}</strong><span>Late Today</span></div>
          <div className="stat-card"><strong>{dashboard.absent_today}</strong><span>Absent Today</span></div>
        </div>
      )}

      <div className="admin-grid">
        <form className="card form-grid" onSubmit={enrollStudent}>
          <div className="card-header">
            <h3>Enroll Student Face</h3>
            <p>Capture multiple angles to improve recognition.</p>
          </div>
          <label><span>Roll No</span><input value={studentForm.roll_no} onChange={(e) => setStudentForm({ ...studentForm, roll_no: e.target.value })} required /></label>
          <label><span>Name</span><input value={studentForm.name} onChange={(e) => setStudentForm({ ...studentForm, name: e.target.value })} required /></label>
          <label><span>Father Name</span><input value={studentForm.father_name} onChange={(e) => setStudentForm({ ...studentForm, father_name: e.target.value })} required /></label>
          <label className="full"><span>Address</span><textarea value={studentForm.address} onChange={(e) => setStudentForm({ ...studentForm, address: e.target.value })} required /></label>
          <VideoCard videoRef={videoRef} started={true} />
          <canvas ref={canvasRef} hidden />
          <div className="row">
            <button type="button" className="secondary-button" onClick={captureStudentPhoto}>Capture Photo</button>
            <span className="helper-text">{capturedPhotos.length} photos captured</span>
          </div>
          <button className="primary-button" type="submit">Save Student</button>
        </form>

        <form className="card form-grid" onSubmit={saveWindow}>
          <div className="card-header">
            <h3>Attendance Settings</h3>
            <p>Only active during the class attendance time period.</p>
          </div>
          <label><span>Start Time</span><input type="time" value={windowForm.attendance_start} onChange={(e) => setWindowForm({ ...windowForm, attendance_start: e.target.value })} required /></label>
          <label><span>End Time</span><input type="time" value={windowForm.attendance_end} onChange={(e) => setWindowForm({ ...windowForm, attendance_end: e.target.value })} required /></label>
          <label><span>Late Grace Minutes</span><input type="number" min="0" max="180" value={windowForm.late_grace_minutes} onChange={(e) => setWindowForm({ ...windowForm, late_grace_minutes: Number(e.target.value) })} required /></label>
          <button className="primary-button" type="submit">Update Attendance Window</button>
        </form>

        <form className="card form-grid" onSubmit={saveCredentials}>
          <div className="card-header">
            <h3>Change Admin Credentials</h3>
            <p>The default login is AdminID / admin@123.</p>
          </div>
          <label><span>Current Password</span><input type="password" value={credentialsForm.current_password} onChange={(e) => setCredentialsForm({ ...credentialsForm, current_password: e.target.value })} required /></label>
          <label><span>New Admin ID</span><input value={credentialsForm.new_admin_id} onChange={(e) => setCredentialsForm({ ...credentialsForm, new_admin_id: e.target.value })} required /></label>
          <label><span>New Password</span><input type="password" value={credentialsForm.new_password} onChange={(e) => setCredentialsForm({ ...credentialsForm, new_password: e.target.value })} required /></label>
          <button className="primary-button" type="submit">Save Credentials</button>
        </form>
      </div>

      <div className="card">
        <div className="card-header">
          <h3>Students</h3>
          <p>Delete support is included for cleanup and re-enrollment.</p>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Roll No</th>
                <th>Name</th>
                <th>Father</th>
                <th>Address</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {students.map((student) => (
                <tr key={student.id}>
                  <td>{student.roll_no}</td>
                  <td>{student.name}</td>
                  <td>{student.father_name}</td>
                  <td>{student.address}</td>
                  <td><button className="ghost-button" onClick={() => deleteStudent(student.id)}>Delete</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h3>Today&apos;s Attendance</h3>
          <p>Daily records update automatically as students mark attendance.</p>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Roll No</th>
                <th>Name</th>
                <th>Father</th>
                <th>Time</th>
                <th>Status</th>
                <th>Confidence</th>
              </tr>
            </thead>
            <tbody>
              {todayRecords.map((record) => (
                <tr key={`${record.roll_no}-${record.attendance_time}`}>
                  <td>{record.roll_no}</td>
                  <td>{record.name}</td>
                  <td>{record.father_name}</td>
                  <td>{record.attendance_time}</td>
                  <td>{record.status}</td>
                  <td>{Math.round(record.confidence * 100)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <p className="helper-text">{adminMessage}</p>
    </section>
  );
}

export default function App() {
  const [mode, setMode] = useState("attendance");
  const [settings, setSettings] = useState({
    admin_id: "AdminID",
    attendance_start: "08:00",
    attendance_end: "09:00",
    late_grace_minutes: 10,
    window_active: false
  });

  async function loadSettings() {
    try {
      const result = await apiRequest("/api/settings");
      setSettings(result);
    } catch (error) {
      console.error(error);
    }
  }

  useEffect(() => {
    loadSettings();
    const timer = setInterval(loadSettings, 15000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Face Recognition Attendance</p>
          <h1>Smart classroom attendance with admin-secured face enrollment.</h1>
          <p className="hero-copy">
            Attendance runs in a fixed class time window, students mark presence by face, and admins manage records and CSV downloads.
          </p>
        </div>
        <div className="hero-card">
          <span>Today&apos;s window</span>
          <strong>{settings.attendance_start} to {settings.attendance_end}</strong>
          <StatusPill active={settings.window_active} />
        </div>
      </header>

      <div className="mode-toggle">
        <button className={mode === "attendance" ? "active" : ""} onClick={() => setMode("attendance")}>
          Attendance Mode
        </button>
        <button className={mode === "admin" ? "active" : ""} onClick={() => setMode("admin")}>
          Admin Mode
        </button>
      </div>

      {mode === "attendance" ? (
        <AttendanceMode settings={settings} />
      ) : (
        <AdminMode settings={settings} refreshSettings={loadSettings} />
      )}
    </div>
  );
}
