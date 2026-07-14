import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

class Config:
    PORT = int(os.environ.get("PORT", 5000))
    MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/support_generator")
    JWT_SECRET = os.environ.get("JWT_SECRET", "super-secret-key-change-in-production")
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
    
    @classmethod
    def validate(cls):
        """Validates that necessary configuration options are provided."""
        errors = []
        if not cls.MONGO_URI:
            errors.append("MONGO_URI environment variable is missing.")
        if not cls.JWT_SECRET or cls.JWT_SECRET == "super-secret-key-change-in-production":
            # For development it's fine, but warn or add error in production
            pass
        if not cls.GROQ_API_KEY:
            errors.append("GROQ_API_KEY environment variable is missing. AI response generation will fail.")
        return errors
