import os
from pathlib import Path

PROJECT_ROOT_PATH = Path(__file__).resolve().parent.parent.parent.parent
PUBLIC_FOLDER_NAME = "public"
PUBLIC_FOLDER_PATH = os.path.join(PROJECT_ROOT_PATH, PUBLIC_FOLDER_NAME)
