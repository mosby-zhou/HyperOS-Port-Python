# ROM 精简流程 - 代码模块调用链路分析

## 概述

本文档分析了 slim-rom skill 的完整调用链路，以及每一步使用的 Linux 二进制工具。

**核心结论**: 整个流程确实可以用纯 Shell 脚本完成，Python 代码主要提供了：
1. 跨平台支持 (Linux/macOS/Windows)
2. 并行处理优化
3. 自动 ROM 类型检测
4. 配置文件管理
5. 更友好的错误处理和日志

---

## 完整调用链路

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Phase 1: 解包 ROM (需要 sudo)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  main.py                                                                    │
│    └── RomPackage.extract_images()                                          │
│          ├── RomType 检测 (PAYLOAD/BROTLI/FASTBOOT/LOCAL_DIR)               │
│          └── 根据类型调用不同 extractor                                       │
│                ├── PAYLOAD → extract_payload()                              │
│                │     └── payload-dumper                                     │
│                ├── BROTLI → extract_brotli()                                │
│                │     ├── brotli (解压)                                       │
│                │     └── sdat2img.py (Python 纯代码转换)                      │
│                └── FASTBOOT → extract_fastboot()                            │
│                      ├── simg2img (sparse → raw)                            │
│                      ├── lpunpack (解包 super.img)                          │
│                      └── extract.erofs (解包 EROFS 文件系统)                  │
│                                                                             │
│  RomPackage.extract_partition_to_file()                                     │
│    └── extract.erofs (解包各分区到文件系统)                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                         Phase 2: 删除应用 (Agent 自动)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│  无需 Python 代码介入，直接操作系统文件                                         │
│    ├── rm -rf build/target/product/app/<应用名>                              │
│    └── rm -rf build/target/product/priv-app/<应用名>                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                         Phase 3: 更新配置 (Agent 自动)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│  fspatch.py (patch_fs_config)                                               │
│    └── 纯 Python 代码，更新 fs_config 文件                                    │
│                                                                             │
│  contextpatch.py (ContextPatcher.patch)                                     │
│    └── 纯 Python 代码，更新 file_contexts 文件                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                         Phase 4: 重新打包                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  Repacker.pack_all()                                                        │
│    ├── fspatch.py (更新 fs_config)                                          │
│    ├── contextpatch.py (更新 file_contexts)                                 │
│    └── 根据文件系统类型调用:                                                   │
│          ├── EROFS: mkfs.erofs                                              │
│          └── EXT4:  mke2fs + e2fsdroid + resize2fs + tune2fs               │
│                                                                             │
│  Repacker.pack_super_image()                                                │
│    ├── lpmake (打包 super.img)                                              │
│    └── zstd (压缩 super.zst)                                                │
│                                                                             │
│  或 Repacker.pack_ota_payload()                                             │
│    └── ota_from_target_files (打包 OTA 包)                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 详细步骤与二进制工具

### Phase 1: 解包 ROM

#### Step 1.1: 初始化工作目录
```bash
# Python: main.py (参数解析 + clean_work_dir)
rm -rf build/
mkdir -p build/
```

#### Step 1.2: 检测 ROM 类型
```python
# Python: RomPackage._detect_type() - 纯 Python 代码
# 检测逻辑:
#   - payload.bin 存在 → PAYLOAD
#   - *.new.dat.br 存在 → BROTLI
#   - super.img 存在 → FASTBOOT
#   - 目录 → LOCAL_DIR
```

#### Step 1.3: 提取镜像文件

**PAYLOAD 类型** (OTA 升级包):
```bash
# Python: extract_payload() 调用
bin/linux/x86_64/payload-dumper --out build/stockrom/images <ROM.zip>
```
- **工具**: `payload-dumper` (C++ 编译的二进制)
- **功能**: 从 payload.bin 提取所有分区镜像

**BROTLI 类型** (老式 ROM):
```bash
# Python: extract_brotli() 调用
# 1. 解压 brotli 文件
bin/linux/x86_64/brotli -d -f system.new.dat.br -o system.new.dat

# 2. 转换 dat → img (纯 Python 代码: sdat2img.py)
python3 src/utils/sdat2img.py system.transfer.list system.new.dat system.img
```
- **工具**: `brotli`
- **功能**: 解压 brotli 压缩的数据文件

**FASTBOOT 类型** (线刷包):
```bash
# Python: extract_fastboot() 调用
# 1. 转换 sparse → raw (如果是 sparse 格式)
bin/linux/x86_64/simg2img super.img super_raw.img

# 2. 解包 super.img
bin/linux/x86_64/lpunpack super_raw.img build/stockrom/images/
# 或 Python 实现
python3 src/utils/lpunpack.py super_raw.img build/stockrom/images/
```
- **工具**: `simg2img` - Android sparse 镜像转换
- **工具**: `lpunpack` - Linux 动态分区解包工具

#### Step 1.4: 解包 EROFS 文件系统
```bash
# Python: RomPackage.extract_partition_to_file() 调用
bin/linux/x86_64/extract.erofs -x -i build/target/product_a.img -o build/target/
```
- **工具**: `extract.erofs`
- **功能**: 解包 EROFS 只读文件系统到目录

---

### Phase 2: 删除应用

```bash
# 纯 Shell 操作，无需 Python
rm -rf build/target/product/product_a/data-app/<应用名>
rm -rf build/target/product/product_a/app/<应用名>
rm -rf build/target/product/product_a/priv-app/<应用名>
```

---

### Phase 3: 更新配置文件

#### fs_config 更新
```python
# Python: fspatch.py (纯 Python 代码，无外部工具)
# 功能: 扫描文件系统，更新 fs_config 配置
# 操作: 读取目录结构 → 计算 uid/gid/mode → 写入配置文件
```

#### file_contexts 更新
```python
# Python: contextpatch.py (纯 Python 代码，无外部工具)
# 功能: 扫描文件系统，更新 SELinux 上下文配置
# 操作: 读取目录结构 → 匹配 SELinux 标签 → 写入配置文件
```

---

### Phase 4: 重新打包

#### Step 4.1: 打包分区镜像

**EROFS 格式**:
```bash
# Python: Repacker._pack_erofs() 调用
mkfs.erofs -zlz4hc,9 -T 1230768000 \
  --mount-point /product \
  --fs-config-file build/target/config/product_fs_config \
  --file-contexts build/target/config/product_file_contexts \
  build/target/product.img build/target/product
```
- **工具**: `mkfs.erofs`
- **参数**: `-zlz4hc,9` (LZ4HC 压缩), `-T` (固定时间戳)

**EXT4 格式**:
```bash
# Python: Repacker._pack_ext4() 调用
# 1. 创建 ext4 镜像
mke2fs -O ^has_journal -L product -I 256 -N 5000 -M /product \
  -m 0 -t ext4 -b 4096 product.img <块数>

# 2. 填充文件
e2fsdroid -e -T 1230768000 -C product_fs_config -S product_file_contexts \
  -f product -a /product product.img

# 3. 优化大小
resize2fs -f -M product.img

# 4. 检查空闲块
tune2fs -l product.img
```
- **工具**: `mke2fs` - 创建 ext2/3/4 文件系统
- **工具**: `e2fsdroid` - Android ext4 文件填充工具
- **工具**: `resize2fs` - 调整 ext4 文件系统大小
- **工具**: `tune2fs` - 查看/调整 ext4 参数

#### Step 4.2: 打包 super.img

```bash
# Python: Repacker.pack_super_image() 调用
otatools/bin/lpmake \
  --metadata-size 65536 \
  --super-name super \
  --block-size 4096 \
  --device super:<大小> \
  --metadata-slots 3 \
  --virtual-ab \
  --group qti_dynamic_partitions_a:<大小> \
  --group qti_dynamic_partitions_b:<大小> \
  --partition product_a:none:<大小>:qti_dynamic_partitions_a \
  --image product_a=build/target/product.img \
  --partition system_a:none:<大小>:qti_dynamic_partitions_a \
  --image system_a=build/target/system.img \
  ... \
  --output build/target/super.img

# 压缩 (可选)
zstd --rm build/target/super.img -o build/target/super.zst
```
- **工具**: `lpmake` - Linux 动态分区打包工具
- **工具**: `zstd` - 高效压缩工具

#### Step 4.3: 打包 OTA Payload (可选)

```bash
# Python: Repacker.pack_ota_payload() 调用
otatools/bin/ota_from_target_files -v -k otatools/security/testkey \
  out/target/product/<设备代号> output.zip
```
- **工具**: `ota_from_target_files` - AOSP OTA 打包工具

---

## 所有使用的二进制工具汇总

### 核心工具 (bin/linux/x86_64/)

| 工具 | 用途 | 阶段 |
|------|------|------|
| `payload-dumper` | 提取 payload.bin 中的分区镜像 | Phase 1 |
| `brotli` | 解压 brotli 压缩文件 | Phase 1 |
| `simg2img` | sparse 镜像转 raw 镜像 | Phase 1 |
| `lpunpack` | 解包 super.img 动态分区 | Phase 1 |
| `extract.erofs` | 解包 EROFS 文件系统 | Phase 1 |
| `mkfs.erofs` | 创建 EROFS 镜像 | Phase 4 |
| `mke2fs` | 创建 ext4 文件系统 | Phase 4 |
| `e2fsdroid` | Android ext4 填充工具 | Phase 4 |
| `resize2fs` | 调整 ext4 大小 | Phase 4 |
| `tune2fs` | 查看 ext4 参数 | Phase 4 |
| `aapt2` | 解析 APK 包名 | Phase 3 (可选) |
| `magiskboot` | 处理 boot.img | Phase 4 (可选) |

### OTA 工具 (otatools/bin/)

| 工具 | 用途 | 阶段 |
|------|------|------|
| `lpmake` | 打包 super.img | Phase 4 |
| `ota_from_target_files` | 打包 OTA 升级包 | Phase 4 |
| `img2simg` | raw 转 sparse 镜像 | Phase 4 (可选) |
| `avbtool` | AVB 签名工具 | Phase 4 (可选) |

### 系统工具

| 工具 | 用途 | 阶段 |
|------|------|------|
| `cp` | 复制文件/目录 | Phase 1, 4 |
| `rm` | 删除文件/目录 | Phase 2 |
| `chown` | 修改文件所有者 | Phase 1 |
| `zstd` | 压缩 super.img | Phase 4 |
| `du` | 计算目录大小 | Phase 4 |
| `zip` | 打包最终输出 | Phase 4 |

---

## Python 代码的实际价值

### 确实可以简化的部分

1. **文件删除操作**: 纯 Shell `rm -rf` 即可
2. **配置文件更新**: 可用 `sed`/`awk` 替代
3. **目录复制**: 纯 Shell `cp -a` 即可

### Python 提供的额外价值

1. **跨平台支持**
   - `ShellRunner` 自动检测 OS 和架构
   - 自动选择正确的二进制路径
   - Windows/macOS/Linux 统一接口

2. **ROM 类型自动检测**
   - 自动识别 PAYLOAD/BROTLI/FASTBOOT/LOCAL_DIR
   - 根据类型选择正确的解包流程

3. **并行处理**
   - `ThreadPoolExecutor` 并行解包/打包多个分区
   - 显著提升处理速度

4. **配置管理**
   - YAML 配置文件支持设备特定参数
   - 自动加载设备配置 (super_size, ksu 等)

5. **错误处理**
   - 统一的日志系统
   - 详细的错误追踪
   - 进度显示

6. **代码复用**
   - Modifier 系统支持扩展
   - 插件架构

---

## Shell 脚本等效实现

如果只需要精简 ROM 功能，以下是等效的 Shell 脚本:

```bash
#!/bin/bash
# minimal_slim_rom.sh - 最小化 ROM 精简脚本

ROM_DIR="$1"
APPS_TO_DELETE="$2"  # 逗号分隔的应用名列表

set -e

# Phase 1: 解包
echo "=== Phase 1: 解包 ROM ==="
BIN="bin/linux/x86_64"

# 转换 sparse → raw
sudo $BIN/simg2img $ROM_DIR/super.img $ROM_DIR/super_raw.img

# 解包 super.img
sudo python3 src/utils/lpunpack.py $ROM_DIR/super_raw.img build/target/

# 解包 EROFS 分区
for part in product_a system_a vendor_a system_ext_a odm_a mi_ext_a; do
    img="build/target/${part}.img"
    [ -f "$img" ] && sudo $BIN/extract.erofs -x -i "$img" -o build/target/
done

# 修正权限
sudo chown -R $USER:$USER build/target/

# Phase 2: 删除应用
echo "=== Phase 2: 删除应用 ==="
for app in ${APPS_TO_DELETE//,/ }; do
    find build/target -type d -name "*$app*" -exec rm -rf {} + 2>/dev/null || true
done

# Phase 3: 更新配置 (需要 Python 辅助)
echo "=== Phase 3: 更新配置 ==="
python3 -c "
from src.utils.fspatch import patch_fs_config
from src.utils.contextpatch import ContextPatcher
from pathlib import Path

for part in ['product', 'system', 'vendor', 'system_ext']:
    src = Path(f'build/target/{part}')
    fs = Path(f'build/target/config/{part}_fs_config')
    fc = Path(f'build/target/config/{part}_file_contexts')
    if src.exists():
        if fs.exists(): patch_fs_config(src, fs)
        if fc.exists(): ContextPatcher().patch(src, fc)
"

# Phase 4: 打包
echo "=== Phase 4: 重新打包 ==="
for part in product system vendor system_ext odm mi_ext; do
    src="build/target/${part}"
    [ -d "$src" ] || continue

    $BIN/mkfs.erofs -zlz4hc,9 -T 1230768000 \
        --mount-point /$part \
        --fs-config-file build/target/config/${part}_fs_config \
        --file-contexts build/target/config/${part}_file_contexts \
        build/target/${part}.img "$src"
done

# 打包 super.img
otatools/bin/lpmake --metadata-size 65536 --super-name super --block-size 4096 \
    --device super:9126805504 --metadata-slots 3 --virtual-ab \
    --group qti_dynamic_partitions_a:9126805504 \
    --group qti_dynamic_partitions_b:9126805504 \
    $(for part in product system vendor system_ext odm mi_ext; do
        img="build/target/${part}.img"
        [ -f "$img" ] || continue
        size=$(stat -c%s "$img")
        echo "--partition ${part}_a:none:$size:qti_dynamic_partitions_a"
        echo "--image ${part}_a=$img"
        echo "--partition ${part}_b:none:0:qti_dynamic_partitions_b"
    done) \
    --output build/target/super.img

echo "完成! 输出: build/target/super.img"
```

---

## 结论

**Python 代码的必要性**:

| 功能 | Shell 可行 | Python 必要 |
|------|-----------|-------------|
| 解包/打包操作 | ✅ | ❌ |
| 文件删除 | ✅ | ❌ |
| 简单配置更新 | ✅ | ❌ |
| ROM 类型检测 | ⚠️ (复杂) | ✅ |
| 跨平台支持 | ❌ | ✅ |
| 并行处理 | ⚠️ (GNU parallel) | ✅ |
| 复杂配置管理 | ❌ | ✅ |
| 插件系统 | ❌ | ✅ |

**对于精简 ROM 这个特定场景**，纯 Shell 脚本完全可以完成，但 Python 代码提供了更好的:
- 可维护性
- 可扩展性
- 用户体验
- 错误处理

如果只需要一个简单的精简工具，Shell 脚本足够；如果需要完整的 ROM 移植工具链，Python 代码是有价值的。
