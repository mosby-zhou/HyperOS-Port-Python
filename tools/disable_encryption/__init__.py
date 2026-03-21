"""Disable Data Encryption Tool for Android ROM porting."""

__version__ = "1.0.0"

# Lazy imports - modules will be created in subsequent tasks
# For now, provide stubs to allow package to load
try:
    from .fstab_parser import FstabParser, EncryptionOptions
    from .erofs_packer import ErofsPacker, detect_cluster_size
except ImportError:
    # Modules not yet implemented
    FstabParser = None  # type: ignore
    EncryptionOptions = None  # type: ignore
    ErofsPacker = None  # type: ignore
    detect_cluster_size = None  # type: ignore

__all__ = ["FstabParser", "EncryptionOptions", "ErofsPacker", "detect_cluster_size"]
