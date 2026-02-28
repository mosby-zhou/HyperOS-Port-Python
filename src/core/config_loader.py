import json
import logging
from pathlib import Path
from typing import Any


class ConfigMerger:
    """
    Configuration merger for device-specific settings.
    Merges configurations from common -> device layers with deep merge support.
    """
    
    def __init__(self, logger: logging.Logger = None):
        self.logger = logger or logging.getLogger("ConfigMerger")
    
    def deep_merge(self, base: dict, override: dict) -> dict:
        """
        Deep merge two dictionaries. Override values take precedence.
        
        Args:
            base: Base dictionary
            override: Dictionary with values to override
            
        Returns:
            Merged dictionary
        """
        result = base.copy()
        
        for key, value in override.items():
            if key.startswith("_"):
                # Skip metadata keys (like _comment)
                continue
                
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self.deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def load_config(self, config_path: Path) -> dict:
        """Load a single configuration file."""
        if not config_path.exists():
            return {}
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse {config_path}: {e}")
            return {}
        except Exception as e:
            self.logger.error(f"Failed to load {config_path}: {e}")
            return {}
    
    def load_device_config(self, device_codename: str) -> dict:
        """
        Load and merge configuration for a specific device.
        Hierarchy: common -> device
        
        Args:
            device_codename: Device codename (e.g., 'mayfly', 'fuxi')
            
        Returns:
            Merged configuration dictionary
        """
        devices_dir = Path("devices")
        
        # Load common config
        common_config = self.load_config(devices_dir / "common" / "config.json")
        if common_config:
            self.logger.info("Loaded common config.")
        
        # Load device-specific config
        device_config = self.load_config(devices_dir / device_codename / "config.json")
        if device_config:
            self.logger.info(f"Loaded device config for {device_codename}.")
        
        # Merge configurations
        merged = self.deep_merge(common_config, device_config)
        
        # Log summary
        self._log_config_summary(merged, device_codename)
        
        return merged
    
    def _log_config_summary(self, config: dict, device_codename: str):
        """Log configuration summary."""
        wild_boost = config.get("wild_boost", {})
        pack = config.get("pack", {})
        ksu = config.get("ksu", {})
        
        self.logger.info(f"Configuration for {device_codename}:")
        self.logger.info(f"  Wild Boost: enabled={wild_boost.get('enable', False)}")
        self.logger.info(f"  Pack: type={pack.get('type', 'payload')}, "
                        f"fs_type={pack.get('fs_type', 'erofs')}")
        self.logger.info(f"  KSU: enabled={ksu.get('enable', False)}")


# Singleton instance for easy access
_config_merger = None

def get_config_merger(logger: logging.Logger = None) -> ConfigMerger:
    """Get or create ConfigMerger singleton."""
    global _config_merger
    if _config_merger is None:
        _config_merger = ConfigMerger(logger)
    return _config_merger


def load_device_config(device_codename: str, logger: logging.Logger = None) -> dict:
    """
    Convenience function to load device configuration.
    
    Args:
        device_codename: Device codename
        logger: Optional logger instance
        
    Returns:
        Merged configuration dictionary
    """
    merger = get_config_merger(logger)
    return merger.load_device_config(device_codename)
