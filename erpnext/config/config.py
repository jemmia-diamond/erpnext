import os
import os
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

class ConfigBase:
    GAPONE_API_KEY: str  = os.getenv("GAPONE_API_KEY")

config = ConfigBase()