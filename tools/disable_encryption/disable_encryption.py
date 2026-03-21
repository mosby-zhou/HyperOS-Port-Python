#!/usr/bin/env python3
"""CLI entry point for disable_encryption tool."""

import argparse
import logging
import sys
from pathlib import Path

# Lazy imports - modules will be created in subsequent tasks
# Import only when needed to allow CLI framework to work independently


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
    )
    return logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="禁用 Android FBE 加密的命令行工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 禁用加密
  python -m tools.disable_encryption.disable_encryption --vendor-dir build/target/vendor

  # 预览修改 (dry-run)
  python -m tools.disable_encryption.disable_encryption --vendor-dir build/target/vendor --dry-run

  # 强制指定簇大小
  python -m tools.disable_encryption.disable_encryption --vendor-dir build/target/vendor --cluster-size 32768 --force-cluster
""",
    )

    parser.add_argument(
        "--vendor-dir",
        type=Path,
        required=True,
        help="vendor 目录路径 (必需)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="输出 vendor.img 路径 (可选，默认覆盖原文件)",
    )
    parser.add_argument(
        "--cluster-size",
        type=int,
        help="EROFS 簇大小 (可选，默认自动检测)",
    )
    parser.add_argument(
        "--force-cluster",
        action="store_true",
        help="强制使用指定的簇大小，不进行自动检测",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只显示将要修改的内容，不实际执行",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="显示详细输出",
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_args()
    logger = setup_logging(args.verbose)

    # Validate input
    if not args.vendor_dir.exists():
        logger.error(f"错误: vendor 目录不存在: {args.vendor_dir}")
        return 1

    if not args.vendor_dir.is_dir():
        logger.error(f"错误: {args.vendor_dir} 不是目录")
        return 1

    logger.info("=" * 50)
    logger.info("Data 加密禁用工具")
    logger.info("=" * 50)

    # TODO: Implement main logic in subsequent tasks
    logger.info("CLI 框架已就绪")
    return 0


if __name__ == "__main__":
    sys.exit(main())
