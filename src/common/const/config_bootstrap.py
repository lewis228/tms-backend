"""환경변수 부트스트랩.

로딩 우선순위:
  1) os.environ 에 이미 세팅된 값 (최우선 — override 의도)
  2) .env 파일 (로컬 개발)
  3) AWS Parameter Store (EC2 dev/prod, IAM Role 인증)

``APP_ENV`` 로 소스를 명시 구분한다:
  - ``local``  → .env 만 사용, Parameter Store 스킵 (로컬 개발자)
  - ``dev``    → Parameter Store prefix ``/omniq/dev/shipmenttrackingengine/``
  - ``prod``   → Parameter Store prefix ``/omniq/prod/shipmenttrackingengine/`` (미래)

``APP_ENV`` 가 없고 ``.env`` 도 없으면 자동으로 Parameter Store 시도 (EC2 부트스트랩 호환).

scraping 레포와 동일한 키 스키마를 사용하므로 tracking-api Settings 필드명으로 alias 매핑:
    DB_USER           → DB_USERNAME
    DB_NAME           → DB_DATABASE
    S3_BUCKET_STORAGE → MINIO_BUCKET
    S3_PUBLIC_URL     → MINIO_PUBLIC_URL

Settings() 가 인스턴스화되기 전에 `load_env()` 가 반드시 실행되어야 한다.
common/const/settings.py 의 최상단에서 호출한다.
"""

from __future__ import annotations

import os
from pathlib import Path

_LOADED = False

_PROJECT_ROOT = Path(__file__).resolve().parents[3]  # repo root (src/common/const → repo)
_DEFAULT_PARAM_STORE_PATH = "/omniq/dev/shipmenttrackingengine/"

# Parameter Store 키 → tracking-api Settings 키
_ALIAS_MAP = {
    "DB_USER": "DB_USERNAME",
    "DB_NAME": "DB_DATABASE",
    "S3_BUCKET_STORAGE": "MINIO_BUCKET",
    "S3_PUBLIC_URL": "MINIO_PUBLIC_URL",
}


def load_env() -> None:
    global _LOADED
    if _LOADED:
        return
    _LOADED = True

    # 1) .env 가 있으면 먼저 로드 (override=False — 기존 os.environ 유지).
    #    이 단계가 APP_ENV 자체를 공급하는 주 경로다.
    env_file = _PROJECT_ROOT / ".env"
    if env_file.exists():
        _load_dotenv(env_file)

    app_env = (os.environ.get("APP_ENV") or "").strip().lower()

    # 2) APP_ENV 결정:
    #    - local     → Parameter Store 스킵
    #    - dev/prod  → Parameter Store 로드
    #    - 빈 값      → .env 가 있으면 local 로 추정, 없으면 Parameter Store 시도
    should_load_ssm = False
    if app_env in ("dev", "prod", "production", "staging"):
        should_load_ssm = True
    elif not app_env and not env_file.exists():
        # .env 없는데 APP_ENV 도 비어있음 → EC2 부트스트랩으로 간주
        should_load_ssm = True

    if should_load_ssm:
        try:
            _load_parameter_store(_resolve_param_store_path(app_env))
        except Exception as e:  # noqa: BLE001
            print(f"[config_bootstrap] WARN: Parameter Store load failed: {e}")

    _apply_aliases()
    _default_minio_for_s3()


def _resolve_param_store_path(app_env: str) -> str:
    """PARAM_STORE_PREFIX 환경변수 > APP_ENV 기반 기본값 > 하드코딩 기본값 순."""
    explicit = os.environ.get("PARAM_STORE_PREFIX")
    if explicit:
        return explicit if explicit.endswith("/") else explicit + "/"
    if app_env == "prod" or app_env == "production":
        return "/omniq/prod/shipmenttrackingengine/"
    return _DEFAULT_PARAM_STORE_PATH


def _load_dotenv(path: Path) -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        return
    load_dotenv(path, override=False)


def _load_parameter_store(path: str) -> None:
    import boto3  # 지연 import

    region = (
        os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or "us-west-1"
    )
    client = boto3.client("ssm", region_name=region)

    next_token: str | None = None
    loaded = 0
    while True:
        kwargs: dict = {"Path": path, "Recursive": True, "WithDecryption": True}
        if next_token:
            kwargs["NextToken"] = next_token

        resp = client.get_parameters_by_path(**kwargs)
        for p in resp.get("Parameters", []):
            key = p["Name"].rsplit("/", 1)[-1]
            # os.environ (= .env 로드 후) 이 우선 — 이미 있으면 덮어쓰지 않음.
            if key not in os.environ:
                os.environ[key] = p["Value"]
                loaded += 1

        next_token = resp.get("NextToken")
        if not next_token:
            break

    print(f"[config_bootstrap] Parameter Store에서 {loaded}개 로드: {path}")


def _apply_aliases() -> None:
    """scraping 레포 키를 tracking-api Settings 필드명으로 복사."""
    for src, dst in _ALIAS_MAP.items():
        if src in os.environ and dst not in os.environ:
            os.environ[dst] = os.environ[src]


def _default_minio_for_s3() -> None:
    """EC2 환경(IAM Role 사용)에서는 MINIO_ACCESS_KEY / SECRET_KEY가 없다.

    Settings가 required이므로 빈 문자열로 채운다. file/const/consts.py에서 이 값이 비어 있으면
    boto3의 default credential chain(IAM Role)을 사용하도록 처리한다.
    MINIO_ENDPOINT도 EC2에선 비워둔다(기본 AWS S3 엔드포인트 사용).
    """
    os.environ.setdefault("MINIO_ACCESS_KEY", "")
    os.environ.setdefault("MINIO_SECRET_KEY", "")
    os.environ.setdefault("MINIO_ENDPOINT", "")


# Import 시점에 자동 실행
load_env()
