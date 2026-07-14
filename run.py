import os
import sys
from dotenv import load_dotenv

# Add current folder to sys.path to enable absolute imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environmental configs
load_dotenv()

from backend.config import Config
from backend.database import get_db

if __name__ == "__main__":
    print("\n=====================================================================")
    print("             AI CUSTOMER SUPPORT RESPONSE GENERATOR PRO              ")
    print("                     PRODUCTION SERVER LAUNCHER                      ")
    print("=====================================================================\n")
    
    # Check for .env file
    if not os.path.exists(".env"):
        print("WARNING: '.env' file not found in root directory!")
        print("Please copy '.env.example' to '.env' and provide your:")
        print("  - MONGO_URI (MongoDB connection string)")
        print("  - GROQ_API_KEY (Groq API token)")
        print("  - JWT_SECRET (Private signature key)")
        print("---------------------------------------------------------------------\n")
    
    # Configuration diagnostics
    errors = Config.validate()
    if errors:
        print("CONFIG WARNINGS:")
        for err in errors:
            print(f"  - {err}")
        print("---------------------------------------------------------------------\n")
        
    # Test MongoDB Connection
    try:
        get_db()
        print("STATUS: Connected to MongoDB database successfully.")
    except Exception as e:
        print(f"CRITICAL: Failed to connect to MongoDB. Details: {e}")
        print("Make sure MongoDB service is running or your Atlas URI is white-listed.")
        print("---------------------------------------------------------------------\n")
        
    # Run server
    from backend.app import app
    print(f"STATUS: Launching Flask App on http://localhost:{Config.PORT}")
    print("=====================================================================\n")
    app.run(host="0.0.0.0", port=Config.PORT, debug=True)
