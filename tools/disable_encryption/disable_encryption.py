#!/usr/bin/env python3
"""CLI entry point for disable_encryption tool."""

import argparse
import logging
import sys
from pathlib import Path

from .fstab_parser import FstabParser
from .erofs_packer import ErofsPacker, detect_cluster_size


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


def print_guide(vendor_img_path: Path) -> None:
    """Print the flashing guide for the user."""
    print("=" * 40)
    print("Data 加密禁用完成")
    print("=" * 40)
    print()
    print(f"生成的 vendor.img: {vendor_img_path}")
    print()
    print("接下来的步骤:")
    print("1. 进入 fastbootd 模式:")
    print("   adb reboot bootloader")
    print("   fastboot reboot fastboot")
    print()
    print("2. 刷入修改后的 vendor 镜像:")
    print(f"   fastboot update-super vendor {vendor_img_path}")
    print("   (注意: 使用 update-super 而非 flash)")
    print()
    print("3. 关闭 vbmeta 校验:")
    print("   fastboot flash vbmeta vbmeta.img")
    print("   fastboot flash vbmeta_system vbmeta_system.img")
    print("   或使用禁用验证:")
    print("   fastboot --disable-verity flash vbmeta vbmeta.img")
    print()
    print("4. 擦除 userdata 分区 (会清除所有用户数据):")
    print("   fastboot erase userdata")
    print("   fastboot erase metadata")
    print()
    print("5. 重启设备:")
    print("   fastboot reboot")
    print()
    print("注意:")
    print("- 此操作会清除所有用户数据")
    print("- 重启后 data 分区将不再加密")
    print("- 部分应用可能拒绝工作(如银行、支付应用)")


def main() -> int:
    """Main entry point."""
    args = parse_args()
    logger = setup_logging(args.verbose)

    # 1. Validate input
    if not args.vendor_dir.exists():
        logger.error(f"错误: vendor 目录不存在: {args.vendor_dir}")
        return 1

    if not args.vendor_dir.is_dir():
        logger.error(f"错误: {args.vendor_dir} 不是目录")
        return 1

    logger.info("=" * 50)
    logger.info("Data 加密禁用工具")
    logger.info("=" * 50)

    # 2. Parse fstab
    logger.info("")
    logger.info("正在分析 fstab 文件...")
    parser = FstabParser(args.vendor_dir, logger)

    fstab_files = parser.find_fstab_files()
    if not fstab_files:
        logger.warning("未找到 fstab 文件")
        logger.warning(f"请检查 {args.vendor_dir}/etc/ 目录")
        return 1

    logger.info(f"找到 {len(fstab_files)} 个 fstab 文件:")
    for fstab in fstab_files:
        logger.info(f"  - {fstab.relative_to(args.vendor_dir)}")

    modifications = parser.analyze_all()
    if not modifications:
        logger.info("")
        logger.info("未发现加密选项，无需修改")
        return 0

    logger.info(f"发现 {len(modifications)} 处加密配置:")
    for mod in modifications:
        logger.info(f"  - {mod.fstab_path.relative_to(args.vendor_dir)}: {', '.join(mod.removed_options)}")

    # 3. Apply modifications
    logger.info("")
    if args.dry_run:
        logger.info("[DRY-RUN] 预览修改内容:")
        modified_count = parser.apply_modifications(dry_run=True)
        logger.info("")
        logger.info(f"[DRY-RUN] 将修改 {modified_count} 个文件")
        return 0
    else:
        logger.info("正在应用修改...")
        modified_count = parser.apply_modifications(dry_run=False)
        logger.info(f"已修改 {modified_count} 个文件")

    # 4. Pack vendor.img
    logger.info("")
    logger.info("正在打包 vendor.img...")

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        output_path = args.vendor_dir.parent / "vendor.img"

    # Detect cluster size
    cluster_size = detect_cluster_size(
        vendor_dir=args.vendor_dir,
        force_size=args.cluster_size if args.force_cluster else None
    )
    logger.info(f"使用簇大小: {cluster_size}")

    # Create packer and pack
    packer = ErofsPacker(args.vendor_dir)

    if not packer.check_prerequisites():
        logger.error("打包前提条件未满足")
        return 1

    # Look for fs_config and file_contexts
    fs_config = args.vendor_dir / "etc" / "fs_config"
    file_contexts = args.vendor_dir / "etc" / "file_contexts"

    success = packer.pack(
        output_path=output_path,
        cluster_size=cluster_size,
        fs_config=fs_config if fs_config.exists() else None,
        file_contexts=file_contexts if file_contexts.exists() else None
    )

    if not success:
        logger.error("打包 vendor.img 失败")
        return 1

    logger.info(f"成功生成: {output_path}")

    # 5. Print guide
    logger.info("")
    print_guide(output_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
