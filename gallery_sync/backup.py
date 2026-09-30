"""可选云备份模块：将图片备份到你自己的云存储。

支持 S3 兼容存储（AWS S3、阿里云 OSS、MinIO 等）和 WebDAV。
所有凭据由你在 config.yaml 中提供，仅用于你自己的存储账号。
"""

import os
import logging
from typing import Optional

from .config import BackupConfig

logger = logging.getLogger(__name__)


class BackupClient:
    def __init__(self, cfg: BackupConfig):
        self.cfg = cfg
        self._s3 = None
        self._webdav_session = None

    def _get_s3(self):
        if self._s3 is None:
            import boto3
            from botocore.client import Config as BotoConfig
            s3_cfg = self.cfg.s3
            self._s3 = boto3.client(
                "s3",
                endpoint_url=s3_cfg.get("endpoint"),
                aws_access_key_id=s3_cfg.get("access_key"),
                aws_secret_access_key=s3_cfg.get("secret_key"),
                region_name=s3_cfg.get("region", "us-east-1"),
                config=BotoConfig(s3={"addressing_style": "path"}),
            )
        return self._s3

    def upload_s3(self, local_path: str, remote_key: str) -> bool:
        try:
            self._get_s3().upload_file(local_path, self.cfg.s3["bucket"], remote_key)
            return True
        except Exception as e:
            logger.error("S3 上传失败 %s: %s", local_path, e)
            return False

    def upload_webdav(self, local_path: str, remote_path: str) -> bool:
        try:
            import requests
            from requests.auth import HTTPBasicAuth
            wd = self.cfg.webdav
            url = wd["url"].rstrip("/") + "/" + remote_path.lstrip("/")
            # 先确保上级目录存在
            parent = url.rsplit("/", 1)[0]
            try:
                requests.request("MKCOL", parent, auth=HTTPBasicAuth(wd["username"], wd["password"]))
            except Exception:
                pass
            with open(local_path, "rb") as f:
                r = requests.put(url, data=f, auth=HTTPBasicAuth(wd["username"], wd["password"]))
            return r.status_code in (200, 201, 204)
        except Exception as e:
            logger.error("WebDAV 上传失败 %s: %s", local_path, e)
            return False

    def upload(self, local_path: str, remote_key: str) -> bool:
        if not self.cfg.enabled:
            return False
        if self.cfg.type == "s3":
            return self.upload_s3(local_path, remote_key)
        elif self.cfg.type == "webdav":
            return self.upload_webdav(local_path, remote_key)
        else:
            logger.error("未知备份类型: %s", self.cfg.type)
            return False
