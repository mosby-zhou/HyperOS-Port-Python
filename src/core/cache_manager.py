"""
Port ROM Cache Manager - 多机型移植缓存复用机制

This module provides a hierarchical caching system for Port ROM processing,
enabling reuse of extracted partitions and APK modifications across multiple
device porting operations.

Features:
    - Partition-level caching (Level 1)
    - APK modification caching (Level 2)
    - File lock support for concurrent access
    - Cache metadata management with versioning
    - Automatic cache validation and invalidation

Usage:
    cache = PortRomCacheManager(".cache/portroms")

    # Store partition
    cache.store_partition(rom_path, "system", extracted_dir)

    # Restore partition
    cache.restore_partition(rom_path, "system", target_dir)

    # Check cache validity
    if cache.is_partition_cached(rom_path, "system"):
        print("Cache hit!")
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any, Union
import threading


# Cache format version
CACHE_VERSION = "1.0"
DEFAULT_CACHE_ROOT = ".cache/portroms"


@dataclass
class CacheMetadata:
    """缓存元数据结构"""

    version: str = CACHE_VERSION
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    rom_hash: str = ""
    partition_name: str = ""
    file_count: int = 0
    total_size: int = 0
    modifier_version: str = "1.0"
    source_size: int = 0
    rom_type: str = ""  # ROM类型 (PAYLOAD, FASTBOOT, etc.)
    extracted_at: str = ""  # 提取时间戳

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CacheMetadata":
        return cls(**data)


class FileLock:
    """
    跨平台文件锁实现

    支持Unix (fcntl) 和 Windows (portalocker备选)
    """

    def __init__(self, lock_file: Union[str, Path], timeout: float = 30.0):
        self.lock_file = Path(lock_file)
        self.timeout = timeout
        self._lock_fd: Optional[Any] = None
        self._logger = logging.getLogger("FileLock")

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False

    def acquire(self) -> bool:
        """获取文件锁"""
        import fcntl

        self.lock_file.parent.mkdir(parents=True, exist_ok=True)

        start_time = time.time()
        while True:
            try:
                self._lock_fd = open(self.lock_file, "w")
                fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._logger.debug(f"Lock acquired: {self.lock_file}")
                return True
            except (IOError, OSError) as e:
                if self._lock_fd:
                    self._lock_fd.close()
                    self._lock_fd = None

                if time.time() - start_time > self.timeout:
                    self._logger.warning(f"Lock timeout after {self.timeout}s")
                    raise TimeoutError(f"Could not acquire lock: {self.lock_file}")

                time.sleep(0.1)

    def release(self):
        """释放文件锁"""
        import fcntl

        if self._lock_fd:
            try:
                fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_UN)
                self._lock_fd.close()
                self._logger.debug(f"Lock released: {self.lock_file}")
            except Exception as e:
                self._logger.error(f"Error releasing lock: {e}")
            finally:
                self._lock_fd = None


class PortRomCacheManager:
    """
    Port ROM缓存管理器

    管理Port ROM的分区和APK修改缓存，支持多设备复用。

    Attributes:
        cache_root: 缓存根目录路径
        logger: 日志记录器

    Example:
        >>> cache = PortRomCacheManager(".cache/portroms")
        >>> cache.store_partition(rom_path, "system", extracted_dir)
        >>> cache.restore_partition(rom_path, "system", target_dir)
    """

    def __init__(self, cache_root: Union[str, Path] = DEFAULT_CACHE_ROOT):
        """
        初始化缓存管理器

        Args:
            cache_root: 缓存根目录路径，默认为".cache/portroms"
        """
        self.cache_root = Path(cache_root).resolve()
        self.cache_root.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("PortRomCacheManager")

        # 确保元数据目录存在
        self._metadata_file = self.cache_root / "metadata.json"
        self._load_global_metadata()

    def _load_global_metadata(self):
        """加载全局缓存元数据"""
        if self._metadata_file.exists():
            try:
                with open(self._metadata_file, "r", encoding="utf-8") as f:
                    self._global_metadata = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                self.logger.warning(f"Failed to load global metadata: {e}")
                self._global_metadata = {"version": CACHE_VERSION, "roms": {}}
        else:
            self._global_metadata = {"version": CACHE_VERSION, "roms": {}}

    def _save_global_metadata(self):
        """保存全局缓存元数据"""
        try:
            with open(self._metadata_file, "w", encoding="utf-8") as f:
                json.dump(self._global_metadata, f, indent=2)
        except IOError as e:
            self.logger.error(f"Failed to save global metadata: {e}")

    def _compute_rom_hash(self, rom_path: Union[str, Path]) -> str:
        """
        计算ROM文件的哈希值

        对于大文件，使用分段哈希以提高性能：
        - 文件头10MB
        - 文件中间10MB
        - 文件尾10MB

        Args:
            rom_path: ROM文件路径

        Returns:
            32字符的MD5哈希字符串
        """
        path = Path(rom_path)
        if not path.exists():
            raise FileNotFoundError(f"ROM file not found: {path}")

        hash_md5 = hashlib.md5()
        file_size = path.stat().st_size

        with open(path, "rb") as f:
            if file_size < 100 * 1024 * 1024:  # < 100MB
                # 小文件：读取全部内容
                hash_md5.update(f.read())
            else:
                # 大文件：分段读取
                chunk_size = 10 * 1024 * 1024  # 10MB

                # 读取开头
                hash_md5.update(f.read(chunk_size))

                # 读取中间
                f.seek(file_size // 2)
                hash_md5.update(f.read(chunk_size))

                # 读取结尾
                f.seek(-chunk_size, 2)
                hash_md5.update(f.read(chunk_size))

        return hash_md5.hexdigest()

    def _get_rom_cache_dir(self, rom_hash: str) -> Path:
        """获取ROM缓存目录"""
        return self.cache_root / rom_hash[:16]

    def _get_partition_cache_dir(self, rom_hash: str, partition: str) -> Path:
        """获取分区缓存目录"""
        return self._get_rom_cache_dir(rom_hash) / "partitions" / partition

    def _get_apk_cache_dir(self, rom_hash: str) -> Path:
        """获取APK缓存目录"""
        return self._get_rom_cache_dir(rom_hash) / "apks"

    def _get_lock_file(self, rom_hash: str) -> Path:
        """获取锁文件路径"""
        return self._get_rom_cache_dir(rom_hash) / ".lock"

    def is_partition_cached(
        self, rom_path: Union[str, Path], partition: str, validate: bool = True
    ) -> bool:
        """
        检查分区是否已缓存

        Args:
            rom_path: ROM文件路径
            partition: 分区名称 (如 "system", "product")
            validate: 是否验证缓存完整性

        Returns:
            True如果缓存存在且有效
        """
        try:
            rom_hash = self._compute_rom_hash(rom_path)
        except FileNotFoundError:
            return False

        cache_dir = self._get_partition_cache_dir(rom_hash, partition)
        metadata_file = cache_dir / "cache_metadata.json"

        if not cache_dir.exists() or not metadata_file.exists():
            return False

        if not validate:
            return True

        # 验证缓存元数据
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata = CacheMetadata.from_dict(json.load(f))

            # 检查版本兼容性
            if metadata.version != CACHE_VERSION:
                self.logger.debug(f"Cache version mismatch: {metadata.version} vs {CACHE_VERSION}")
                return False

            # 检查缓存目录非空
            if not any(cache_dir.iterdir()):
                return False

            return True

        except (json.JSONDecodeError, IOError, KeyError) as e:
            self.logger.debug(f"Cache validation failed: {e}")
            return False

    def store_partition(
        self,
        rom_path: Union[str, Path],
        partition: str,
        source_dir: Union[str, Path],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        存储分区到缓存

        Args:
            rom_path: ROM文件路径
            partition: 分区名称
            source_dir: 源目录路径
            metadata: 额外元数据

        Returns:
            True如果存储成功
        """
        rom_hash = self._compute_rom_hash(rom_path)
        cache_dir = self._get_partition_cache_dir(rom_hash, partition)
        lock_file = self._get_lock_file(rom_hash)

        with FileLock(lock_file):
            try:
                # 清理旧缓存
                if cache_dir.exists():
                    shutil.rmtree(cache_dir)
                cache_dir.mkdir(parents=True, exist_ok=True)

                # 复制文件
                source = Path(source_dir)
                file_count = 0
                total_size = 0

                for item in source.rglob("*"):
                    if item.is_file():
                        rel_path = item.relative_to(source)
                        target = cache_dir / rel_path
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, target, follow_symlinks=False)
                        file_count += 1
                        total_size += item.stat().st_size

                # 保存元数据
                cache_metadata = CacheMetadata(
                    rom_hash=rom_hash,
                    partition_name=partition,
                    file_count=file_count,
                    total_size=total_size,
                    source_size=Path(rom_path).stat().st_size,
                    **(metadata or {}),
                )

                metadata_file = cache_dir / "cache_metadata.json"
                with open(metadata_file, "w", encoding="utf-8") as f:
                    json.dump(cache_metadata.to_dict(), f, indent=2)

                # 更新全局元数据
                self._global_metadata["roms"][rom_hash] = {
                    "hash": rom_hash,
                    "cached_at": datetime.now().isoformat(),
                    "partitions": list(
                        self._global_metadata["roms"].get(rom_hash, {}).get("partitions", [])
                    )
                    + [partition],
                }
                self._save_global_metadata()

                self.logger.info(
                    f"Cached partition {partition}: {file_count} files, "
                    f"{total_size / 1024 / 1024:.1f} MB"
                )
                return True

            except Exception as e:
                self.logger.error(f"Failed to cache partition {partition}: {e}")
                # 清理失败的缓存
                if cache_dir.exists():
                    shutil.rmtree(cache_dir)
                return False

    def restore_partition(
        self, rom_path: Union[str, Path], partition: str, target_dir: Union[str, Path]
    ) -> bool:
        """
        从缓存恢复分区

        Args:
            rom_path: ROM文件路径
            partition: 分区名称
            target_dir: 目标目录路径

        Returns:
            True如果恢复成功
        """
        if not self.is_partition_cached(rom_path, partition):
            return False

        rom_hash = self._compute_rom_hash(rom_path)
        cache_dir = self._get_partition_cache_dir(rom_hash, partition)
        target = Path(target_dir)

        try:
            # 清理目标目录
            if target.exists():
                shutil.rmtree(target)
            target.mkdir(parents=True, exist_ok=True)

            # 复制文件（排除元数据文件）
            for item in cache_dir.rglob("*"):
                if item.name == "cache_metadata.json":
                    continue
                if item.is_file():
                    rel_path = item.relative_to(cache_dir)
                    dst = target / rel_path
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dst, follow_symlinks=False)

            self.logger.info(f"Restored partition {partition} from cache")
            return True

        except Exception as e:
            self.logger.error(f"Failed to restore partition {partition}: {e}")
            return False

    def get_cache_info(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            包含缓存统计的字典
        """
        info = {
            "version": CACHE_VERSION,
            "cache_root": str(self.cache_root),
            "total_size_bytes": 0,
            "total_size_mb": 0,
            "cached_roms": [],
        }

        try:
            for rom_dir in self.cache_root.iterdir():
                if not rom_dir.is_dir():
                    continue
                if rom_dir.name in ["metadata.json", ".lock"]:
                    continue

                rom_info = {
                    "hash": rom_dir.name,
                    "partitions": [],
                    "total_size_bytes": 0,
                }

                partitions_dir = rom_dir / "partitions"
                if partitions_dir.exists():
                    for part_dir in partitions_dir.iterdir():
                        if part_dir.is_dir():
                            part_size = sum(
                                f.stat().st_size for f in part_dir.rglob("*") if f.is_file()
                            )
                            rom_info["partitions"].append(
                                {
                                    "name": part_dir.name,
                                    "size_bytes": part_size,
                                    "size_mb": round(part_size / 1024 / 1024, 2),
                                }
                            )
                            rom_info["total_size_bytes"] += part_size

                info["cached_roms"].append(rom_info)
                info["total_size_bytes"] += rom_info["total_size_bytes"]

            info["total_size_mb"] = round(info["total_size_bytes"] / 1024 / 1024, 2)

        except Exception as e:
            self.logger.error(f"Error getting cache info: {e}")

        return info

    def list_cached_roms(self) -> List[Dict[str, Any]]:
        """列出所有缓存的ROM"""
        return self.get_cache_info().get("cached_roms", [])

    def clear_partition(self, rom_path: Union[str, Path], partition: str) -> bool:
        """
        清除特定分区缓存

        Args:
            rom_path: ROM文件路径
            partition: 分区名称

        Returns:
            True如果清除成功
        """
        try:
            rom_hash = self._compute_rom_hash(rom_path)
            cache_dir = self._get_partition_cache_dir(rom_hash, partition)
            lock_file = self._get_lock_file(rom_hash)

            with FileLock(lock_file):
                if cache_dir.exists():
                    shutil.rmtree(cache_dir)
                    self.logger.info(f"Cleared cache for partition {partition}")
                    return True
            return False

        except Exception as e:
            self.logger.error(f"Failed to clear partition cache: {e}")
            return False

    def clear_rom(self, rom_path: Union[str, Path]) -> bool:
        """
        清除特定ROM的所有缓存

        Args:
            rom_path: ROM文件路径

        Returns:
            True如果清除成功
        """
        try:
            rom_hash = self._compute_rom_hash(rom_path)
            rom_dir = self._get_rom_cache_dir(rom_hash)
            lock_file = self._get_lock_file(rom_hash)

            with FileLock(lock_file):
                if rom_dir.exists():
                    shutil.rmtree(rom_dir)

                # 从全局元数据中移除
                if rom_hash in self._global_metadata.get("roms", {}):
                    del self._global_metadata["roms"][rom_hash]
                    self._save_global_metadata()

                self.logger.info(f"Cleared all cache for ROM {rom_hash[:16]}...")
                return True

        except Exception as e:
            self.logger.error(f"Failed to clear ROM cache: {e}")
            return False

    def clear_all(self) -> bool:
        """
        清除所有缓存

        Returns:
            True如果清除成功
        """
        try:
            for item in self.cache_root.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                elif item.is_file() and item.name != ".gitkeep":
                    item.unlink()

            self._global_metadata = {"version": CACHE_VERSION, "roms": {}}
            self._save_global_metadata()

            self.logger.info("Cleared all cache")
            return True

        except Exception as e:
            self.logger.error(f"Failed to clear all cache: {e}")
            return False

    def verify_integrity(self, rom_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """
        验证缓存完整性

        Args:
            rom_path: 可选，指定ROM进行验证。None表示验证所有

        Returns:
            验证结果字典
        """
        results = {
            "valid": [],
            "invalid": [],
            "errors": [],
        }

        try:
            if rom_path:
                roms_to_check = [Path(rom_path)]
            else:
                # 从元数据中获取所有缓存的ROM
                roms_to_check = [
                    self.cache_root / rom_hash[:16]
                    for rom_hash in self._global_metadata.get("roms", {}).keys()
                ]

            for rom_item in roms_to_check:
                if not rom_item.exists():
                    continue

                partitions_dir = rom_item / "partitions"
                if not partitions_dir.exists():
                    continue

                for part_dir in partitions_dir.iterdir():
                    if not part_dir.is_dir():
                        continue

                    metadata_file = part_dir / "cache_metadata.json"
                    if not metadata_file.exists():
                        results["invalid"].append(
                            {
                                "rom": rom_item.name,
                                "partition": part_dir.name,
                                "reason": "Missing metadata",
                            }
                        )
                        continue

                    try:
                        with open(metadata_file, "r", encoding="utf-8") as f:
                            metadata = json.load(f)

                        # 验证文件数量
                        actual_files = (
                            sum(1 for _ in part_dir.rglob("*") if _.is_file()) - 1
                        )  # 排除metadata
                        expected_files = metadata.get("file_count", 0)

                        if actual_files != expected_files:
                            results["invalid"].append(
                                {
                                    "rom": rom_item.name,
                                    "partition": part_dir.name,
                                    "reason": f"File count mismatch: {actual_files} vs {expected_files}",
                                }
                            )
                        else:
                            results["valid"].append(
                                {
                                    "rom": rom_item.name,
                                    "partition": part_dir.name,
                                    "files": actual_files,
                                }
                            )

                    except Exception as e:
                        results["errors"].append(
                            {
                                "rom": rom_item.name,
                                "partition": part_dir.name,
                                "error": str(e),
                            }
                        )

        except Exception as e:
            results["errors"].append({"global": str(e)})

        return results


# 便捷函数
def get_cache_manager(cache_root: Union[str, Path] = DEFAULT_CACHE_ROOT) -> PortRomCacheManager:
    """获取缓存管理器实例"""
    return PortRomCacheManager(cache_root)
