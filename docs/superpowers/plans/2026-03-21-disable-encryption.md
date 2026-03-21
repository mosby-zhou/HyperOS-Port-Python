# Disable Encryption Tool 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建独立的命令行工具，用于禁用 Android FBE 加密，修改 vendor fstab 并重新打包。

**Architecture:** 纯 Python 实现，包含 fstab 解析器、EROFS 打包器、CLI 入口三个模块。复用项目现有的 mkfs.erofs 工具和打包逻辑。

**Tech Stack:** Python 3.8+, stdlib (argparse, logging, subprocess, struct), 无外部依赖

---

## 文件结构

```
tools/disable_encryption/
├── __init__.py              # 包初始化
├── disable_encryption.py    # CLI 入口, 主流程编排
├── fstab_parser.py          # fstab 解析和加密选项处理
├── erofs_packer.py          # EROFS 打包逻辑
└── README.md                # 使用说明 (已存在)
```

**依赖关系:**
- `disable_encryption.py` → `fstab_parser.py`, `erofs_packer.py`
- `erofs_packer.py` → `bin/linux/x86_64/mkfs.erofs`
- 独立工具, 不修改现有项目代码

---

## Task 1: 创建包结构和 CLI 框架

**Files:**
- Create: `tools/disable_encryption/__init__.py`
- Create: `tools/disable_encryption/disable_encryption.py`

- [ ] **Step 1: 创建 `__init__.py`**

```python
"""Disable Data Encryption Tool for Android ROM porting."""

__version__ = "1.0.0"

from .fstab_parser import FstabParser, EncryptionOptions
from .erofs_packer import ErofsPacker, detect_cluster_size

__all__ = ["FstabParser", "EncryptionOptions", "ErofsPacker", "detect_cluster_size"]
```

- [ ] **Step 2: 创建 CLI 框架 `disable_encryption.py`**

```python
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
```

- [ ] **Step 3: 测试 CLI 帮助信息**

Run: `cd /home/zhouc/code/2026/HyperOS-Port-Python && python -m tools.disable_encryption.disable_encryption --help`
Expected: 显示帮助信息和使用示例

- [ ] **Step 4: 提交框架代码**

```bash
git add tools/disable_encryption/__init__.py tools/disable_encryption/disable_encryption.py
git commit -m "feat(disable-encryption): add CLI framework with argument parsing"
```

---

## Task 2: 实现 fstab 解析器

**Files:**
- Create: `tools/disable_encryption/fstab_parser.py`

- [ ] **Step 1: 创建 fstab 解析器**

```python
"""Fstab parser for detecting and removing encryption options."""

import re
import shutil
from dataclasses import dataclass, field
from logging import Logger
from pathlib import Path
from typing import List, Optional, Tuple


# 加密相关选项模式
ENCRYPTION_PATTERNS = [
    r"fileencryption=[^\s,]*",
    r"forceencrypt=[^\s,]*",
    r"encryptable[^\s,]*",
]


@dataclass
class EncryptionOptions:
    """存储检测到的加密选项信息."""

    fstab_path: Path
    original_line: str
    modified_line: str
    removed_options: List[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        """是否有实际修改。"""
        return self.original_line != self.modified_line


class FstabParser:
    """解析和修改 fstab 文件中的加密选项。"""

    def __init__(self, vendor_dir: Path, logger: Optional[Logger] = None):
        self.vendor_dir = vendor_dir
        self.logger = logger or Logger(__name__)
        self._fstab_files: List[Path] = []
        self._modifications: List[EncryptionOptions] = []

    def find_fstab_files(self) -> List[Path]:
        """查找 vendor 目录中的所有 fstab 文件。"""
        etc_dir = self.vendor_dir / "etc"

        if not etc_dir.exists():
            self.logger.warning(f"etc 目录不存在: {etc_dir}")
            return []

        # 查找所有 fstab 文件
        found = set()

        # 常见 fstab 文件名
        common_names = ["fstab.qcom", "fstab.postinstall", "fstab.ranchu"]
        for name in common_names:
            fstab_path = etc_dir / name
            if fstab_path.exists():
                found.add(fstab_path)

        # 通配符匹配
        for f in etc_dir.glob("fstab.*"):
            found.add(f)

        self._fstab_files = sorted(found)
        self.logger.info(f"找到 {len(self._fstab_files)} 个 fstab 文件")
        for f in self._fstab_files:
            self.logger.debug(f"  - {f.name}")
        return self._fstab_files

    def parse_line(self, line: str) -> Tuple[str, List[str]]:
        """
        解析 fstab 行，识别并删除加密选项。

        Args:
            line: fstab 中的一行

        Returns:
            (修改后的行, 删除的选项列表)
        """
        stripped = line.strip()

        # 跳过注释和空行
        if not stripped or stripped.startswith("#"):
            return line, []

        removed = []
        modified = line

        for pattern in ENCRYPTION_PATTERNS:
            matches = re.findall(pattern, modified)
            removed.extend(matches)
            modified = re.sub(pattern, "", modified)

        # 清理多余的逗号和空格
        modified = re.sub(r",+", ",", modified)  # 多个逗号变一个
        modified = re.sub(r",\s*,", ",", modified)  # 逗号空格逗号
        modified = re.sub(r"\s+,", " ", modified)  # 空格逗号
        modified = re.sub(r",\s+$", "", modified)  # 行尾逗号
        modified = re.sub(r"\s+", " ", modified)  # 多个空格变一个

        return modified, removed

    def analyze_fstab(self, fstab_path: Path) -> List[EncryptionOptions]:
        """分析单个 fstab 文件，返回所有需要修改的行。"""
        if not fstab_path.exists():
            return []

        modifications = []

        try:
            with open(fstab_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    modified, removed = self.parse_line(line)
                    if removed:
                        mod = EncryptionOptions(
                            fstab_path=fstab_path,
                            original_line=line,
                            modified_line=modified,
                            removed_options=removed,
                        )
                        modifications.append(mod)
        except Exception as e:
            self.logger.error(f"读取 fstab 文件失败 {fstab_path}: {e}")

        return modifications

    def analyze_all(self) -> List[EncryptionOptions]:
        """分析所有 fstab 文件。"""
        if not self._fstab_files:
            self.find_fstab_files()

        all_modifications = []
        for fstab_path in self._fstab_files:
            mods = self.analyze_fstab(fstab_path)
            all_modifications.extend(mods)

        self._modifications = all_modifications
        if all_modifications:
            self.logger.info(f"发现 {len(all_modifications)} 处加密选项需要删除")
        else:
            self.logger.info("未发现加密选项")
        return all_modifications

    def backup_fstab(self, fstab_path: Path) -> Optional[Path]:
        """备份 fstab 文件。"""
        backup_path = fstab_path.with_suffix(fstab_path.suffix + ".bak")
        try:
            shutil.copy2(fstab_path, backup_path)
            self.logger.debug(f"备份: {backup_path}")
            return backup_path
        except Exception as e:
            self.logger.error(f"备份失败: {e}")
            return None

    def apply_modifications(self, dry_run: bool = False) -> int:
        """
        应用所有修改。

        Args:
            dry_run: 如果为 True，只显示修改内容不实际执行

        Returns:
            修改的文件数量
        """
        if not self._modifications:
            self.logger.info("没有需要修改的加密选项")
            return 0

        # 按文件分组
        by_file: dict = {}
        for mod in self._modifications:
            if mod.fstab_path not in by_file:
                by_file[mod.fstab_path] = []
            by_file[mod.fstab_path].append(mod)

        modified_count = 0

        for fstab_path, mods in by_file.items():
            if dry_run:
                self.logger.info(f"\n[DRY-RUN] 将修改: {fstab_path}")
                for mod in mods:
                    for opt in mod.removed_options:
                        self.logger.info(f"  删除: {opt}")
                modified_count += 1
                continue

            # 备份
            self.backup_fstab(fstab_path)

            # 读取原文件
            try:
                with open(fstab_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
            except Exception as e:
                self.logger.error(f"读取文件失败: {e}")
                continue

            # 应用修改
            for mod in mods:
                for i, line in enumerate(lines):
                    if line == mod.original_line:
                        lines[i] = mod.modified_line
                        self.logger.info(f"修改: {fstab_path.name}")
                        for opt in mod.removed_options:
                            self.logger.info(f"  删除: {opt}")

            # 写回文件
            try:
                with open(fstab_path, "w", encoding="utf-8") as f:
                    f.writelines(lines)
                modified_count += 1
            except Exception as e:
                self.logger.error(f"写入文件失败: {e}")

        return modified_count

    @property
    def modifications(self) -> List[EncryptionOptions]:
        """获取所有修改记录。"""
        return self._modifications
```

- [ ] **Step 2: 提交 fstab 解析器**

```bash
git add tools/disable_encryption/fstab_parser.py
git commit -m "feat(disable-encryption): add fstab parser with encryption detection"
```

---

## Task 3: 实现 EROFS 打包器

**Files:**
- Create: `tools/disable_encryption/erofs_packer.py`

- [ ] **Step 1: 创建 EROFS 打包器**

```python
"""EROFS packer for vendor partition."""

import logging
import shutil
import struct
import subprocess
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)


def get_dir_size(path: Path) -> int:
    """计算目录总大小。"""
    total = 0
    try:
        for p in path.rglob("*"):
            if p.is_file() and not p.is_symlink():
                total += p.stat().st_size
    except Exception:
        pass
    return total


def read_erofs_cluster_size(img_path: Path) -> Optional[int]:
    """
    从 EROFS 镜像读取簇大小。

    EROFS superblock 结构:
    - 偏移 1024: superblock 起始
    - 偏移 1024+20: blkszbits (1 byte, log2 of block size)

    Returns:
        簇大小 (bytes) 或 None
    """
    if not img_path.exists():
        return None

    try:
        with open(img_path, "rb") as f:
            # EROFS superblock magic 在偏移 1024
            f.seek(1024)

            # 读取 magic (4 bytes)
            magic = f.read(4)
            if magic != b"\xe2\xe1\xf5\xe0":  # EROFS magic
                logger.debug("不是有效的 EROFS 镜像")
                return None

            # blkszbits 在偏移 16 (相对于 superblock)
            f.seek(1024 + 16)
            blkszbits_byte = f.read(1)
            if blkszbits_byte:
                blkszbits = blkszbits_byte[0]
                cluster_size = 1 << blkszbits  # 2^blkszbits
                logger.debug(f"从镜像读取 blkszbits={blkszbits}, cluster_size={cluster_size}")
                return cluster_size

    except Exception as e:
        logger.debug(f"读取 EROFS 簇大小失败: {e}")

    return None


def detect_cluster_size(
    vendor_dir: Path,
    original_img: Optional[Path] = None,
    force_size: Optional[int] = None,
) -> int:
    """
    检测 EROFS 簇大小。

    优先级:
    1. 用户强制指定
    2. 从原镜像检测
    3. 根据目录大小估算

    Args:
        vendor_dir: vendor 目录路径
        original_img: 原始 vendor.img 路径 (用于检测簇大小)
        force_size: 用户强制指定的簇大小

    Returns:
        簇大小 (bytes)
    """
    # 1. 用户强制指定
    if force_size:
        logger.info(f"使用强制指定的簇大小: {force_size}")
        return force_size

    # 2. 从原镜像检测
    if original_img and original_img.exists():
        cluster_size = read_erofs_cluster_size(original_img)
        if cluster_size:
            logger.info(f"从原镜像检测到簇大小: {cluster_size}")
            return cluster_size

    # 3. 根据目录大小估算
    dir_size = get_dir_size(vendor_dir)
    size_mb = dir_size / (1024 * 1024)
    logger.debug(f"Vendor 目录大小: {size_mb:.2f} MB")

    if dir_size < 1024 * 1024 * 1024:  # < 1GB
        cluster_size = 4096
    elif dir_size < 3 * 1024 * 1024 * 1024:  # < 3GB
        cluster_size = 16384
    else:
        cluster_size = 65536

    logger.info(f"根据目录大小估算簇大小: {cluster_size}")
    return cluster_size


class ErofsPacker:
    """EROFS 镜像打包器。"""

    def __init__(self, vendor_dir: Path):
        self.vendor_dir = vendor_dir
        self.mkfs_erofs = self._find_mkfs_erofs()

    def _find_mkfs_erofs(self) -> Optional[Path]:
        """查找 mkfs.erofs 工具。"""
        # 1. 项目 bin 目录
        candidates = [
            Path("bin/linux/x86_64/mkfs.erofs"),
            Path("bin/mkfs.erofs"),
            Path("bin/linux/mkfs.erofs"),
        ]
        for c in candidates:
            if c.exists():
                logger.debug(f"找到 mkfs.erofs: {c}")
                return c.resolve()

        # 2. 系统 PATH
        mkfs = shutil.which("mkfs.erofs")
        if mkfs:
            return Path(mkfs)

        logger.warning("未找到 mkfs.erofs 工具")
        return None

    def check_prerequisites(self) -> bool:
        """检查打包所需的条件。"""
        if not self.vendor_dir.exists():
            logger.error(f"Vendor 目录不存在: {self.vendor_dir}")
            return False

        if not self.mkfs_erofs:
            logger.error("找不到 mkfs.erofs 工具，无法打包")
            return False

        return True

    def pack(
        self,
        output_path: Path,
        cluster_size: int = 16384,
        fs_config: Optional[Path] = None,
        file_contexts: Optional[Path] = None,
    ) -> bool:
        """
        打包 vendor 目录为 EROFS 镜像。

        Args:
            output_path: 输出镜像路径
            cluster_size: 簇大小
            fs_config: fs_config 文件路径
            file_contexts: file_contexts 文件路径

        Returns:
            True 如果成功
        """
        if not self.mkfs_erofs:
            logger.error("mkfs.erofs 工具不可用")
            return False

        # 构建命令
        cmd = [
            str(self.mkfs_erofs),
            "-zlz4hc,9",
            "-T",
            "1230768000",  # 固定时间戳 (2009-01-01)
            f"-C{cluster_size}",
            "--mount-point",
            "/vendor",
        ]

        # 添加可选参数
        if fs_config and fs_config.exists():
            cmd.extend(["--fs-config-file", str(fs_config)])
            logger.debug(f"使用 fs_config: {fs_config}")

        if file_contexts and file_contexts.exists():
            cmd.extend(["--file-contexts", str(file_contexts)])
            logger.debug(f"使用 file_contexts: {file_contexts}")

        cmd.extend([str(output_path), str(self.vendor_dir)])

        logger.info(f"打包 vendor.img...")
        logger.debug(f"簇大小: {cluster_size}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            if result.stdout:
                logger.debug(result.stdout)

            if output_path.exists():
                size_mb = output_path.stat().st_size / (1024 * 1024)
                logger.info(f"生成: {output_path} ({size_mb:.2f} MB)")
                return True
            else:
                logger.error("打包完成但输出文件不存在")
                return False

        except subprocess.CalledProcessError as e:
            logger.error(f"打包失败: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"打包异常: {e}")
            return False
```

- [ ] **Step 2: 提交 EROFS 打包器**

```bash
git add tools/disable_encryption/erofs_packer.py
git commit -m "feat(disable-encryption): add EROFS packer with auto cluster size detection"
```

---

## Task 4: 整合主流程

**Files:**
- Modify: `tools/disable_encryption/disable_encryption.py`

- [ ] **Step 1: 完善 main 函数**

替换 `disable_encryption.py` 中的 `main` 函数：

```python
def print_guide(vendor_img_path: Path) -> None:
    """打印刷入指南。"""
    guide = f"""
========================================
Data 加密禁用完成
========================================

生成的 vendor.img: {vendor_img_path}

接下来的步骤:
1. 进入 fastbootd 模式:
   adb reboot bootloader
   fastboot reboot fastboot

2. 刷入修改后的 vendor 镜像:
   fastboot update-super vendor {vendor_img_path}
   (注意: 使用 update-super 而非 flash)

3. 关闭 vbmeta 校验:
   fastboot flash vbmeta vbmeta.img
   fastboot flash vbmeta_system vbmeta_system.img

   或使用禁用验证:
   fastboot --disable-verity flash vbmeta vbmeta.img

4. 擦除 userdata 分区 (会清除所有用户数据):
   fastboot erase userdata
   fastboot erase metadata

5. 重启设备:
   fastboot reboot

注意:
- 此操作会清除所有用户数据
- 重启后 data 分区将不再加密
- 部分应用可能拒绝工作(如银行、支付应用)
"""
    print(guide)


def main() -> int:
    """Main entry point."""
    args = parse_args()
    logger = setup_logging(args.verbose)

    # 1. 验证输入
    if not args.vendor_dir.exists():
        logger.error(f"错误: vendor 目录不存在: {args.vendor_dir}")
        return 1

    if not args.vendor_dir.is_dir():
        logger.error(f"错误: {args.vendor_dir} 不是目录")
        return 1

    logger.info("=" * 50)
    logger.info("Data 加密禁用工具")
    logger.info("=" * 50)

    # 2. 解析 fstab
    parser = FstabParser(args.vendor_dir, logger)
    fstab_files = parser.find_fstab_files()

    if not fstab_files:
        logger.warning("未找到 fstab 文件")
        logger.info("提示: 确保 vendor 目录结构正确 (vendor/etc/fstab.*)")
        return 1

    # 3. 分析加密选项
    logger.info("\n[1/3] 分析加密选项...")
    modifications = parser.analyze_all()

    if modifications:
        for mod in modifications:
            for opt in mod.removed_options:
                logger.info(f"  发现: {opt}")

        if args.dry_run:
            logger.info("\n[DRY-RUN] 以下修改将被应用:")
            parser.apply_modifications(dry_run=True)
            logger.info("\n提示: 移除 --dry-run 参数以实际执行修改")
            return 0

        # 4. 应用修改
        logger.info("\n[2/3] 修改 fstab 文件...")
        modified_count = parser.apply_modifications(dry_run=False)
        logger.info(f"修改了 {modified_count} 个文件")
    else:
        logger.info("未发现加密选项 (可能已禁用加密)")
        logger.info("继续打包 vendor.img...")

    # 5. 打包 vendor.img
    logger.info("\n[3/3] 打包 vendor.img...")

    packer = ErofsPacker(args.vendor_dir)

    if not packer.check_prerequisites():
        logger.error("打包条件不满足")
        return 1

    # 确定输出路径
    output_path = args.output or (args.vendor_dir.parent / "vendor.img")

    # 检测簇大小
    cluster_size = detect_cluster_size(
        args.vendor_dir,
        original_img=output_path if output_path.exists() else None,
        force_size=args.cluster_size if args.force_cluster else None,
    )

    # 查找配置文件
    config_dir = args.vendor_dir.parent.parent / "config"
    fs_config = config_dir / "vendor_fs_config"
    file_contexts = config_dir / "vendor_file_contexts"

    success = packer.pack(
        output_path,
        cluster_size=cluster_size,
        fs_config=fs_config if fs_config.exists() else None,
        file_contexts=file_contexts if file_contexts.exists() else None,
    )

    if not success:
        logger.error("打包失败")
        return 1

    # 6. 打印指南
    print_guide(output_path)

    return 0
```

同时更新文件顶部的 import：

```python
from .fstab_parser import FstabParser
from .erofs_packer import ErofsPacker, detect_cluster_size
```

- [ ] **Step 2: 更新 `__init__.py` 导出**

确保 `__init__.py` 正确导出所有模块。

- [ ] **Step 3: 测试完整流程**

Run: `cd /home/zhouc/code/2026/HyperOS-Port-Python && python -m tools.disable_encryption.disable_encryption --help`
Expected: 显示完整帮助信息

- [ ] **Step 4: 提交完整实现**

```bash
git add tools/disable_encryption/disable_encryption.py tools/disable_encryption/__init__.py
git commit -m "feat(disable-encryption): complete main workflow integration"
```

---

## Task 5: 更新文档和最终提交

**Files:**
- Verify: `tools/disable_encryption/README.md`
- Modify: `docs/superpowers/specs/2026-03-21-disable-encryption-design.md`

- [ ] **Step 1: 验证 README.md 内容准确**

确认 README.md 反映实际实现。

- [ ] **Step 2: 更新设计文档状态**

修改设计文档状态为"已实现"：
```markdown
**状态**: 已实现
```

- [ ] **Step 3: 最终提交**

```bash
git add tools/disable_encryption/ docs/superpowers/specs/2026-03-21-disable-encryption-design.md
git commit -m "feat(disable-encryption): implement disable FBE encryption tool

- Add CLI tool for disabling FBE encryption
- Auto-detect cluster size from original image
- Parse and modify fstab encryption options
- Pack vendor.img with EROFS format
- Output flash guide for users

Refs: docs/superpowers/specs/2026-03-21-disable-encryption-design.md"
```

---

## 验证清单

完成所有任务后，执行以下验证：

- [ ] `python -m tools.disable_encryption.disable_encryption --help` 显示帮助
- [ ] `--dry-run` 参数可以预览修改而不实际执行
- [ ] fstab 解析器正确识别 `fileencryption=` 选项
- [ ] 簇大小自动检测逻辑正确 (优先级: 强制指定 > 原镜像 > 估算)
- [ ] 输出指南格式正确
- [ ] README.md 文档完整
- [ ] 设计文档状态已更新
