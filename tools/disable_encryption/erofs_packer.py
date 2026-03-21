#!/usr/bin/env python3
"""EROFS image packer for Android vendor partition.

This module provides functionality to pack a vendor directory into an EROFS image.
It supports automatic cluster size detection and integrates with Android build tools.
"""

import logging
import subprocess
from pathlib import Path
from typing import Optional

# Import project's ShellRunner for cross-platform binary discovery
import sys
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
from src.utils.shell import ShellRunner

logger = logging.getLogger(__name__)

# EROFS superblock constants
EROFS_SUPER_OFFSET = 1024
EROFS_MAGIC = b'\xe2\xe1\xf5\xe0'
EROFS_MAGIC_OFFSET = 0  # Relative to superblock start
EROFS_BLKSZBITS_OFFSET = 16  # Relative to superblock start


def get_dir_size(path: Path) -> int:
    """Calculate total size of all files in directory (excluding symlinks).

    Args:
        path: Directory path to calculate size for.

    Returns:
        Total size in bytes of all regular files in the directory tree.
    """
    total_size = 0
    if not path.exists():
        return 0

    for item in path.rglob('*'):
        # Skip symlinks, only count regular files
        if item.is_file() and not item.is_symlink():
            try:
                total_size += item.stat().st_size
            except OSError:
                # Skip files that can't be accessed
                pass

    return total_size


def read_erofs_cluster_size(img_path: Path) -> Optional[int]:
    """Read cluster size from EROFS superblock.

    EROFS superblock is located at offset 1024 from the start of the image.
    The magic number is at offset 0 (relative to superblock).
    blkszbits is at offset 16 (relative to superblock), which is log2 of block size.

    Args:
        img_path: Path to EROFS image file.

    Returns:
        Cluster size in bytes (2^blkszbits), or None if not a valid EROFS image.
    """
    if not img_path.exists():
        return None

    try:
        with open(img_path, 'rb') as f:
            # Seek to EROFS superblock
            f.seek(EROFS_SUPER_OFFSET)

            # Read magic number (4 bytes)
            magic = f.read(4)
            if magic != EROFS_MAGIC:
                logger.debug(f"Not a valid EROFS image: {img_path}")
                return None

            # Read blkszbits (1 byte at offset 16 from superblock)
            f.seek(EROFS_SUPER_OFFSET + EROFS_BLKSZBITS_OFFSET)
            blkszbits = ord(f.read(1))

            # Calculate cluster size: 2^blkszbits
            cluster_size = 1 << blkszbits
            logger.debug(f"EROFS cluster size from {img_path}: {cluster_size}")
            return cluster_size

    except (OSError, IOError) as e:
        logger.warning(f"Failed to read EROFS superblock from {img_path}: {e}")
        return None


def detect_cluster_size(
    vendor_dir: Path,
    original_img: Optional[Path] = None,
    force_size: Optional[int] = None
) -> int:
    """Detect appropriate cluster size for EROFS image.

    Priority order:
    1. User force specified (force_size)
    2. From original image (read_erofs_cluster_size)
    3. Estimate by directory size:
       - < 1GB: 4096
       - 1-3GB: 16384
       - > 3GB: 65536

    Args:
        vendor_dir: Path to vendor directory.
        original_img: Optional path to original EROFS image to read cluster size from.
        force_size: Optional forced cluster size to use.

    Returns:
        Detected or specified cluster size in bytes.
    """
    # Priority 1: User force specified
    if force_size is not None:
        logger.info(f"Using forced cluster size: {force_size}")
        return force_size

    # Priority 2: From original image
    if original_img is not None and original_img.exists():
        cluster_size = read_erofs_cluster_size(original_img)
        if cluster_size is not None:
            logger.info(f"Using cluster size from original image: {cluster_size}")
            return cluster_size

    # Priority 3: Estimate by directory size
    dir_size = get_dir_size(vendor_dir)
    size_gb = dir_size / (1024 * 1024 * 1024)

    if size_gb < 1:
        cluster_size = 4096
    elif size_gb <= 3:
        cluster_size = 16384
    else:
        cluster_size = 65536

    logger.info(f"Estimated cluster size based on directory size ({size_gb:.2f} GB): {cluster_size}")
    return cluster_size


class ErofsPacker:
    """Packs a vendor directory into an EROFS image.

    This class handles the creation of EROFS images from a vendor directory,
    using mkfs.erofs tool with appropriate settings for Android vendor partitions.
    """

    def __init__(self, vendor_dir: Path):
        """Initialize the EROFS packer.

        Args:
            vendor_dir: Path to the vendor directory to pack.
        """
        self.vendor_dir = vendor_dir
        self.shell = ShellRunner()

    def _get_mkfs_erofs_path(self) -> Optional[Path]:
        """Get mkfs.erofs tool path using ShellRunner's binary discovery.

        ShellRunner searches in order:
        1. bin/{os}/{arch}/ (platform-specific tools)
        2. otatools/bin/ (Google OTA tools)
        3. bin/ (common tools)
        4. System PATH

        Returns:
            Path to mkfs.erofs if found, None otherwise.
        """
        return self.shell.get_binary_path("mkfs.erofs")

    def check_prerequisites(self) -> bool:
        """Verify that all prerequisites are met for packing.

        Returns:
            True if vendor_dir exists and mkfs_erofs is available, False otherwise.
        """
        # Check vendor directory exists
        if not self.vendor_dir.exists():
            logger.error(f"Vendor directory does not exist: {self.vendor_dir}")
            return False

        if not self.vendor_dir.is_dir():
            logger.error(f"Vendor path is not a directory: {self.vendor_dir}")
            return False

        # Check mkfs.erofs is available (ShellRunner handles discovery)
        mkfs_path = self.shell.get_binary_path("mkfs.erofs")
        if not mkfs_path.exists():
            logger.error("mkfs.erofs tool not found")
            return False

        logger.debug(f"Prerequisites check passed, mkfs.erofs: {mkfs_path}")
        return True

    def pack(
        self,
        output_path: Path,
        cluster_size: int = 16384,
        fs_config: Optional[Path] = None,
        file_contexts: Optional[Path] = None
    ) -> bool:
        """Pack the vendor directory into an EROFS image.

        Args:
            output_path: Path for the output EROFS image.
            cluster_size: Cluster size in bytes (default: 16384).
            fs_config: Optional path to fs_config file for file permissions.
            file_contexts: Optional path to file_contexts for SELinux labels.

        Returns:
            True if packing succeeded, False otherwise.
        """
        # Verify prerequisites
        if not self.check_prerequisites():
            return False

        # Build mkfs.erofs command (ShellRunner will resolve mkfs.erofs path)
        cmd = [
            "mkfs.erofs",
            "-zlz4hc,9",  # LZ4HC compression, level 9
            "-T", "1230768000",  # Fixed timestamp (2009-01-01)
            f"-C{cluster_size}",  # Cluster size
            "--mount-point", "/vendor",  # Mount point for Android
        ]

        # Add optional fs_config file
        if fs_config is not None and fs_config.exists():
            cmd.extend(["--fs-config-file", str(fs_config)])

        # Add optional file_contexts
        if file_contexts is not None and file_contexts.exists():
            cmd.extend(["--file-contexts", str(file_contexts)])

        # Add output path and source directory
        cmd.extend([str(output_path), str(self.vendor_dir)])

        logger.info(f"Packing EROFS image: {output_path}")
        logger.debug(f"Cluster size: {cluster_size}")

        try:
            # Run mkfs.erofs via ShellRunner (handles binary discovery and cross-platform)
            self.shell.run(cmd, check=True, capture_output=True)

            if output_path.exists():
                size_mb = output_path.stat().st_size / (1024 * 1024)
                logger.info(f"Generated: {output_path} ({size_mb:.2f} MB)")
                return True
            else:
                logger.error("Packing completed but output file does not exist")
                return False

        except subprocess.CalledProcessError as e:
            logger.error(f"mkfs.erofs failed with return code {e.returncode}")
            if e.stderr:
                logger.error(f"stderr: {e.stderr}")
            if e.stdout:
                logger.error(f"stdout: {e.stdout}")
            return False
        except Exception as e:
            logger.error(f"Failed to run mkfs.erofs: {e}")
            return False
