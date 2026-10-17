# Quotex Trading Journal & P&L Analytics Web Application

A secure, mobile-responsive trading journal and performance analytics web application built specifically for **Quotex** binary options and OTC traders. Directly inspired by professional trading dashboards (LegendJournal UI), featuring password protection, dark-mode glassmorphism, responsive charts, interactive calendar heatmaps, in-app trade editing, and stored file management.

---

## 🌟 What's New in v2.0 (Full Web App Refactor)

1. 🔐 **Authentication & Remote Security**:
   - Secure login screen with password visibility toggle.
   - All dashboard views, file uploads, and API endpoints are protected behind secure session authentication.
   - Easily configurable credentials via `.env` file with secure password hash support (`werkzeug.security`).
   - Logout button in both the top navigation bar and sidebar profile card.

2. 📱 **Mobile & Tablet Responsive UI**:
   - Slide-out mobile navigation drawer with backdrop overlay and hamburger menu button.
   - Touch-optimized buttons, adaptive calendar heatmaps, and flexible cards.
   - Direct remote access from your phone or tablet on your local WiFi network (`http://<YOUR_LOCAL_IP>:8000`).

3. ✏️ **Direct In-Dashboard Data Editing**:
   - View, edit, and update any recorded trade directly from the **Trade History** table using the ✏️ **Edit** button.
   - In-app modal allows modifying date/time, pair/asset, direction (CALL/PUT), result (WIN/LOSS/REFUND), investment, payout %, and profit with instant recalculation.

4. 📁 **Stored Files & Upload History Manager**:
   - Uploaded CSV files are physically saved to the server's `uploads/` folder and indexed in SQLite.
   - View all past file uploads, file size, imported trade count, and upload timestamp.
   - One-click **⬇️ Download** of original CSV files or **🗑️ Delete** from disk and database.

5. 🚀 **Production Deployment Ready**:
   - Server binds to `0.0.0.0` and respects dynamic `PORT` environment variables (defaulting to `8000`).
   - Includes production-ready `requirements.txt` and `Procfile` for 1-click cloud deployment on **Render**, **Railway**, or **Heroku**.

---

## 🔑 Default Login Credentials

| Username | Password |
| :--- | :--- |
| `skpaltrader` | `success*` |

> [!TIP]
> You can easily change your credentials at any time by editing the `.env` file in the root directory:
> ```ini
> ADMIN_USERNAME=skpaltrader
> ADMIN_PASSWORD=success*
> ```

---

## 🚀 Running Locally

### Option 1: One-Click Startup (Windows)
Double-click:
```bat
start_server.bat
```
This automatically ensures dependencies are installed, launches your default web browser, and starts the server on port `8000`.

### Option 2: Running via Command Line
```powershell
cd D:\QUOTEX
python app.py
```

Open your browser and navigate to:
```
http://localhost:8000
```

---

## 📱 Accessing from Your Phone or Tablet (Local Network)

1. Make sure your phone is connected to the same Wi-Fi network as your computer.
2. Find your computer's local IP address (or use the one displayed in the terminal startup banner, e.g. `http://192.168.0.110:8000`).
3. Open your mobile browser (Safari, Chrome) and visit:
   ```
   http://192.168.0.110:8000
   ```
4. Enter your login credentials (`skpaltrader` / `success*`).
5. You can tap **Add to Home Screen** on your phone to install it like a native app!

---

## ☁️ Deploying to the Cloud (Free 24/7 Remote Access)

You can host this project on free cloud platforms such as **Render** or **Railway** so you can access it from anywhere in the world without keeping your PC running:

### Deploy to Render:
1. Push this project folder to your GitHub repository.
2. Sign up / Log in to [Render.com](https://render.com).
3. Click **New +** -> **Web Service**.
4. Connect your GitHub repository.
5. Set:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
6. Under **Environment Variables**, add:
   - `ADMIN_USERNAME`: `skpaltrader` (or your chosen username)
   - `ADMIN_PASSWORD`: `success*` (or your chosen password)
   - `SECRET_KEY`: (any long random string)
7. Click **Create Web Service**. Render will generate a public HTTPS URL (e.g., `https://quotex-journal.onrender.com`).

---

## 📂 Project Architecture

```
d:\QUOTEX\
│
├── .env                 # Environment secrets (Username, Password, Secret Key, Port)
├── .env.example         # Template configuration
├── config.py            # Configuration loader
├── app.py               # Flask application with session auth and REST API
├── database.py          # SQLite database schema, analytics queries, file & trade CRUD
├── csv_parser.py        # Flexible Quotex CSV parser with regex date & column normalization
├── sample_data.py       # Realistic 320-trade generator
├── requirements.txt     # Python dependencies (Flask, gunicorn, python-dotenv, etc.)
├── Procfile             # Process file for cloud deployments
├── start_server.bat     # Windows 1-click launcher script
│
├── templates/
│   ├── login.html       # Responsive glassmorphism login portal
│   └── index.html       # Trading dashboard with responsive drawer, modals, & tables
│
├── static/
│   ├── css/
│   │   └── style.css    # Quotex dark-mode theme, mobile media queries, buttons & cards
│   └── js/
│       └── app.js       # Heatmaps, equity curve, edit trade modal, file manager logic
│
└── uploads/             # Server storage folder for uploaded CSV files
```
