from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_db: str = "helios"
    postgres_user: str = "helios"
    postgres_password: str = "changeme"
    database_url: str = "postgresql+asyncpg://helios:changeme@postgres:5432/helios"
    database_url_sync: str = "postgresql://helios:changeme@postgres:5432/helios"
    redis_url: str = "redis://redis:6379/0"
    triton_url: str = "triton:8000"
    jwt_secret: str = "change-me-in-production"

    copernicus_client_id: str = ""
    copernicus_client_secret: str = ""
    copernicus_token_url: str = (
        "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
    )
    copernicus_stac_url: str = "https://catalogue.dataspace.copernicus.eu/stac/search"
    copernicus_s3_credentials_url: str = "https://eodata.dataspace.copernicus.eu/s3-credentials"
    copernicus_s3_endpoint: str = "https://eodata.dataspace.copernicus.eu"

    planet_api_key: str = ""
    planet_api_base: str = "https://api.planet.com"

    data_root: str = "/data"
    tiles_dir: str = "/tiles"
    dem_path: str = "/data/dem/srtm_30m.tif"
    max_cloud_cover: float = 0.30
    tile_size: int = 640
    tile_overlap: float = 0.20

    yolo_confidence_min: float = 0.25
    nms_iou_threshold: float = 0.45
    mstar_confidence_min: float = 0.50
    bit_change_threshold: float = 0.50
    detections_dir: str = "/data/detections"
    artifacts_dir: str = "/ml/artifacts"
    yolo_weights_path: str = "/ml/artifacts/yolo/best.pt"
    triton_yolo_model: str = "yolov8_detection"
    triton_mstar_model: str = "mstar_sar"
    triton_bit_model: str = "bit_change"
    kaggle_username: str = ""
    kaggle_key: str = ""
    ml_data_dir: str = "./ml/datasets"
    yolo_model_size: str = "s"


settings = Settings()
