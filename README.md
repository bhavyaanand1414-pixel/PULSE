# PULSE: Intelligent API Anomaly Detection & Monitoring Platform

PULSE is a full-stack, local-first API observability platform designed to monitor API endpoints, collect performance metrics, and automatically detect unusual behavior using both Statistical (Z-Score) and Machine Learning (Isolation Forest) models.

## 🚀 Key Features

- **Real-Time Monitoring**: Tracks API response times, error rates, and traffic volume.
- **Dual-Engine Anomaly Detection**:
  - **Statistical (Z-Score)**: Analyzes single metrics to find extreme deviations from historical baselines.
  - **Machine Learning (Isolation Forest)**: Analyzes multiple metrics simultaneously to find complex, multi-dimensional anomalies (e.g., a moderate latency spike combined with an unusual traffic drop).
- **Incident Management**: Automatically groups anomalies into trackable incidents with an `OPEN → INVESTIGATING → RESOLVED` lifecycle.
- **Modern Dashboard**: A premium, dark-themed React dashboard built with Vite and Recharts for beautiful data visualization.
- **100% Local & Free**: Uses no paid third-party APIs or external LLMs. Runs completely on your local machine using SQLite/PostgreSQL, FastAPI, and scikit-learn.

---

## 🏗️ Architecture

PULSE uses a modern, decoupled architecture:

### 1. Backend (Python / FastAPI)
- **Framework**: FastAPI for high-performance, asynchronous REST APIs.
- **Database**: SQLAlchemy ORM for database interactions.
- **Machine Learning**: `scikit-learn` and `pandas` for the Isolation Forest engine, `numpy` for the Z-score engine.
- **Data Validation**: Pydantic schemas enforce strict data contracts for all API inputs and outputs.

### 2. Frontend (React / Vite)
- **Framework**: React with Vite for lightning-fast HMR and building.
- **Styling**: Custom vanilla CSS design system (glassmorphism, dark mode, CSS variables).
- **Visualization**: `recharts` for responsive, animated SVGs (Area, Line, and Bar charts).

---

## 📂 Database Schema

1. **Endpoints**: The APIs being monitored.
2. **Metrics**: Raw time-series data (latency, status codes, traffic volume).
3. **Anomalies**: Unusual metric observations flagged by the detection engines.
4. **Incidents**: Trackable issues created from anomalies.

*Relationships*: An Endpoint has many Metrics, Anomalies, and Incidents.

---

## 🛠️ How to Run Locally

### 1. Start the Backend
```bash
cd backend
# Activate your virtual environment
source venv/bin/activate
# Install requirements if you haven't already
pip install fastapi uvicorn sqlalchemy pydantic numpy pandas scikit-learn psycopg2-binary
# Run the FastAPI server
uvicorn main:app --reload --port 8000
```
*The backend API will be available at `http://localhost:8000`*

### 2. Start the Frontend
```bash
cd frontend
# Install dependencies
npm install
# Start the Vite development server
npm run dev
```
*The React dashboard will be available at `http://localhost:5173`*

### 3. Generate Demo Data
If your database is empty, you can populate it with 7 days of realistic API traffic (including injected anomalies):
```bash
cd backend
source venv/bin/activate
python generate_demo_data.py
```

---

## 🎓 Interview Prep Guide (For B.Tech Students)

If asked about this project in an interview, focus on these key talking points:

1. **Why did you build this?**
   "I wanted to build a practical DevOps/SRE tool. API monitoring is critical for modern microservices, and I wanted to explore how machine learning can automate the detection of system degradation before customers complain."

2. **Why Isolation Forest?**
   "I started with a simple Z-score approach, which is great for finding single-metric spikes (e.g., latency suddenly goes to 5 seconds). But I realized that system failures are often multi-dimensional. Isolation Forest is an unsupervised ML algorithm that works perfectly here—it isolates data points by randomly splitting features. Anomalies need fewer splits to be isolated. This allows PULSE to detect when the *combination* of latency, traffic, and error rates is unusual, even if no single metric crosses a strict threshold."

3. **Why FastAPI and React?**
   "FastAPI is modern, fast, and uses Python type hints (Pydantic) which caught a lot of bugs during development and automatically generated my API docs. I used React with Vite for the frontend because I wanted a highly responsive, component-driven dashboard, and Vite provides a much faster developer experience than Create React App."

4. **How did you handle the database?**
   "I used SQLAlchemy ORM to strictly decouple my Python code from raw SQL. I structured it relationally: Endpoints -> Metrics -> Anomalies. I also used Pydantic schemas to validate data before it ever touches the database, which prevented integrity errors (like ensuring `is_error` is always computed correctly from the HTTP status code)."

5. **Future Improvements?**
   "If I had more time, I would replace the SQLite/local DB with a time-series database like InfluxDB or Prometheus, which are better suited for massive volumes of metric data. I would also add real-time WebSocket streaming to the React dashboard instead of relying on HTTP polling."

---

## 🚀 Deployment

PULSE is designed to be deployed as a single-instance application (due to its in-memory APScheduler). 

### Required Environment Variables

When deploying, you must configure the following environment variables:

**Backend Environment Variables:**
- `DATABASE_URL`: The connection string to your PostgreSQL database (e.g., `postgresql+psycopg://user:password@host:port/dbname`).
- `ALLOWED_ORIGINS`: A comma-separated list of origins allowed to make API requests to the backend. In production, this should be the URL where your frontend is hosted (e.g., `https://pulse.my-domain.com`).

**Frontend Environment Variables:**
- `VITE_API_URL`: The public URL of your deployed backend API (e.g., `https://pulse-api.my-domain.com`). This ensures the frontend correctly routes API calls to the production server instead of localhost.

### Startup Command
For platforms using a `Procfile`, PULSE is configured to start with a single Uvicorn worker bound to the platform's port:
`web: cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1`
