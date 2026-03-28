# Official Tools Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将所有二进制工具调用改为从 `bin/offical/` 目录获取，找不到时直接报错中断。

**Architecture:** 修改 `ShellRunner.get_binary_path()` 方法和 `PortingContext._init_tools()` 方法，添加严格的工具存在性检查，移除所有 fallback 到系统 PATH 的逻辑。

**Tech Stack:** Python 3.8+, pathlib

---

## 文件结构

### 需要修改的文件

| 文件 | 职责 |
|------|------|
| `src/utils/shell.py` | 核心二进制工具查找逻辑 |
| `src/core/context.py` | 工具路径初始化 |
| `src/core/packer.py` | 多处直接调用工具（lpmake, resize2fs, tune2fs 等） |
| `src/core/rom/extractors.py` | payload-dumper, brotli, lpunpack 调用 |
| `src/core/rom/utils.py` | simg2img 查找逻辑 |

### 目录结构

```
bin/
├── offical/                    # 官方工具目录（优先）
│   └── linux/x86_64/
│       ├── aapt2
│       ├── brotli
│       ├── e2fsdroid
│       ├── extract.erofs
│       ├── lpunpack
│       ├── magiskboot
│       ├── mke2fs
│       ├── mkfs.erofs
│       ├── payload-dumper
│       ├── simg2img
│       ├── android-lptools-static-x86_64/
│       │   ├── lpmake
│       │   └── ...
│       └── lib64/
│           └── libc++.so
├── linux/x86_64/               # 旧的工具目录（兼容）
├── apktool/
└── *.jar
```

---

## Task 1: 修改 ShellRunner 工具查找逻辑

**Files:**
- Modify: `src/utils/shell.py`

- [ ] **Step 1: 添加官方工具目录常量和错误类**

```python
# 在文件开头添加
from typing import List, Union, Optional, Callable

class ToolNotFoundError(Exception):
    """当找不到必要的二进制工具时抛出"""
    pass

class ShellRunner:
    # 添加官方工具目录常量
    OFFICIAL_BIN_DIR = "offical"  # 注意拼写保持一致

    def __init__(self):
        # ... 现有代码 ...

        # 添加官方工具目录路径
        self.official_bin_dir = project_root / "bin" / self.OFFICIAL_BIN_DIR / self.os_name / self.arch
```

- [ ] **Step 2: 重写 get_binary_path 方法**

```python
def get_binary_path(self, tool_name: str, required: bool = True) -> Path:
    """
    Get the absolute path of the tool.

    Search Order:
    1. bin/offical/{os}/{arch}/ (Official tools - highest priority)
    2. bin/{os}/{arch}/ (Platform specific tools)
    3. bin/offical/{os}/{arch}/android-lptools-static-*/ (lptools)
    4. otatools/bin/ (Google OTA tools)

    Args:
        tool_name: Name of the binary tool
        required: If True, raises ToolNotFoundError when tool not found.
                  If False, returns Path(tool_name) as fallback.

    Returns:
        Path to the tool binary

    Raises:
        ToolNotFoundError: When required=True and tool is not found
    """
    # 1. Official tools directory (highest priority)
    official_path = self.official_bin_dir / tool_name
    if official_path.exists():
        return official_path

    # 2. Check android-lptools-static subdirectory (lpmake, lpunpack, etc.)
    lptools_dirs = list(self.official_bin_dir.glob("android-lptools-static-*"))
    for lptools_dir in lptools_dirs:
        lptools_path = lptools_dir / tool_name
        if lptools_path.exists():
            return lptools_path

    # 3. Platform specific bin directory (legacy)
    bin_path = self.bin_dir / tool_name
    if bin_path.exists():
        return bin_path

    # 4. OTATools
    ota_path = self.otatools_bin / tool_name
    if ota_path.exists():
        return ota_path

    # 5. Tool not found
    if required:
        raise ToolNotFoundError(
            f"Required binary tool '{tool_name}' not found!\n"
            f"Searched locations:\n"
            f"  - {self.official_bin_dir}/{tool_name}\n"
            f"  - {self.official_bin_dir}/android-lptools-static-*/{tool_name}\n"
            f"  - {self.bin_dir}/{tool_name}\n"
            f"  - {self.otatools_bin}/{tool_name}\n"
            f"Please download the official tool and place it in bin/offical/{self.os_name}/{self.arch}/"
        )

    # Fallback for non-required tools
    return Path(tool_name)
```

- [ ] **Step 3: 更新 run 方法使用 required 参数**

```python
def run(self, cmd: Union[str, List[str]], cwd: Optional[Path] = None,
        check: bool = True, capture_output: bool = False,
        env: Optional[dict] = None, logger: Optional[logging.Logger] = None,
        on_line: Optional[Callable[[str], None]] = None,
        shell: bool = False, tool_required: bool = True) -> subprocess.CompletedProcess:
    """
    Core method to execute commands

    :param tool_required: If True, raise ToolNotFoundError when binary not found
    """
    # Binary search logic (skipped if shell=True and cmd is a string)
    if not shell and isinstance(cmd, list):
        tool = cmd[0]
        tool_path = self.get_binary_path(tool, required=tool_required)
        if tool_path.is_absolute() and tool_path.exists():
            cmd[0] = str(tool_path)
            if not os.access(tool_path, os.X_OK):
                os.chmod(tool_path, 0o755)
    # ... 其余代码保持不变 ...
```

- [ ] **Step 4: 运行测试验证改动**

Run: `python3 -c "from src.utils.shell import ShellRunner; s = ShellRunner(); print(s.get_binary_path('magiskboot'))"`

Expected: 输出 `/home/zhouc/code/2026/HyperOS-Port-Python/bin/offical/linux/x86_64/magiskboot` 或抛出 ToolNotFoundError

- [ ] **Step 5: Commit**

```bash
git add src/utils/shell.py
git commit -m "feat(shell): add ToolNotFoundError and prioritize bin/offical directory"
```

---

## Task 2: 更新 PortingContext 工具初始化

**Files:**
- Modify: `src/core/context.py`

- [ ] **Step 1: 修改 _init_tools 方法使用官方目录**

```python
def _init_tools(self) -> None:
    """
    Auto-detect system environment and set global tool paths.
    """
    system: str = platform.system().lower()
    machine: str = platform.machine().lower()

    # 1. Unify architecture name
    if machine in ["amd64", "x86_64"]:
        arch: str = "x86_64"
    elif machine in ["aarch64", "arm64"]:
        arch = "arm64"
    else:
        arch = "x86_64"

    # 2. Determine platform directory and extension
    if system == "windows":
        plat_dir: str = "windows"
        exe_ext: str = ".exe"
    elif system == "linux":
        plat_dir = "linux"
        exe_ext = ""
    elif system == "darwin":
        plat_dir = "macos"
        exe_ext = ""
    else:
        self.logger.warning(f"Unknown system: {system}, defaulting to Linux.")
        plat_dir = "linux"
        exe_ext = ""

    # 3. Set official binary directory (primary)
    self.official_bin_dir: Path = self.bin_root / "offical" / plat_dir / arch
    self.platform_bin_dir: Path = self.official_bin_dir  # Alias for compatibility

    if not self.official_bin_dir.exists():
        self.logger.error(f"Official binary directory not found: {self.official_bin_dir}")
        raise FileNotFoundError(
            f"Official tools directory not found: {self.official_bin_dir}\n"
            f"Please ensure all required tools are placed in bin/offical/{plat_dir}/{arch}/"
        )

    self.logger.info(f"Official Binary Dir: {self.official_bin_dir}")

    # 4. Define global tools (self.tools)
    self.tools: SimpleNamespace = SimpleNamespace()

    # >> Native tools from official directory
    self.tools.magiskboot = self.official_bin_dir / f"magiskboot{exe_ext}"
    self.tools.aapt2 = self.official_bin_dir / f"aapt2{exe_ext}"

    # >> LPTOOLS (may be in subdirectory)
    lptools_dir = self.official_bin_dir / f"android-lptools-static-{arch}"
    if lptools_dir.exists():
        self.tools.lpmake = lptools_dir / "lpmake"
        self.tools.lpunpack = lptools_dir / "lpunpack"
        self.tools.lpdump = lptools_dir / "lpdump"
    else:
        # Fallback to main directory
        self.tools.lpmake = self.official_bin_dir / "lpmake"
        self.tools.lpunpack = self.official_bin_dir / "lpunpack"
        self.tools.lpdump = self.official_bin_dir / "lpdump"

    # >> Java tools (still in bin/)
    self.tools.apktool_jar = self.bin_root / "apktool" / "apktool_2.12.1.jar"
    self.tools.apkeditor_jar = self.bin_root / "APKEditor.jar"

    # 5. Verify critical tools exist
    critical_tools = [
        ("magiskboot", self.tools.magiskboot),
        ("aapt2", self.tools.aapt2),
    ]

    missing_tools = []
    for name, path in critical_tools:
        if not path.exists():
            missing_tools.append(f"{name}: {path}")

    if missing_tools:
        raise FileNotFoundError(
            f"Critical tools not found in {self.official_bin_dir}:\n" +
            "\n".join(f"  - {m}" for m in missing_tools) +
            "\nPlease download missing tools and place them in the official directory."
        )
```

- [ ] **Step 2: 运行测试验证**

Run: `python3 -c "from src.core.context import PortingContext; print('OK')" 2>&1 || echo "Expected error if context needs ROM"`

Expected: 可能需要 ROM 参数，但不应有工具目录相关的错误

- [ ] **Step 3: Commit**

```bash
git add src/core/context.py
git commit -m "feat(context): use official tools directory with strict verification"
```

---

## Task 3: 更新 Packer 中的工具调用

**Files:**
- Modify: `src/core/packer.py`

- [ ] **Step 1: 修改构造函数添加官方目录引用**

```python
def __init__(self, context: Any):
    # ... 现有代码 ...
    self.official_tools_dir: Path = Path("bin/offical").resolve()
```

- [ ] **Step 2: 修改 pack_super_image 中的 lpmake 路径查找**

```python
def pack_super_image(self) -> None:
    """Pack super.img for non-payload.bin ROMs"""
    self.logger.info("Packing super.img...")

    # 使用 ShellRunner 查找 lpmake
    try:
        lpmake_path = self.shell.get_binary_path("lpmake", required=True)
    except Exception as e:
        self.logger.error(f"lpmake not found: {e}")
        raise FileNotFoundError("lpmake binary not found in official tools directory")

    # ... 其余代码使用 lpmake_path ...
```

- [ ] **Step 3: 修改 _get_dir_size 移除对 du 的依赖或标记为可选**

```python
def _get_dir_size(self, path: Path) -> int:
    """Calculate directory size using Python (cross-platform)."""
    try:
        total: int = 0
        for p in path.rglob("*"):
            if p.is_file() and not p.is_symlink():
                total += p.stat().st_size
        return total if total > 0 else 4096
    except Exception as e:
        self.logger.warning(f"Failed to calculate directory size: {e}")
        return 4096
```

- [ ] **Step 4: 修改 _get_free_blocks 使用 tune2fs 从官方目录**

```python
def _get_free_blocks(self, img_path: Path) -> int:
    """Parse tune2fs -l output to get Free blocks"""
    try:
        tune2fs_path = self.shell.get_binary_path("tune2fs", required=False)
        if not tune2fs_path.exists():
            # tune2fs might be in otatools or need system install
            tune2fs_path = Path("tune2fs")  # Fallback to PATH

        output: str = subprocess.check_output(
            [str(tune2fs_path), "-l", str(img_path)],
            text=True
        )
        for line in output.splitlines():
            if "Free blocks:" in line:
                return int(line.split(":")[1].strip())
    except (subprocess.SubprocessError, ValueError, FileNotFoundError):
        pass
    return 0
```

- [ ] **Step 5: Commit**

```bash
git add src/core/packer.py
git commit -m "feat(packer): use official tools directory for binary lookup"
```

---

## Task 4: 更新 ROM Extractors 中的工具调用

**Files:**
- Modify: `src/core/rom/extractors.py`

- [ ] **Step 1: 修改 extract_payload 使用官方 payload-dumper**

```python
def extract_payload(
    package: RomPackage,
    partitions: Optional[List[str]],
) -> None:
    """Extract payload.bin from ROM package."""
    # 使用 ShellRunner 查找 payload-dumper
    payload_dumper = package.shell.get_binary_path("payload-dumper", required=True)

    cmd = [str(payload_dumper), "--out", str(package.images_dir)]

    if partitions:
        package.logger.info(f"[{package.label}] Extracting specific images: {partitions} ...")
        cmd.extend(["--partitions", ",".join(partitions)])
    else:
        package.logger.info(f"[{package.label}] Extracting ALL images (Firmware + Logical) ...")

    cmd.append(str(package.path))
    package.shell.run(cmd)
```

- [ ] **Step 2: 修改 extract_brotli 使用官方 brotli**

```python
def extract_brotli(
    package: RomPackage,
    partitions: Optional[List[str]],
) -> None:
    # ... 现有代码 ...

    # 3. Brotli Decompress
    package.logger.info(f"[{package.label}] Decompressing {br_file.name}...")
    try:
        brotli_bin = package.shell.get_binary_path("brotli", required=True)
        cmd = [str(brotli_bin), "-d", "-f", str(br_file), "-o", str(new_dat)]
        package.shell.run(cmd)
    except Exception as e:
        package.logger.error(f"Brotli decompression failed for {prefix}: {e}")
        continue
    # ... 其余代码 ...
```

- [ ] **Step 3: 修改 extract_fastboot 使用官方 lpunpack**

```python
def extract_fastboot(
    package: RomPackage,
    partitions: Optional[List[str]],
) -> None:
    # ... 现有代码 ...

    # 获取 lpunpack 路径
    try:
        lpunpack_bin = package.shell.get_binary_path("lpunpack", required=True)
    except Exception as e:
        package.logger.error(f"lpunpack not found: {e}")
        raise

    # ... 使用 str(lpunpack_bin) 替换 "lpunpack" ...
    try:
        cmd = [str(lpunpack_bin), "-p", part, str(super_img), str(package.images_dir)]
        package.shell.run(cmd)
    # ... 其余代码 ...
```

- [ ] **Step 4: Commit**

```bash
git add src/core/rom/extractors.py
git commit -m "feat(extractors): use official tools directory for payload-dumper, brotli, lpunpack"
```

---

## Task 5: 更新 ROM Utils 中的 simg2img 查找

**Files:**
- Modify: `src/core/rom/utils.py`

- [ ] **Step 1: 重写 process_sparse_images 使用 ShellRunner**

```python
from src.utils.shell import ShellRunner, ToolNotFoundError

def process_sparse_images(images_dir: Path, logger: logging.Logger, shell: ShellRunner) -> None:
    """Merge/Convert sparse images (super.img.*, cust.img.*) using simg2img."""

    # 使用 ShellRunner 查找 simg2img
    try:
        simg2img_bin = shell.get_binary_path("simg2img", required=True)
        logger.info(f"Using simg2img: {simg2img_bin}")
    except ToolNotFoundError as e:
        logger.error(f"simg2img not found in official tools directory: {e}")
        raise

    # 1. Handle super.img
    super_chunks = sorted(list(images_dir.glob("super.img.*")))
    target_super = images_dir / "super.img"

    if super_chunks:
        logger.info(f"Merging sparse super images: {[c.name for c in super_chunks]}...")
        try:
            cmd = [str(simg2img_bin)] + [str(c) for c in super_chunks] + [str(target_super)]
            shell.run(cmd)
            for c in super_chunks:
                os.unlink(c)
        except Exception as e:
            logger.error(f"Failed to merge super.img: {e}")
            raise

    elif target_super.exists():
        logger.info("converting super.img to raw (if sparse)...")
        temp_raw = images_dir / "super.raw.img"
        try:
            shell.run([str(simg2img_bin), str(target_super), str(temp_raw)])
            shutil.move(temp_raw, target_super)
        except Exception as e:
            logger.warning(f"simg2img conversion skipped/failed: {e}")
            if temp_raw.exists():
                os.unlink(temp_raw)

    # 2. Handle cust.img (same pattern)
    cust_chunks = sorted(list(images_dir.glob("cust.img.*")))
    target_cust = images_dir / "cust.img"

    if cust_chunks:
        logger.info("Merging sparse cust images...")
        try:
            cmd = [str(simg2img_bin)] + [str(c) for c in cust_chunks] + [str(target_cust)]
            shell.run(cmd)
            for c in cust_chunks:
                os.unlink(c)
        except Exception as e:
            logger.error(f"Failed to merge cust.img: {e}")
```

- [ ] **Step 2: Commit**

```bash
git add src/core/rom/utils.py
git commit -m "feat(rom-utils): use ShellRunner for simg2img with strict error"
```

---

## Task 6: 验证与测试

- [ ] **Step 1: 创建测试脚本验证工具查找**

```bash
python3 -c "
from src.utils.shell import ShellRunner, ToolNotFoundError
s = ShellRunner()

tools = ['magiskboot', 'payload-dumper', 'brotli', 'lpunpack', 'simg2img', 'mkfs.erofs', 'mke2fs']
for tool in tools:
    try:
        path = s.get_binary_path(tool, required=True)
        print(f'✓ {tool}: {path}')
    except ToolNotFoundError as e:
        print(f'✗ {tool}: NOT FOUND')
"
```

Expected: 所有工具都应找到并显示路径

- [ ] **Step 2: 测试完整流程**

```bash
# 使用一个测试 ROM 验证完整流程
sudo python3 main.py --stock test_rom.zip --pack-type super --phases system
```

- [ ] **Step 3: 最终 Commit**

```bash
git add -A
git commit -m "feat: integrate official tools directory with strict verification"
```

---

## 总结

### 变更摘要

| 文件 | 变更内容 |
|------|----------|
| `src/utils/shell.py` | 添加 `ToolNotFoundError`，重写 `get_binary_path()`，优先使用 `bin/offical/` |
| `src/core/context.py` | 更新 `_init_tools()` 使用官方目录，添加严格验证 |
| `src/core/packer.py` | 更新工具查找逻辑，使用 `ShellRunner.get_binary_path()` |
| `src/core/rom/extractors.py` | 更新 `payload-dumper`, `brotli`, `lpunpack` 查找 |
| `src/core/rom/utils.py` | 更新 `simg2img` 查找逻辑 |

### 行为变更

1. **工具查找优先级**: `bin/offical/` > `bin/{os}/{arch}/` > `otatools/bin/`
2. **严格模式**: 默认情况下，找不到工具会抛出 `ToolNotFoundError` 异常
3. **错误信息**: 包含详细的搜索路径和解决方案提示

### 兼容性

- 保留 `otatools/bin/` 作为备用查找位置
- JAR 文件仍从 `bin/` 目录加载
- 现有代码通过 `tool_required=False` 参数可以保持旧的行为
