import os
import json
import uuid
import datetime
import logging
from pymongo import MongoClient, ASCENDING
from bson import ObjectId
from backend.config import Config

logger = logging.getLogger("db_service")
logging.basicConfig(level=logging.INFO)

db = None
client = None
use_json_fallback = False
db_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "db")

def get_db():
    global db, client, use_json_fallback
    if db is not None:
        return db
    if use_json_fallback:
        return None
        
    try:
        logger.info(f"Connecting to MongoDB with URI: {Config.MONGO_URI}")
        client = MongoClient(Config.MONGO_URI, serverSelectionTimeoutMS=2000)
        client.admin.command('ping')
        db = client.get_database()
        logger.info("Successfully connected to MongoDB.")
        setup_indexes(db)
        return db
    except Exception as e:
        logger.warning(f"MongoDB connection failed: {e}")
        logger.warning("TRANSITION: Falling back to local persistent JSON file-based database for offline support.")
        use_json_fallback = True
        ensure_json_db()
        return None

def setup_indexes(database):
    try:
        database.users.create_index([("email", ASCENDING)], unique=True)
        database.cases.create_index([("created_by", ASCENDING)])
        database.cases.create_index([("status", ASCENDING)])
        database.cases.create_index([("order_id", ASCENDING)])
        logger.info("Database indexes configured successfully.")
    except Exception as e:
        logger.error(f"Failed to create indexes: {e}")

# --- JSON File Fallback Helpers ---

def ensure_json_db():
    if not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    
    files = ["users.json", "cases.json", "notifications.json", "activity_logs.json"]
    for f in files:
        path = os.path.join(db_dir, f)
        if not os.path.exists(path):
            with open(path, "w") as out:
                json.dump([], out)

def read_json_file(filename):
    ensure_json_db()
    path = os.path.join(db_dir, filename)
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading local file database {filename}: {e}")
        return []

def write_json_file(filename, data):
    ensure_json_db()
    path = os.path.join(db_dir, filename)
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error writing local file database {filename}: {e}")

# --- User Operations ---

def create_user(name, email, password_hash, role):
    get_db()
    
    user = {
        "name": name,
        "email": email.lower().strip(),
        "password": password_hash,
        "role": role,
        "created_at": datetime.datetime.utcnow()
    }
    
    if use_json_fallback:
        users = read_json_file("users.json")
        user["_id"] = str(uuid.uuid4())
        user["created_at"] = user["created_at"].isoformat()
        users.append(user)
        write_json_file("users.json", users)
        return user
    else:
        database = get_db()
        result = database.users.insert_one(user)
        user["_id"] = str(result.inserted_id)
        return user

def get_user_by_email(email):
    get_db()
    normalized_email = email.lower().strip()
    
    if use_json_fallback:
        users = read_json_file("users.json")
        for u in users:
            if u["email"] == normalized_email:
                return u
        return None
    else:
        database = get_db()
        user = database.users.find_one({"email": normalized_email})
        if user:
            user["_id"] = str(user["_id"])
        return user

def get_user_by_id(user_id):
    get_db()
    
    if use_json_fallback:
        users = read_json_file("users.json")
        for u in users:
            if u["_id"] == user_id:
                return u
        return None
    else:
        database = get_db()
        try:
            user = database.users.find_one({"_id": ObjectId(user_id)})
            if user:
                user["_id"] = str(user["_id"])
            return user
        except Exception:
            return None

def get_all_users():
    get_db()
    
    if use_json_fallback:
        users = read_json_file("users.json")
        # Strip passwords
        cleaned = []
        for u in users:
            uc = u.copy()
            if "password" in uc:
                del uc["password"]
            cleaned.append(uc)
        return cleaned
    else:
        database = get_db()
        users = list(database.users.find({}, {"password": 0}))
        for u in users:
            u["_id"] = str(u["_id"])
            if "created_at" in u and isinstance(u["created_at"], datetime.datetime):
                u["created_at"] = u["created_at"].isoformat()
        return users

def update_user_role(user_id, new_role):
    get_db()
    
    if use_json_fallback:
        users = read_json_file("users.json")
        updated = False
        for u in users:
            if u["_id"] == user_id:
                u["role"] = new_role
                updated = True
                break
        if updated:
            write_json_file("users.json", users)
        return updated
    else:
        database = get_db()
        try:
            result = database.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"role": new_role}}
            )
            return result.modified_count > 0
        except Exception:
            return False

# --- Case Operations ---

def create_case(case_data):
    get_db()
    
    case = {
        "customer_name": case_data.get("customer_name"),
        "customer_email": case_data.get("customer_email"),
        "order_id": case_data.get("order_id"),
        "category": case_data.get("category"),
        "complaint": case_data.get("complaint"),
        "amount": float(case_data.get("amount", 0)),
        "generated_response": case_data.get("generated_response", ""),
        "escalation_status": case_data.get("escalation_status", False),
        "escalation_reason": case_data.get("escalation_reason", ""),
        "manager_note": case_data.get("manager_note", ""),
        "status": case_data.get("status", "Pending"),
        "created_by": case_data.get("created_by"),
        "created_date": datetime.datetime.utcnow()
    }
    
    if use_json_fallback:
        cases = read_json_file("cases.json")
        case["_id"] = str(uuid.uuid4())
        case["created_date"] = case["created_date"].isoformat()
        cases.append(case)
        write_json_file("cases.json", cases)
        return case
    else:
        database = get_db()
        result = database.cases.insert_one(case)
        case["_id"] = str(result.inserted_id)
        case["created_date"] = case["created_date"].isoformat()
        return case

def get_case_by_id(case_id):
    get_db()
    
    if use_json_fallback:
        cases = read_json_file("cases.json")
        for c in cases:
            if c["_id"] == case_id:
                return c
        return None
    else:
        database = get_db()
        try:
            c = database.cases.find_one({"_id": ObjectId(case_id)})
            if c:
                c["_id"] = str(c["_id"])
                if "created_date" in c and isinstance(c["created_date"], datetime.datetime):
                    c["created_date"] = c["created_date"].isoformat()
            return c
        except Exception:
            return None

def get_agent_cases(agent_email):
    get_db()
    
    if use_json_fallback:
        cases = read_json_file("cases.json")
        agent_cases = [c for c in cases if c.get("created_by") == agent_email]
        # Sort by date descending
        agent_cases.sort(key=lambda x: x.get("created_date", ""), reverse=True)
        return agent_cases
    else:
        database = get_db()
        cases = list(database.cases.find({"created_by": agent_email}).sort("created_date", -1))
        for c in cases:
            c["_id"] = str(c["_id"])
            if "created_date" in c and isinstance(c["created_date"], datetime.datetime):
                c["created_date"] = c["created_date"].isoformat()
        return cases

def get_escalated_cases():
    get_db()
    
    if use_json_fallback:
        cases = read_json_file("cases.json")
        escalated = [c for c in cases if c.get("status") in ["Escalated", "Pending"]]
        escalated.sort(key=lambda x: x.get("created_date", ""), reverse=True)
        return escalated
    else:
        database = get_db()
        cases = list(database.cases.find({"status": {"$in": ["Escalated", "Pending"]}}).sort("created_date", -1))
        for c in cases:
            c["_id"] = str(c["_id"])
            if "created_date" in c and isinstance(c["created_date"], datetime.datetime):
                c["created_date"] = c["created_date"].isoformat()
        return cases

def get_all_cases():
    get_db()
    
    if use_json_fallback:
        cases = read_json_file("cases.json")
        cases.sort(key=lambda x: x.get("created_date", ""), reverse=True)
        return cases
    else:
        database = get_db()
        cases = list(database.cases.find().sort("created_date", -1))
        for c in cases:
            c["_id"] = str(c["_id"])
            if "created_date" in c and isinstance(c["created_date"], datetime.datetime):
                c["created_date"] = c["created_date"].isoformat()
        return cases

def update_case_status(case_id, status, manager_note=None):
    get_db()
    
    if use_json_fallback:
        cases = read_json_file("cases.json")
        updated = False
        for c in cases:
            if c["_id"] == case_id:
                c["status"] = status
                if manager_note is not None:
                    c["manager_note"] = manager_note
                updated = True
                break
        if updated:
            write_json_file("cases.json", cases)
        return updated
    else:
        database = get_db()
        try:
            update_doc = {"status": status}
            if manager_note is not None:
                update_doc["manager_note"] = manager_note
                
            result = database.cases.update_one(
                {"_id": ObjectId(case_id)},
                {"$set": update_doc}
            )
            return result.modified_count > 0
        except Exception:
            return False

def save_case_response(case_id, response_text):
    get_db()
    
    if use_json_fallback:
        cases = read_json_file("cases.json")
        updated = False
        for c in cases:
            if c["_id"] == case_id:
                c["generated_response"] = response_text
                updated = True
                break
        if updated:
            write_json_file("cases.json", cases)
        return updated
    else:
        database = get_db()
        try:
            result = database.cases.update_one(
                {"_id": ObjectId(case_id)},
                {"$set": {"generated_response": response_text}}
            )
            return result.modified_count > 0
        except Exception:
            return False

# --- Logs & Notifications ---

def log_activity(user_email, role, action, details):
    get_db()
    
    log = {
        "user_email": user_email,
        "role": role,
        "action": action,
        "details": details,
        "timestamp": datetime.datetime.utcnow()
    }
    
    if use_json_fallback:
        logs = read_json_file("activity_logs.json")
        log["_id"] = str(uuid.uuid4())
        log["timestamp"] = log["timestamp"].isoformat()
        logs.append(log)
        write_json_file("activity_logs.json", logs)
    else:
        database = get_db()
        database.activity_logs.insert_one(log)

def add_notification(recipient_role, title, message, case_id=None):
    get_db()
    
    notification = {
        "recipient_role": recipient_role,
        "title": title,
        "message": message,
        "case_id": case_id,
        "read": False,
        "timestamp": datetime.datetime.utcnow()
    }
    
    if use_json_fallback:
        notifs = read_json_file("notifications.json")
        notification["_id"] = str(uuid.uuid4())
        notification["timestamp"] = notification["timestamp"].isoformat()
        notifs.append(notification)
        write_json_file("notifications.json", notifs)
    else:
        database = get_db()
        database.notifications.insert_one(notification)

def get_notifications(role):
    get_db()
    
    if use_json_fallback:
        notifs = read_json_file("notifications.json")
        role_notifs = [n for n in notifs if n.get("recipient_role") == role]
        # Sort and limit
        role_notifs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return role_notifs[:20]
    else:
        database = get_db()
        notifications = list(database.notifications.find({"recipient_role": role}).sort("timestamp", -1).limit(20))
        for n in notifications:
            n["_id"] = str(n["_id"])
            n["timestamp"] = n["timestamp"].isoformat()
        return notifications

# --- Analytics Computations ---

def get_admin_dashboard_stats():
    get_db()
    
    if use_json_fallback:
        users = read_json_file("users.json")
        cases = read_json_file("cases.json")
        
        total_users = len(users)
        total_cases = len(cases)
        
        escalated_cases = sum(1 for c in cases if c.get("status") == "Escalated")
        approved_cases = sum(1 for c in cases if c.get("status") == "Approved")
        rejected_cases = sum(1 for c in cases if c.get("status") == "Rejected")
        pending_cases = sum(1 for c in cases if c.get("status") == "Pending")
        
        # Cases by Category
        cases_by_category = {}
        for c in cases:
            cat = c.get("category")
            if cat:
                cases_by_category[cat] = cases_by_category.get(cat, 0) + 1
                
        # Cases by Status
        cases_by_status = {}
        for c in cases:
            stat = c.get("status")
            if stat:
                cases_by_status[stat] = cases_by_status.get(stat, 0) + 1
                
        # Cases monthly trends (group by Year-Month string: YYYY-MM)
        monthly_cases = {}
        for c in cases:
            dt_str = c.get("created_date", "")
            if dt_str:
                month_str = dt_str[:7] # Get 'YYYY-MM'
                monthly_cases[month_str] = monthly_cases.get(month_str, 0) + 1
                
        # Escalation trends
        escalated_count = sum(1 for c in cases if c.get("escalation_status") == True)
        non_escalated_count = sum(1 for c in cases if c.get("escalation_status") == False)
        
        return {
            "total_users": total_users,
            "total_cases": total_cases,
            "escalated_cases": escalated_cases,
            "approved_cases": approved_cases,
            "rejected_cases": rejected_cases,
            "pending_cases": pending_cases,
            "cases_by_category": cases_by_category,
            "cases_by_status": cases_by_status,
            "monthly_cases": monthly_cases,
            "escalation_trends": {
                "Escalated": escalated_count,
                "NonEscalated": non_escalated_count
            }
        }
    else:
        database = get_db()
        total_users = database.users.count_documents({})
        total_cases = database.cases.count_documents({})
        escalated_cases = database.cases.count_documents({"status": "Escalated"})
        approved_cases = database.cases.count_documents({"status": "Approved"})
        rejected_cases = database.cases.count_documents({"status": "Rejected"})
        pending_cases = database.cases.count_documents({"status": "Pending"})
        
        # Category
        pipeline_category = [{"$group": {"_id": "$category", "count": {"$sum": 1}}}]
        categories_res = list(database.cases.aggregate(pipeline_category))
        cases_by_category = {item["_id"]: item["count"] for item in categories_res if item["_id"]}
        
        # Status
        pipeline_status = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
        status_res = list(database.cases.aggregate(pipeline_status))
        cases_by_status = {item["_id"]: item["count"] for item in status_res if item["_id"]}
        
        # Monthly
        pipeline_monthly = [
            {"$project": {"month": {"$dateToString": {"format": "%Y-%m", "date": "$created_date"}}}},
            {"$group": {"_id": "$month", "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}}
        ]
        monthly_res = list(database.cases.aggregate(pipeline_monthly))
        monthly_cases = {item["_id"]: item["count"] for item in monthly_res if item["_id"]}
        
        # Escalated counts
        escalated_count = database.cases.count_documents({"escalation_status": True})
        non_escalated_count = database.cases.count_documents({"escalation_status": False})
        
        return {
            "total_users": total_users,
            "total_cases": total_cases,
            "escalated_cases": escalated_cases,
            "approved_cases": approved_cases,
            "rejected_cases": rejected_cases,
            "pending_cases": pending_cases,
            "cases_by_category": cases_by_category,
            "cases_by_status": cases_by_status,
            "monthly_cases": monthly_cases,
            "escalation_trends": {
                "Escalated": escalated_count,
                "NonEscalated": non_escalated_count
            }
        }

def get_manager_dashboard_stats():
    get_db()
    
    if use_json_fallback:
        cases = read_json_file("cases.json")
        return {
            "escalated_cases": sum(1 for c in cases if c.get("status") == "Escalated"),
            "pending_review": sum(1 for c in cases if c.get("status") == "Pending"),
            "approved_cases": sum(1 for c in cases if c.get("status") == "Approved"),
            "rejected_cases": sum(1 for c in cases if c.get("status") == "Rejected")
        }
    else:
        database = get_db()
        return {
            "escalated_cases": database.cases.count_documents({"status": "Escalated"}),
            "pending_review": database.cases.count_documents({"status": "Pending"}),
            "approved_cases": database.cases.count_documents({"status": "Approved"}),
            "rejected_cases": database.cases.count_documents({"status": "Rejected"})
        }

def get_agent_dashboard_stats(agent_email):
    get_db()
    
    if use_json_fallback:
        cases = read_json_file("cases.json")
        my_cases = [c for c in cases if c.get("created_by") == agent_email]
        
        my_count = len(my_cases)
        generated = sum(1 for c in my_cases if c.get("status") == "Generated")
        escalated = sum(1 for c in my_cases if c.get("status") == "Escalated")
        pending = sum(1 for c in my_cases if c.get("status") == "Pending")
        approved = sum(1 for c in my_cases if c.get("status") == "Approved")
        rejected = sum(1 for c in my_cases if c.get("status") == "Rejected")
        
        return {
            "my_cases": my_count,
            "generated_responses": generated,
            "escalated_cases": escalated,
            "pending_cases": pending + generated,
            "approved_cases": approved,
            "rejected_cases": rejected
        }
    else:
        database = get_db()
        my_cases = database.cases.count_documents({"created_by": agent_email})
        generated = database.cases.count_documents({"created_by": agent_email, "status": "Generated"})
        escalated = database.cases.count_documents({"created_by": agent_email, "status": "Escalated"})
        pending = database.cases.count_documents({"created_by": agent_email, "status": "Pending"})
        approved = database.cases.count_documents({"created_by": agent_email, "status": "Approved"})
        rejected = database.cases.count_documents({"created_by": agent_email, "status": "Rejected"})
        
        return {
            "my_cases": my_cases,
            "generated_responses": generated,
            "escalated_cases": escalated,
            "pending_cases": pending + generated,
            "approved_cases": approved,
            "rejected_cases": rejected
        }
