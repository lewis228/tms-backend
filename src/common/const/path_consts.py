import os
from pathlib import Path

#  1. 프로젝트 최상단의 절대 경로
# PROJECT_ROOT_PATH = os.getcwd()  # 또는 os.path.dirname(os.path.abspath(__file__))

#  현재 파일 기준으로 Backend 폴더 계산
PROJECT_ROOT_PATH = Path(__file__).resolve().parent.parent.parent.parent

#  2. 폴더 이름 정의
PUBLIC_FOLDER_NAME = "public"
POSTS_FOLDER_NAME = "posts"
TEMP_FOLDER_NAME = "temp"
BACKUP_FOLDER_NAME = "backup"
FILES_FOLDER_NAME = "files" 

#  3. 실제 공개 폴더의 절대 경로: {프로젝트}/public
PUBLIC_FOLDER_PATH = os.path.join(PROJECT_ROOT_PATH, PUBLIC_FOLDER_NAME)

#  4. 포스트 이미지 폴더: {프로젝트}/public/posts
POST_IMAGE_PATH = os.path.join(PUBLIC_FOLDER_PATH, POSTS_FOLDER_NAME)

#  5. 클라이언트에게 전달할 공개 이미지 경로: public/posts/xxx.jpg
POST_PUBLIC_IMAGE_PATH = os.path.join(PUBLIC_FOLDER_NAME, POSTS_FOLDER_NAME)

#  6. 임시 업로드 폴더: {프로젝트}/public/temp
TEMP_FOLDER_PATH = os.path.join(PUBLIC_FOLDER_PATH, TEMP_FOLDER_NAME)

#  7. 이미지 백업 폴더: {프로젝트}/public/backup
TEMP_BACKUP_PATH = os.path.join(PUBLIC_FOLDER_PATH, BACKUP_FOLDER_NAME)

#  8. 실제 파일 업로드 위치: {프로젝트}/public/files
FILE_UPLOAD_PATH = os.path.join(PUBLIC_FOLDER_PATH, FILES_FOLDER_NAME)

#  9. 클라이언트에게 제공될 파일 경로 (예: public/files/xxx.ext)
FILE_PUBLIC_PATH = os.path.join(PUBLIC_FOLDER_NAME, FILES_FOLDER_NAME)
