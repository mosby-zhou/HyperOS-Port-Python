# HyperOS-Port-Python 安全风险分析报告

**文档版本**: 2.0
**分析日期**: 2026-03-18
**风险等级**: 极高

---

## 重要声明

**本文档第一版存在严重错误：低风险的评估是基于工具名称的假设，并未实际验证任何工具的来源。**

**实际情况：所有工具都没有签名验证，无法确认是否来自官方。**

---

## 一、核心安全问题

### 1.1 没有任何工具来源验证

项目中所有二进制工具和 JAR 文件：

- 无法确认是否来自官方
- 没有存储 SHA256 校验和
- 没有运行时完整性检查
- 可能已被替换为恶意版本

### 1.2 网络下载无签名验证

KernelSU 等组件从网络下载后：

- 不验证数字签名
- 直接注入到启动镜像
- 如果下载源被入侵 → 用户设备被完全控制

---

## 二、每个工具的详细使用分析

### 2.1 `payload-dumper` - 极高风险

**位置**: `bin/linux/x86_64/payload-dumper`

**代码调用位置**:

- 文件: `src/core/rom/extractors.py`
- 行号: 25

```python
cmd = ["payload-dumper", "--out", str(package.images_dir)]
cmd.append(str(package.path))  # 用户提供的 ROM 文件
package.shell.run(cmd)
```

**功能说明**:

- 解包 `payload.bin` 格式的 ROM 包
- 提取所有分区镜像 (system, vendor, product, boot 等)
- 是 ROM 处理流程的第一步

**风险分析**:
| 风险点 | 说明 |
|--------|------|
| 处理用户输入 | 直接处理用户提供的 ROM 文件 |
| 无来源验证 | 不知道这个二进制从哪里来 |
| 可执行任意代码 | 如果被替换，可在解包时植入恶意代码 |
| 影响范围 | 所有从该工具解包的镜像都不可信 |

**官方来源**: https://github.com/ssut/payload-dumper-go/releases

---

### 2.2 `magiskboot` - 极高风险

**位置**: `bin/linux/x86_64/magiskboot`

**代码调用位置**:

| 文件                   | 行号    | 操作                     |
| ---------------------- | ------- | ------------------------ |
| `firmware_modifier.py` | 110     | 解包 vendor_boot.img     |
| `firmware_modifier.py` | 126     | 解压缩 ramdisk           |
| `firmware_modifier.py` | 155     | cpio extract 操作        |
| `firmware_modifier.py` | 184     | 添加文件到 cpio          |
| `firmware_modifier.py` | 203     | DTB patch                |
| `firmware_modifier.py` | 222     | repack vendor_boot       |
| `firmware_modifier.py` | 334     | 解包 boot.img 分析 KMI   |
| `firmware_modifier.py` | 454     | 解包 init_boot 注入 KSU  |
| `firmware_modifier.py` | 463-495 | KSU 注入完整流程         |
| `wild_boost.py`        | 85      | 解包 boot.img            |
| `wild_boost.py`        | 204-363 | vendor_boot 完整操作流程 |

**功能说明**:

- 解包/打包 boot.img, vendor_boot.img, init_boot.img
- 操作 ramdisk.cpio (启动脚本和模块)
- 注入 KernelSU 到启动镜像
- 修改 fstab 禁用 AVB 验证

**风险分析**:
| 风险点 | 说明 |
|--------|------|
| 操作启动镜像 | 直接修改设备启动流程 |
| 注入内核模块 | KernelSU 注入点 |
| 最高权限 | boot.img 被修改后可获得 root 权限 |
| 无验证 | 如果被替换，完全控制用户设备 |

**官方来源**: https://github.com/topjohnwu/Magisk/releases (从 Magisk APK 中提取)

---

### 2.3 `lpunpack` - 高风险

**位置**: `bin/linux/x86_64/lpunpack`

**代码调用位置**:

- 文件: `src/core/rom/extractors.py`
- 行号: 166, 180, 190

```python
# 解包指定分区
cmd = ["lpunpack", "-p", part, str(super_img), str(package.images_dir)]
package.shell.run(cmd)

# 解包全部分区
package.shell.run(["lpunpack", str(super_img), str(package.images_dir)])
```

**功能说明**:

- 解包 super.img 逻辑分区
- 提取 system, vendor, product, odm 等分区

**风险分析**:
| 风险点 | 说明 |
|--------|------|
| 解包系统分区 | 提取所有关键分区 |
| 备用方案 | 失败时有 Python 实现 `src/utils/lpunpack.py` |

**官方来源**: AOSP 源码编译

---

### 2.4 `brotli` - 高风险

**位置**: `bin/linux/x86_64/brotli`

**代码调用位置**:

- 文件: `src/core/rom/extractors.py`
- 行号: 88

```python
cmd = ["brotli", "-d", "-f", str(br_file), "-o", str(new_dat)]
package.shell.run(cmd)
```

**功能说明**:

- 解压 `.new.dat.br` 文件
- 老版本 ROM 使用此格式

**风险分析**:

- 解压的数据最终会转换为系统镜像
- 如果被替换，可注入恶意数据

**官方来源**: https://github.com/google/brotli/releases

---

### 2.5 `mkfs.erofs` - 高风险

**位置**: `bin/linux/x86_64/mkfs.erofs`

**代码调用位置**:

- 文件: `src/core/packer.py`
- 行号: 102-117

```python
cmd = [
    "mkfs.erofs",
    "-zlz4hc,9",
    "-T", self.fix_timestamp,
    "--mount-point", f"/{part_name}",
    "--fs-config-file", str(fs_config),
    "--file-contexts", str(file_contexts),
    str(img_output),
    str(src_dir),
]
self.shell.run(cmd)
```

**功能说明**:

- 将目录打包为 EROFS 格式镜像
- 用于打包 system, vendor, product 等分区

**风险分析**:
| 风险点 | 说明 |
|--------|------|
| 生成刷机镜像 | 最终刷入用户设备的内容由此生成 |
| 可注入文件 | 如果被替换，可在分区中注入任意文件 |
| SELinux 配置 | 设置文件安全上下文 |

**官方来源**: https://github.com/erofs/erofs-utils

---

### 2.6 `mke2fs` + `e2fsdroid` - 高风险

**位置**: `bin/linux/x86_64/mke2fs`, `bin/linux/x86_64/e2fsdroid`

**代码调用位置**:

- 文件: `src/core/packer.py`
- 行号: 195-235

```python
# 创建 EXT4 文件系统
mkfs_cmd = [
    "mke2fs", "-O", "^has_journal", "-L", part_name,
    "-I", "256", "-N", str(inodes), "-M", f"/{part_name}",
    "-m", "0", "-t", "ext4", "-b", "4096",
    str(img_path), str(size // 4096),
]
self.shell.run(mkfs_cmd)

# 写入文件和权限
e2fs_cmd = [
    "e2fsdroid", "-e", "-T", self.fix_timestamp,
    "-C", str(fs_config), "-S", str(file_contexts),
    "-f", str(src_dir), "-a", f"/{part_name}",
    str(img_path),
]
self.shell.run(e2fs_cmd)
```

**功能说明**:

- 创建 EXT4 格式镜像
- 写入文件内容、权限、SELinux 标签

**风险分析**:

- 可在系统分区注入任意文件
- 可设置任意权限和 SELinux 上下文

**官方来源**: e2fsprogs 项目, AOSP

---

### 2.7 `simg2img` - 中风险

**位置**: `bin/linux/x86_64/simg2img`

**代码调用位置**:

- 文件: `src/core/rom/utils.py`
- 行号: 65, 77, 91

```python
# 合并稀疏镜像块
cmd = [str(simg2img_bin)] + [str(c) for c in super_chunks] + [str(target_super)]
shell.run(cmd)

# 转换单个稀疏镜像
shell.run([str(simg2img_bin), str(target_super), str(temp_raw)])
```

**功能说明**:

- 转换稀疏镜像 (sparse image) 为原始镜像
- 合并分片的镜像文件

**风险分析**:

- 只做格式转换，不修改内容
- 风险相对较低，但仍需验证来源

**官方来源**: AOSP

---

### 2.8 `aapt2` - 中风险

**位置**: `bin/linux/x86_64/aapt2`

**代码调用位置**:

- 文件: `src/core/context.py`
- 行号: 455-467

```python
cmd = [str(self.tools.aapt2), "dump", "packagename", str(apk_path)]
result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=5)
return result.stdout.strip()  # 返回 APK 包名
```

**功能说明**:

- 解析 APK 包名
- 用于 APK 查找缓存

**风险分析**:

- 只读取信息，不修改文件
- 如果被替换，可能返回错误的包名
- 可能导致错误的 APK 被修改

**官方来源**: Android SDK Build Tools

---

### 2.9 `lpmake` - 高风险

**位置**: `otatools/bin/lpmake`

**代码调用位置**:

- 文件: `src/core/packer.py`
- 行号: 265-356

```python
lpmake_path = self.ota_tools_dir / "bin" / "lpmake"
base_args = [
    str(lpmake_path),
    "--metadata-size", "65536",
    "--super-name", "super",
    "--block-size", "4096",
    "--device", f"super:{super_size}",
    "--output", str(super_img),
    # ... 分区定义
]
self.shell.run(base_args)
```

**功能说明**:

- 打包 super.img
- 定义动态分区布局

**风险分析**:

- 决定所有动态分区的布局和大小
- 可篡改分区元数据

**官方来源**: AOSP otatools

---

### 2.10 JAR 工具 - 高风险

#### APKEditor.jar

**位置**: `bin/APKEditor.jar`

**代码调用位置**:

- 文件: `src/core/modifiers/plugins/apk/base.py`
- 行号: 223, 254

```python
# 反编译 APK
self.ctx.shell.run_java_jar(
    ["-jar", str(apkeditor_jar), "d", "-i", str(apk_path), "-o", str(output_dir)]
)

# 重编译 APK
self.ctx.shell.run_java_jar(
    ["-jar", str(apkeditor_jar), "b", "-i", str(input_dir), "-o", str(output_apk)]
)
```

#### apktool.jar

**位置**: `bin/apktool/apktool_2.12.1.jar`

**代码调用位置**:

- 文件: `src/core/modifiers/framework/base.py`
- 行号: 43, 49

#### smali.jar / baksmali.jar

**位置**: `bin/smali.jar`, `bin/baksmali.jar`

**功能说明**:

- 反编译/重编译 APK
- 修改 APK 内的 smali 代码
- 修改 resources.arsc

**风险分析**:
| 风险点 | 说明 |
|--------|------|
| 修改系统 APK | 可注入恶意代码到 Settings、SecurityCenter 等 |
| 无签名验证 | 重编译后的 APK 签名可能被绕过 |
| Java 执行环境 | 可执行任意 Java 代码 |

**官方来源**:

- APKEditor: https://github.com/REAndroid/APKEditor/releases
- apktool: https://github.com/iBotPeaches/Apktool/releases
- smali/baksmali: https://github.com/JesusFreke/smali/releases

---

## 三、网络下载风险 - 极高风险

### 3.1 KernelSU 下载

**代码调用位置**:

- 文件: `src/core/modifiers/firmware_modifier.py`
- 行号: 404-425

```python
api_url = self.ksu_config_url_template.format(
    owner=self.repo_owner, repo=self.repo_name
)
with urllib.request.urlopen(api_url, timeout=10) as resp:
    data = json.loads(resp.read().decode())

assets = data.get("assets", [])
for asset in assets:
    name = asset["name"]
    url = asset["browser_download_url"]
    # 下载 ksuinit 和 kernelsu.ko
    self._download_file(url, target_init)
    self._download_file(url, target_ko)
```

**功能说明**:

- 从 GitHub API 获取最新版本
- 下载 `ksuinit` 和 `kernelsu.ko`
- 直接注入到 boot.img 或 init_boot.img

**风险分析**:
| 风险点 | 说明 |
|--------|------|
| 无签名验证 | 下载的文件不验证签名 |
| 中间人攻击 | HTTP 可能被劫持 |
| 供应链攻击 | GitHub 仓库可能被入侵 |
| 直接注入 | 下载的内容写入启动镜像 |
| 完全控制 | 恶意 KSU 可完全控制设备 |

**攻击链**:

```
攻击者控制下载源/中间人攻击
    → 注入恶意 kernelsu.ko
    → 用户刷入修改后的 ROM
    → 设备被完全控制
    → 攻击者获得 root 权限
```

**官方来源**: https://github.com/tiann/KernelSU/releases (必须验证签名!)

---

### 3.2 otatools 下载

**代码调用位置**:

- 文件: `src/utils/otatools_manager.py`
- 行号: 12

```python
DEFAULT_URL = "https://github.com/toraidl/HyperOS-Port-Python/releases/download/assets/otatools.zip"
```

**风险分析**:

- otatools 包含大量二进制工具
- 这些工具会被直接执行
- URL 指向项目自身 Release

---

## 四、设备配置文件风险

### 4.1 预打包资源

**位置**: `devices/common/`

| 文件                  | 内容                | 风险                |
| --------------------- | ------------------- | ------------------- |
| `PropsHook.zip`       | APK，注入系统       | 高 - 可执行任意代码 |
| `wild_boost_5.10.zip` | 内核模块            | 高 - 内核级权限     |
| `wild_boost_5.15.zip` | 内核模块            | 高 - 内核级权限     |
| `pif_patch.zip`       | Play Integrity 补丁 | 中 - 修改系统属性   |
| `pif_patch_v2.zip`    | Play Integrity 补丁 | 中                  |
| `xeutoolbox.zip`      | 工具包              | 中 - 需验证来源     |
| `otacerts.zip`        | 证书文件            | 中                  |

---

## 五、数据流与注入点分析

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ROM 处理数据流                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  [用户 ROM 文件]                                                             │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 解包阶段                                                              │   │
│  │ ┌─────────────┐  ┌──────────────┐  ┌─────────────┐                   │   │
│  │ │payload-dumper│  │ lpunpack     │  │ brotli      │                   │   │
│  │ │ 🔴 极高风险  │  │ 🔴 高风险    │  │ 🔴 高风险   │                   │   │
│  │ └─────────────┘  └──────────────┘  └─────────────┘                   │   │
│  │       ↓                ↓                 ↓                            │   │
│  │      [提取的分区镜像: system.img, vendor.img, boot.img 等]             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 修改阶段                                                              │   │
│  │ ┌─────────────┐  ┌──────────────┐  ┌─────────────┐                   │   │
│  │ │ APKEditor   │  │ apktool      │  │ magiskboot  │                   │   │
│  │ │ 🔴 高风险   │  │ 🔴 高风险    │  │ 🔴 极高风险 │                   │   │
│  │ └─────────────┘  └──────────────┘  └─────────────┘                   │   │
│  │       ↓                ↓                 ↓                            │   │
│  │      [修改后的 APK, 注入的 KSU, 修改的 boot.img]                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 网络下载 (无验证)                                                     │   │
│  │ ┌─────────────────────────────────────────────────────────────────┐ │   │
│  │ │ KernelSU 下载 → ksuinit + kernelsu.ko → 注入 boot.img            │ │   │
│  │ │ 🔴 极高风险 - 无签名验证，直接注入启动镜像                          │ │   │
│  │ └─────────────────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 打包阶段                                                              │   │
│  │ ┌─────────────┐  ┌──────────────┐  ┌─────────────┐                   │   │
│  │ │mkfs.erofs   │  │ mke2fs/      │  │ lpmake      │                   │   │
│  │ │ 🔴 高风险   │  │ e2fsdroid    │  │ 🔴 高风险   │                   │   │
│  │ │             │  │ 🔴 高风险    │  │             │                   │   │
│  │ └─────────────┘  └──────────────┘  └─────────────┘                   │   │
│  │       ↓                ↓                 ↓                            │   │
│  │      [最终的刷机包: super.img, boot.img, OTA zip]                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                     │
│       ▼                                                                     │
│  [用户设备] ← 🔴 最终风险承载者                                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 六、风险等级汇总

| 工具/资源          | 风险等级 | 处理内容              | 官方来源               |
| ------------------ | -------- | --------------------- | ---------------------- |
| `payload-dumper`   | 🔴 极高  | 整个 ROM 解包         | ssut/payload-dumper-go |
| `magiskboot`       | 🔴 极高  | 启动镜像操作          | topjohnwu/Magisk       |
| `KernelSU`         | 🔴 极高  | 网络下载+注入启动镜像 | tiann/KernelSU         |
| `lpunpack`         | 🔴 高    | 系统分区解包          | AOSP                   |
| `brotli`           | 🔴 高    | 镜像数据解压          | google/brotli          |
| `mkfs.erofs`       | 🔴 高    | 系统分区打包          | erofs/erofs-utils      |
| `mke2fs`           | 🔴 高    | EXT4 创建             | e2fsprogs              |
| `e2fsdroid`        | 🔴 高    | EXT4 写入             | AOSP                   |
| `lpmake`           | 🔴 高    | super.img 打包        | AOSP otatools          |
| `APKEditor.jar`    | 🔴 高    | APK 修改              | REAndroid/APKEditor    |
| `apktool.jar`      | 🔴 高    | APK 反编译            | iBotPeaches/Apktool    |
| `smali.jar`        | 🔴 高    | Smali 汇编            | JesusFreke/smali       |
| `baksmali.jar`     | 🔴 高    | Smali 反汇编          | JesusFreke/smali       |
| `wild_boost_*.zip` | 🔴 高    | 内核模块              | 需验证来源             |
| `PropsHook.zip`    | 🔴 高    | 系统 APK              | 需验证来源             |
| `simg2img`         | ⚠️ 中    | 格式转换              | AOSP                   |
| `aapt2`            | ⚠️ 中    | 信息读取              | Android SDK            |
| `pif_patch*.zip`   | ⚠️ 中    | 属性修改              | 需验证来源             |

---

## 七、官方工具下载地址

### 7.1 二进制工具

```bash
# magiskboot - 从 Magisk APK 提取
# https://github.com/topjohnwu/Magisk/releases
# 下载 Magisk-*.apk，解压后提取 lib/*/libmagiskboot.so

# payload-dumper-go
https://github.com/ssut/payload-dumper-go/releases

# brotli
https://github.com/google/brotli/releases

# erofs-utils (mkfs.erofs, extract.erofs)
https://github.com/erofs/erofs-utils

# e2fsprogs (mke2fs, e2fsdroid)
https://sourceforge.net/projects/e2fsprogs/
# 或从 AOSP 编译

# Android SDK (aapt2)
https://developer.android.com/studio#command-tools

# AOSP 工具 (lpunpack, lpmake, simg2img)
# 需要从 AOSP 源码编译或从官方 otatools 提取
https://source.android.com/docs/setup
```

### 7.2 JAR 工具

```bash
# APKEditor
https://github.com/REAndroid/APKEditor/releases

# Apktool
https://github.com/iBotPeaches/Apktool/releases

# smali/baksmali
https://github.com/JesusFreke/smali/releases
```

### 7.3 可下载资源

```bash
# KernelSU (必须验证签名!)
https://github.com/tiann/KernelSU/releases

# 注意：KernelSU 发布包含 .sig 签名文件
# 下载后必须验证签名
```

---

## 八、缓解措施

### 8.1 立即行动

1. **重新下载所有工具**
   - 从上述官方地址下载
   - 记录每个文件的 SHA256 校验和
   - 删除项目中现有的未验证工具

2. **验证 JAR 文件**

   ```bash
   # 示例：验证 apktool
   sha256sum bin/apktool/apktool_2.12.1.jar
   # 与 GitHub Release 中的校验和对比
   ```

3. **验证 KernelSU**
   - 下载官方 Release
   - 验证 `.sig` 签名文件
   - 不要让程序自动下载

### 8.2 代码改进建议

#### 添加工具校验配置

```python
# 建议添加到配置文件
TOOL_CHECKSUMS = {
    "magiskboot": "expected_sha256_here",
    "payload-dumper": "expected_sha256_here",
    "APKEditor.jar": "expected_sha256_here",
    "apktool.jar": "expected_sha256_here",
    # ...
}

def verify_tool_integrity(tool_path: Path, expected_hash: str) -> bool:
    """验证工具完整性"""
    actual = hashlib.sha256(tool_path.read_bytes()).hexdigest()
    return actual == expected_hash
```

#### 添加启动时检查

```python
def startup_security_check():
    """启动时验证所有关键工具"""
    failures = []
    for tool_name, expected_hash in TOOL_CHECKSUMS.items():
        tool_path = get_tool_path(tool_name)
        if not tool_path.exists():
            failures.append(f"{tool_name}: 不存在")
        elif not verify_tool_integrity(tool_path, expected_hash):
            failures.append(f"{tool_name}: 校验失败，可能被篡改")

    if failures:
        raise SecurityError(f"工具完整性检查失败:\n" + "\n".join(failures))
```

#### KernelSU 下载签名验证

```python
def download_ksu_with_verification():
    """带签名验证的 KernelSU 下载"""
    # 1. 下载文件和签名
    # 2. 使用 GPG 或 minisign 验证
    # 3. 验证通过后才使用
    pass
```

### 8.3 用户安全建议

1. **隔离环境运行**
   - 使用虚拟机
   - 不要在生产环境直接运行

2. **网络控制**
   - 首次运行时禁用网络
   - 手动下载所有需要的资源

3. **验证输出**
   - 检查生成的镜像大小是否合理
   - 在测试设备上验证后再用于主力设备

---

## 九、结论

### 9.1 风险总结

本项目存在 **极高的安全风险**，主要原因：

1. **所有工具来源未知** - 无法确认是否来自官方
2. **无完整性验证** - 没有 SHA256 校验
3. **网络下载无签名** - KernelSU 直接下载注入
4. **高权限操作** - 操作启动镜像和系统分区

### 9.2 风险后果

如果任何工具被替换为恶意版本：

- 用户设备可被完全控制
- 可安装持久化后门
- 可窃取所有数据
- 可监控所有通信

### 9.3 建议行动优先级

| 优先级   | 行动                                |
| -------- | ----------------------------------- |
| **立即** | 从官方重新下载所有工具并验证 SHA256 |
| **立即** | 禁用自动网络下载功能                |
| **短期** | 添加工具完整性校验代码              |
| **中期** | 实现 KernelSU 签名验证              |
| **长期** | 建立自动化安全审计流程              |

---

**免责声明**: 本文档仅用于安全分析目的。用户应自行评估风险并采取适当防护措施。本文档不构成任何形式的安全保证。
