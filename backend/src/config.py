import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Load API keys from environment variables
GLADIA_API_KEY = os.getenv("GLADIA_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Database URL
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/dbname")

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your_secret_key_here")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

# Check if keys are present and raise ValueError if not
if not GLADIA_API_KEY:
    raise ValueError("GLADIA_API_KEY not found in environment variables. Please set it in your .env file.")

if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in environment variables. Please set it in your .env file.")