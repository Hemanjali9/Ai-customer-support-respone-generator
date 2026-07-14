import os
import jwt
import bcrypt
import datetime
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from backend.config import Config
from backend.database import (
    get_db,
    create_user,
    get_user_by_email,
    get_all_users,
    update_user_role,
    create_case,
    get_case_by_id,
    get_agent_cases,
    get_escalated_cases,
    get_all_cases,
    update_case_status,
    save_case_response,
    log_activity,
    add_notification,
    get_notifications,
    get_admin_dashboard_stats,
    get_manager_dashboard_stats,
    get_agent_dashboard_stats
)
from backend.utils.escalation_checker import check_escalation
from backend.utils.ai_service import generate_support_response

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app) # Enable CORS for all routes (aids development)

# Verify configurations
config_errors = Config.validate()
if config_errors:
    print("WARNING: Configuration errors detected:")
    for err in config_errors:
        print(f"  - {err}")

# JWT Decorator
def token_required(allowed_roles=None):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            token = None
            if "Authorization" in request.headers:
                auth_header = request.headers["Authorization"]
                if auth_header.startswith("Bearer "):
                    token = auth_header.split(" ")[1]
            
            if not token:
                return jsonify({"error": "Access denied. Authentication token is missing."}), 401
                
            try:
                data = jwt.decode(token, Config.JWT_SECRET, algorithms=["HS256"])
                # Fetch user details
                current_user = get_user_by_email(data["email"])
                if not current_user:
                    return jsonify({"error": "User no longer exists."}), 401
                
                # Check authorization roles
                if allowed_roles and current_user["role"] not in allowed_roles:
                    return jsonify({"error": f"Access forbidden. Required role: {allowed_roles}"}), 403
                    
                # Inject current_user
                return f(current_user, *args, **kwargs)
                
            except jwt.ExpiredSignatureError:
                return jsonify({"error": "Session expired. Please log in again."}), 401
            except jwt.InvalidTokenError:
                return jsonify({"error": "Invalid token. Please log in again."}), 401
            except Exception as e:
                return jsonify({"error": f"Authentication failed: {str(e)}"}), 401
        return decorated
    return decorator

# --- Static File Serving ---

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    # Fallback to serving files from frontend folder
    return send_from_directory(app.static_folder, path)

# --- Authentication Endpoints ---

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password")
    confirm_password = data.get("confirm_password")
    role = data.get("role", "Agent").strip() # Default Agent

    if not name or not email or not password or not role:
        return jsonify({"error": "All fields are required."}), 400

    if password != confirm_password:
        return jsonify({"error": "Passwords do not match."}), 400

    # Role validation
    if role not in ["Agent", "Manager", "Admin"]:
        return jsonify({"error": "Invalid role specified."}), 400

    # Password rules validation
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters long."}), 400
    if not any(c.isupper() for c in password):
        return jsonify({"error": "Password must contain at least 1 uppercase letter."}), 400
    if not any(c.islower() for c in password):
        return jsonify({"error": "Password must contain at least 1 lowercase letter."}), 400
    if not any(c.isdigit() for c in password):
        return jsonify({"error": "Password must contain at least 1 number."}), 400
    # Special character rule
    special_chars = re_special = r"[!@#$%^&*(),.?\":{}|<>]"
    import re
    if not re.search(re_special, password):
        return jsonify({"error": "Password must contain at least 1 special character."}), 400

    try:
        # Check if user already exists
        existing = get_user_by_email(email)
        if existing:
            return jsonify({"error": "User with this email already exists."}), 400

        # Hash password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Save to database
        user = create_user(name, email, hashed_password, role)
        
        # Log activity
        log_activity(email, role, "REGISTER", f"User registered successfully as {role}")
        
        return jsonify({
            "message": "User registered successfully.",
            "user": {
                "name": user["name"],
                "email": user["email"],
                "role": user["role"]
            }
        }), 201
        
    except Exception as e:
        return jsonify({"error": f"Registration failed: {str(e)}"}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    try:
        user = get_user_by_email(email)
        if not user:
            return jsonify({"error": "Invalid email or password."}), 401

        # Check password
        if not bcrypt.checkpw(password.encode('utf-8'), user["password"].encode('utf-8')):
            return jsonify({"error": "Invalid email or password."}), 401

        # Generate JWT Token
        payload = {
            "user_id": user["_id"],
            "email": user["email"],
            "name": user["name"],
            "role": user["role"],
            "exp": datetime.datetime.utcnow() + datetime.timedelta(days=1)
        }
        token = jwt.encode(payload, Config.JWT_SECRET, algorithm="HS256")
        if isinstance(token, bytes):
            token = token.decode('utf-8')

        log_activity(user["email"], user["role"], "LOGIN", "User logged in successfully")

        return jsonify({
            "message": "Login successful.",
            "token": token,
            "user": {
                "name": user["name"],
                "email": user["email"],
                "role": user["role"]
            }
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Login failed: {str(e)}"}), 500

# --- Response & Escalation Endpoints ---

@app.route('/api/generate-response', methods=['POST'])
@token_required(allowed_roles=["Agent"])
def generate_response(current_user):
    data = request.get_json() or {}
    
    # Pre-validate fields
    customer_name = data.get("customer_name", "").strip()
    customer_email = data.get("customer_email", "").strip()
    order_id = data.get("order_id", "").strip()
    category = data.get("category", "").strip()
    complaint = data.get("complaint", "").strip()
    amount_str = data.get("amount", "0")
    repeated = data.get("repeated_complaint", False)
    
    if not customer_name or not customer_email or not category or not complaint:
        return jsonify({"error": "Customer Name, Email, Category, and Complaint details are required."}), 400

    # Parse amount
    try:
        amount = float(amount_str) if amount_str else 0.0
    except ValueError:
        return jsonify({"error": "Invalid order amount. Must be a number."}), 400

    # Struct payload for checkers
    case_payload = {
        "customer_name": customer_name,
        "customer_email": customer_email,
        "order_id": order_id,
        "category": category,
        "complaint": complaint,
        "amount": amount,
        "repeated_complaint": repeated,
        "created_by": current_user["email"]
    }

    # 1. Run Escalation Checker
    is_escalated, reason = check_escalation(case_payload)

    if is_escalated:
        # Save directly as Escalated case (no LLM call)
        case_payload["escalation_status"] = True
        case_payload["escalation_reason"] = reason
        case_payload["status"] = "Escalated"
        case_payload["generated_response"] = ""
        
        saved_case = create_case(case_payload)
        
        # Log and Notify
        log_activity(current_user["email"], current_user["role"], "CASE_ESCALATED", f"Case {saved_case['_id']} auto-escalated: {reason}")
        add_notification("Manager", "Action Required: Case Escalated", f"Order {order_id} escalated for: {reason}", saved_case["_id"])
        
        return jsonify({
            "escalated": True,
            "reason": reason,
            "status": "Escalated",
            "case": saved_case,
            "message": "Needs Manager Review. This case was automatically escalated due to company policies."
        }), 200

    # 2. Call Groq API
    try:
        ai_response = generate_support_response(case_payload)
        
        # Log activity
        log_activity(current_user["email"], current_user["role"], "AI_RESPONSE_GENERATED", f"AI response generated for category: {category}")
        
        return jsonify({
            "escalated": False,
            "status": "Generated",
            "response": ai_response,
            "message": "Response generated successfully."
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"AI Generation failed: {str(e)}"}), 500

# --- Case Endpoints ---

@app.route('/api/cases/create', methods=['POST'])
@token_required(allowed_roles=["Agent"])
def save_agent_case(current_user):
    data = request.get_json() or {}
    
    customer_name = data.get("customer_name", "").strip()
    customer_email = data.get("customer_email", "").strip()
    order_id = data.get("order_id", "").strip()
    category = data.get("category", "").strip()
    complaint = data.get("complaint", "").strip()
    amount_str = data.get("amount", "0")
    generated_response = data.get("generated_response", "").strip()
    escalation_status = data.get("escalation_status", False)
    escalation_reason = data.get("escalation_reason", "").strip()
    
    if not customer_name or not customer_email or not category or not complaint:
        return jsonify({"error": "Customer Name, Email, Category, and Complaint details are required."}), 400

    try:
        amount = float(amount_str) if amount_str else 0.0
    except ValueError:
        return jsonify({"error": "Invalid order amount."}), 400

    # Save case
    case_payload = {
        "customer_name": customer_name,
        "customer_email": customer_email,
        "order_id": order_id,
        "category": category,
        "complaint": complaint,
        "amount": amount,
        "generated_response": generated_response,
        "escalation_status": escalation_status,
        "escalation_reason": escalation_reason,
        "status": "Pending", # Submitting for review
        "created_by": current_user["email"]
    }
    
    try:
        saved_case = create_case(case_payload)
        
        log_activity(current_user["email"], current_user["role"], "CASE_SAVED", f"Case {saved_case['_id']} saved as Pending")
        add_notification("Manager", "Pending Review", f"Agent {current_user['name']} submitted a case for Order {order_id} approval.", saved_case["_id"])
        
        return jsonify({
            "message": "Case submitted for Manager review successfully.",
            "case": saved_case
        }), 201
    except Exception as e:
        return jsonify({"error": f"Failed to save case: {str(e)}"}), 500

@app.route('/api/cases/my', methods=['GET'])
@token_required(allowed_roles=["Agent"])
def get_my_cases(current_user):
    try:
        cases = get_agent_cases(current_user["email"])
        stats = get_agent_dashboard_stats(current_user["email"])
        notifications = get_notifications("Agent")
        return jsonify({
            "cases": cases,
            "stats": stats,
            "notifications": notifications
        }), 200
    except Exception as e:
        return jsonify({"error": f"Failed to fetch cases: {str(e)}"}), 500

@app.route('/api/cases/escalated', methods=['GET'])
@token_required(allowed_roles=["Manager"])
def get_escalated(current_user):
    try:
        cases = get_escalated_cases()
        stats = get_manager_dashboard_stats()
        notifications = get_notifications("Manager")
        return jsonify({
            "cases": cases,
            "stats": stats,
            "notifications": notifications
        }), 200
    except Exception as e:
        return jsonify({"error": f"Failed to fetch cases: {str(e)}"}), 500

@app.route('/api/cases/approve/<id>', methods=['PUT'])
@token_required(allowed_roles=["Manager"])
def approve_case(current_user, id):
    data = request.get_json() or {}
    manager_note = data.get("manager_note", "").strip()
    
    try:
        case = get_case_by_id(id)
        if not case:
            return jsonify({"error": "Case not found."}), 404
            
        success = update_case_status(id, "Approved", manager_note)
        if success:
            log_activity(current_user["email"], current_user["role"], "CASE_APPROVED", f"Approved case {id}")
            # Notify agent who created it
            add_notification("Agent", "Case Approved", f"Your case for Order {case['order_id']} has been approved.", id)
            return jsonify({"message": "Case approved successfully."}), 200
        else:
            return jsonify({"error": "Failed to update case status."}), 500
    except Exception as e:
        return jsonify({"error": f"Failed to approve case: {str(e)}"}), 500

@app.route('/api/cases/reject/<id>', methods=['PUT'])
@token_required(allowed_roles=["Manager"])
def reject_case(current_user, id):
    data = request.get_json() or {}
    manager_note = data.get("manager_note", "").strip()
    
    if not manager_note:
        return jsonify({"error": "Manager note is required to reject a case."}), 400
        
    try:
        case = get_case_by_id(id)
        if not case:
            return jsonify({"error": "Case not found."}), 404
            
        success = update_case_status(id, "Rejected", manager_note)
        if success:
            log_activity(current_user["email"], current_user["role"], "CASE_REJECTED", f"Rejected case {id}")
            # Notify agent
            add_notification("Agent", "Case Rejected", f"Case for Order {case['order_id']} was rejected: {manager_note}", id)
            return jsonify({"message": "Case rejected successfully."}), 200
        else:
            return jsonify({"error": "Failed to update case status."}), 500
    except Exception as e:
        return jsonify({"error": f"Failed to reject case: {str(e)}"}), 500

# --- Admin Endpoints ---

@app.route('/api/admin/users', methods=['GET'])
@token_required(allowed_roles=["Admin"])
def get_users(current_user):
    try:
        users = get_all_users()
        return jsonify({"users": users}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to fetch users: {str(e)}"}), 500

@app.route('/api/admin/users/<id>/role', methods=['PUT'])
@token_required(allowed_roles=["Admin"])
def update_role(current_user, id):
    data = request.get_json() or {}
    new_role = data.get("role")
    
    if new_role not in ["Agent", "Manager", "Admin"]:
        return jsonify({"error": "Invalid role value."}), 400
        
    try:
        success = update_user_role(id, new_role)
        if success:
            log_activity(current_user["email"], current_user["role"], "USER_ROLE_UPDATED", f"Updated user {id} role to {new_role}")
            return jsonify({"message": "User role updated successfully."}), 200
        else:
            return jsonify({"error": "Failed to update user role."}), 500
    except Exception as e:
        return jsonify({"error": f"Failed to update role: {str(e)}"}), 500

@app.route('/api/admin/dashboard', methods=['GET'])
@token_required(allowed_roles=["Admin"])
def get_admin_dashboard(current_user):
    try:
        stats = get_admin_dashboard_stats()
        cases = get_all_cases()
        notifications = get_notifications("Admin")
        return jsonify({
            "stats": stats,
            "cases": cases,
            "notifications": notifications
        }), 200
    except Exception as e:
        return jsonify({"error": f"Failed to fetch admin dashboard: {str(e)}"}), 500

if __name__ == '__main__':
    # Initialize DB connection on startup
    try:
        get_db()
    except Exception as e:
        print(f"CRITICAL: Failed to connect to database. Make sure MongoDB is running and MONGO_URI is set. Details: {e}")
        
    port = Config.PORT
    print(f"Starting server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=True)
