import os
import requests
import logging
from pathlib import Path

class AssetDownloader:
    def __init__(self, repo="toraidl/HyperOS-Port-Python", tag="assets"):
        self.repo = repo
        self.tag = tag
        self.base_url = f"https://github.com/{repo}/releases/download/{tag}"
        self.logger = logging.getLogger("Downloader")

    def _get_asset_name(self, local_path: Path) -> str:
        """
        Convert local path to remote asset name with prefix.
        Rules:
        - devices/common/file.zip -> common_file.zip
        - devices/fuxi/file.ko    -> fuxi_file.ko
        - assets/ksuinit          -> assets_ksuinit
        """
        parts = local_path.parts
        # If it's inside devices/...
        if "devices" in parts:
            idx = parts.index("devices")
            if len(parts) > idx + 1:
                # Get the folder name after 'devices' (e.g., 'common', 'fuxi')
                prefix = parts[idx + 1]
                name = parts[-1]
                return f"{prefix}_{name}"
        
        # If it's inside assets/...
        if "assets" in parts:
            name = parts[-1]
            return f"assets_{name}"
            
        return local_path.name

    def download_if_missing(self, local_path: Path) -> bool:
        """
        Check if file exists, if not, try to download from GitHub Assets.
        """
        if local_path.exists():
            return True

        asset_name = self._get_asset_name(local_path)
        url = f"{self.base_url}/{asset_name}"
        
        self.logger.info(f"File missing: {local_path.name}, attempting to download from {url}...")
        
        try:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            response = requests.get(url, stream=True, timeout=30)
            
            if response.status_code == 200:
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(local_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            # Simple progress log for large files
                            if total_size > 1024 * 1024 and downloaded % (1024 * 1024 * 5) < 8192:
                                self.logger.info(f"  Downloaded: {downloaded // (1024*1024)}MB / {total_size // (1024*1024)}MB")
                
                self.logger.info(f"Successfully downloaded: {local_path.name}")
                return True
            elif response.status_code == 404:
                self.logger.warning(f"Asset not found on GitHub: {asset_name}")
            else:
                self.logger.error(f"Failed to download (HTTP {response.status_code})")
                
        except Exception as e:
            self.logger.error(f"Error during download: {e}")
            if local_path.exists():
                local_path.unlink() # Cleanup partial download
                
        return False
