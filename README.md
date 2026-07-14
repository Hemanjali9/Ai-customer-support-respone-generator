# AI Customer Support Response Generator Pro

An enterprise-grade, full-stack AI-powered Customer Support Response Platform. Designed to help support agents instantly draft professional, empathetic, and company-policy-compliant customer service responses using Groq's `llama-3.1-8b-instant` LLM. Features automated compliance checks, keyword-based escalations for legal/abuse flags, a manager approval flow, and an administrative analytics dashboard.

---

## Folder Structure

```
AI CUSTOMER SUPPORT RESPONSE GENERATOR PRO
├── .env.example
├── README.md
├── run.py
├── backend/
│   ├── app.py
│   ├── config.py
│   ├── database.py
│   ├── requirements.txt
│   ├── data/
│   │   ├── policies.json
│   │   └── templates.json
│   ├── tests/
│   │   └── verify_cases.py
│   └── utils/
│       ├── ai_service.py
│       └── escalation_checker.py
└── frontend/
    ├── index.html
    ├── css/
    │   └── styles.css
    └── js/
        └── app.js
```

---

## Features

1. **Role-Based Authentication & Workspaces**: Separate interfaces and permissions for **Agents**, **Managers**, and **Administrators** secured with JWT tokens and bcrypt password hashing.
2. **Automated Escalation Checker**: Instantly flags tickets with order values > INR 5000, repeated issues, delay queries > 10 days, missing mandatory Order IDs, or legal/abusive vocabulary, preventing AI execution and routing them straight to manager review.
3. **Groq Llama-3.1 Integration**: Uses low-latency inference on the `llama-3.1-8b-instant` model to draft structured, tone-appropriate, and policy-compliant email responses in milliseconds.
4. **Interactive Policy & Template Engine**: Maps tickets to 10 distinct issue categories, prompting agents with live guidelines and verifying responses against custom quality checklists.
5. **Real-time Password Rules Checker**: Validates registration password complexity interactively (8+ characters, uppercase, lowercase, numbers, special characters) with show/hide eye toggles.
6. **Case Management Modal**: Enables detailed review, custom manager approval notes, copy-to-clipboard actions, raw text downloads, and print-to-PDF formatting.
7. **Premium SaaS UI**: Styled in glassmorphism cards and neon highlight borders on a dark navy theme.
8. **Admin Visualizations**: Integrates dynamic Chart.js canvases detailing cases by category, escalation metrics, monthly volumes, and resolution statistics.

---

## Installation Guide

### Prerequisites
- Python 3.8 or higher
- MongoDB instance (Local Community Server or Atlas Cloud Cluster)
- Groq API Account Token

### Steps
1. Clone the project files to your directory.
2. Open terminal in the root directory:
   ```bash
   pip install -r backend/requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill out your credentials:
   ```bash
   cp .env.example .env
   ```
4. Run the application:
   ```bash
   python run.py
   ```
5. Open your browser and navigate to `http://localhost:5000`.

---

## Environment Variables

| Variable | Description | Example Value |
| :--- | :--- | :--- |
| `PORT` | Local web server port | `5000` |
| `MONGO_URI` | MongoDB Connection URL | `mongodb+srv://user:pass@cluster.mongodb.net/support_generator` |
| `JWT_SECRET` | Secret token signing signature | `f87ef9281a8b30dc8470a1a09d6c` |
| `GROQ_API_KEY` | Groq console developer token | `gsk_m9qN0sL848d7...` |

---

## API Documentation

### Authentication Endpoints
- **`POST /api/auth/register`**: Creates a user profile.
  - *Payload*: `{"name": "...", "email": "...", "role": "Agent/Manager/Admin", "password": "...", "confirm_password": "..."}`
- **`POST /api/auth/login`**: Authenticates credentials and returns a JWT token.
  - *Payload*: `{"email": "...", "password": "..."}`

### Generator Endpoints
- **`POST /api/generate-response`**: Evaluates policy guidelines. If clean, generates an LLM draft; if violated, saves as escalated. (Requires *Agent* Bearer Token).
  - *Payload*: `{"customer_name": "...", "customer_email": "...", "order_id": "...", "category": "...", "complaint": "...", "amount": 0, "repeated_complaint": false}`

### Case Management Endpoints
- **`POST /api/cases/create`**: Saves and submits a manual or edited AI support response. (Requires *Agent* Bearer Token).
- **`GET /api/cases/my`**: Lists cases processed by the logged-in agent. (Requires *Agent* Bearer Token).
- **`GET /api/cases/escalated`**: Returns cases awaiting review. (Requires *Manager* Bearer Token).
- **`PUT /api/cases/approve/<id>`**: Approves case and records notes. (Requires *Manager* Bearer Token).
- **`PUT /api/cases/reject/<id>`**: Rejects case and records explanations. (Requires *Manager* Bearer Token).

### Administration Endpoints
- **`GET /api/admin/users`**: Lists registered profiles. (Requires *Admin* Bearer Token).
- **`PUT /api/admin/users/<id>/role`**: Modifies user role status. (Requires *Admin* Bearer Token).
- **`GET /api/admin/dashboard`**: Compiles analytics aggregations. (Requires *Admin* Bearer Token).

---

## Testing Verification

Run the automated test suite locally:
```bash
python backend/tests/verify_cases.py
```

### Test Case Execution Log

| Test Case | Inputs | Expected Output | Actual Output | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Category Order Delayed** | Delayed query, ORD-123, ₹250 | Standard / Process through AI | Standard / Process through AI | **PASS** |
| **High Refund Amount** | Standard query, ORD-998, ₹6500 | Escalated (High Value) | Escalated (High Value) | **PASS** |
| **Repeated Complaint** | Repeated Flag true, ORD-443, ₹120 | Escalated (Repeated) | Escalated (Repeated) | **PASS** |
| **Missing Order ID** | Wrong Item, Order ID: "", ₹150 | Escalated (Missing ID) | Escalated (Missing ID) | **PASS** |
| **Legal Threat** | "consumer court lawsuit", ORD-889 | Escalated (Legal threat) | Escalated (Legal threat) | **PASS** |
| **Abusive Language** | "useless fraud scam", ORD-554 | Escalated (Inappropriate) | Escalated (Inappropriate) | **PASS** |
| **Refund Delay > 10 Days** | "waiting 14 days", ORD-776, ₹300 | Escalated (Refund Delay) | Escalated (Refund Delay) | **PASS** |
| **General Inquiry (No ID)** | Question, Order ID: "", ₹0 | Standard / Process through AI | Standard / Process through AI | **PASS** |

---

## Deployment Guide

### MongoDB Atlas Setup
1. Create a free cluster on [MongoDB Atlas](https://www.mongodb.com/cloud/atlas).
2. Create a Database User with read/write privileges.
3. Whitelist access from IP addresses `0.0.0.0/0` (all locations) or provide specific environment hosting IPs.
4. Copy the connection URI and define it in your `.env` settings.

### Deploying to Render / Railway
1. Push the repository to GitHub.
2. Link your repository to **Render** or **Railway** web services.
3. Configure settings:
   - **Environment**: Python
   - **Build Command**: `pip install -r backend/requirements.txt`
   - **Start Command**: `gunicorn backend.app:app` or `python run.py` (ensure to expose host `0.0.0.0` and port through environment ports).
4. Add all values (`GROQ_API_KEY`, `MONGO_URI`, `JWT_SECRET`) to the Environment Settings panel.

---

## Team Members
- **Lead System Architect**: AI Integration Specialist
- **Senior UI/UX Engineer**: Glassmorphic Themes Designer
- **Backend Developer**: Flask & Security Coordinator
