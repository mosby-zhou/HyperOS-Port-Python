# 小米 12S 线刷包精简操作流程

本文档用于指导如何使用 HyperOS-Port-Python 工具对小米 12S (mayfly) 线刷包进行精简处理。

---

## 一、准备工作

### 1.1 环境要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Linux (推荐 Ubuntu 20.04+) |
| Python | 3.8+ |
| 磁盘空间 | 50GB+ 可用空间 |
| 内存 | 8GB+ (推荐 16GB) |
| 权限 | sudo 权限 |

### 1.2 安装依赖

```bash
cd /home/zhouc/code/2026/HyperOS-Port-Python
pip install -r requirements.txt
```

### 1.3 准备文件

将小米 12S 线刷包放置到指定目录，例如：
```
/home/zhouc/roms/mayfly_hyperos_xxx.tgz
```

---

## 二、操作流程

### 步骤 1: 解包 ROM

使用官改模式解包线刷包：

```bash
cd /home/zhouc/code/2026/HyperOS-Port-Python

sudo python3 main.py \
    --stock /path/to/mayfly_hyperos_xxx.tgz \
    --pack-type super \
    --clean \
    --phases system
```

**参数说明**:
- `--stock`: 线刷包路径 (支持 .tgz / .zip / 目录)
- `--pack-type super`: 生成线刷格式的 super.img
- `--clean`: 清理旧的工作目录
- `--phases system`: 仅执行系统级处理，跳过 APK 修改

**预期输出**:
```
build/target/
├── system/          # 系统分区
├── product/         # 产品分区 (预装应用主要在此)
├── vendor/          # 厂商分区
├── system_ext/      # 系统扩展分区
├── mi_ext/          # MIUI 扩展分区
├── config/          # 配置文件
└── repack_images/   # 固件镜像 (boot, vbmeta 等)
```

---

### 步骤 2: 定位并删除内置应用

#### 2.1 应用位置速查

| 分区 | 路径 | 内容 |
|------|------|------|
| **product** | `product/app/` | 系统应用 |
| **product** | `product/priv-app/` | 特权应用 |
| **product** | `product/preinstall/` | 预装第三方应用 |
| **system** | `system/app/` | 核心系统应用 |
| **system** | `system/priv-app/` | 核心特权应用 |
| **system_ext** | `system_ext/app/` | 系统扩展应用 |
| **mi_ext** | `mi_ext/app/` | MIUI 特有应用 |

#### 2.2 删除应用示例

假设要删除以下应用:
- `product/app/MiBrowser` (小米浏览器)
- `product/priv-app/Music` (音乐)
- `product/preinstall/SoGouInput` (搜狗输入法)

```bash
# 进入工作目录
cd /home/zhouc/code/2026/HyperOS-Port-Python/build/target

# 删除应用目录
sudo rm -rf product/app/MiBrowser
sudo rm -rf product/priv-app/Music
sudo rm -rf product/preinstall/SoGouInput

# 同步删除对应的 odex/vdex 缓存 (如果存在)
sudo rm -rf system/system/app/MiBrowser
sudo rm -rf system/system/priv-app/Music
```

#### 2.3 查找应用方法

**按包名查找**:
```bash
# 查找特定包名的应用
find build/target -type d -name "*Browser*"
find build/target -type d -name "*Music*"
```

**按 APK 名称查找**:
```bash
# 列出所有 APK
find build/target -name "*.apk" | sort
```

---

### 步骤 3: 同步更新配置文件

删除应用后，需要更新对应的配置文件：

#### 3.1 更新 fs_config

```bash
# 从 fs_config 中移除已删除应用的条目
# 文件位置: build/target/config/product_fs_config

# 编辑文件
sudo nano build/target/config/product_fs_config
```

**格式示例**:
```
# 删除类似以下行:
product/app/MiBrowser 0 0 755
product/app/MiBrowser/MiBrowser.apk 0 0 644
```

#### 3.2 更新 file_contexts

```bash
# 从 file_contexts 中移除已删除应用的 SELinux 上下文
# 文件位置: build/target/config/product_file_contexts

# 编辑文件
sudo nano build/target/config/product_file_contexts
```

---

### 步骤 4: 重新打包

执行重新打包流程：

```bash
cd /home/zhouc/code/2026/HyperOS-Port-Python

sudo python3 main.py \
    --stock /path/to/mayfly_hyperos_xxx.tgz \
    --pack-type super \
    --phases repack
```

**预期输出**:
```
out/
└── mayfly-hybrid-<version>-<timestamp>.zip
    ├── super.zst              # 压缩的系统分区 (精简后)
    ├── boot.img               # 启动镜像
    ├── firmware-update/       # 固件文件
    │   ├── vbmeta.img
    │   ├── dtbo.img
    │   └── ...
    ├── windows_flash_script.bat
    ├── mac_linux_flash_script.sh
    └── META-INF/
```

---

## 三、快捷操作 (推荐)

### 一键流程脚本

创建脚本 `slim_mayfly.sh`:

```bash
#!/bin/bash
set -e

PROJECT_DIR="/home/zhouc/code/2026/HyperOS-Port-Python"
ROM_PATH="$1"
APPS_TO_DELETE="$2"

if [ -z "$ROM_PATH" ]; then
    echo "用法: ./slim_mayfly.sh <线刷包路径> [应用列表文件]"
    exit 1
fi

cd "$PROJECT_DIR"

echo "=== 步骤 1: 解包 ROM ==="
sudo python3 main.py --stock "$ROM_PATH" --pack-type super --clean --phases system

echo "=== 步骤 2: 删除应用 ==="
if [ -f "$APPS_TO_DELETE" ]; then
    while IFS= read -r app_path; do
        [ -z "$app_path" ] && continue
        [[ "$app_path" == \#* ]] && continue
        echo "删除: $app_path"
        sudo rm -rf "build/target/$app_path"
    done < "$APPS_TO_DELETE"
fi

echo "=== 步骤 3: 重新打包 ==="
sudo python3 main.py --stock "$ROM_PATH" --pack-type super --phases repack

echo "=== 完成! ==="
echo "输出文件: out/mayfly-hybrid-*.zip"
ls -lh out/mayfly-hybrid-*.zip
```

**应用列表文件格式** (`apps_to_delete.txt`):
```
# 格式: 相对于 build/target/ 的路径
product/app/MiBrowser
product/priv-app/Music
product/preinstall/SoGouInput
system/app/SomeApp
```

**使用方法**:
```bash
chmod +x slim_mayfly.sh
./slim_mayfly.sh /path/to/mayfly.tgz apps_to_delete.txt
```

---

## 四、刷入方法

### 4.1 Fastboot 模式 (推荐)

```bash
# 解压输出包
unzip mayfly-hybrid-*.zip -d flash_package
cd flash_package

# 如果存在 super.zst，先解压
zstd -d super.zst -o super.img

# 设备进入 Fastboot 模式
# 然后执行刷入脚本
./mac_linux_flash_script.sh
```

### 4.2 Recovery 模式

直接将 ZIP 包传入手机，在 Recovery 中选择刷入。

---

## 五、注意事项

### 5.1 不要删除的关键应用

| 应用 | 原因 |
|------|------|
| `com.android.systemui` | 系统界面，删除会导致无法启动 |
| `com.android.settings` | 设置应用 |
| `com.miui.home` | 桌面启动器 |
| `com.android.phone` | 电话服务 |
| `com.android.providers.*` | 系统提供者 |
| `com.miui.securitycenter` | 安全中心 (可能导致功能异常) |

### 5.2 删除后可能的问题

1. **系统更新失败**: 删除系统应用可能导致 OTA 校验失败
2. **功能异常**: 部分应用被其他应用依赖
3. **启动卡顿**: 系统可能等待已删除的服务

### 5.3 建议保留的应用

- 核心系统服务 (`com.android.*`)
- MIUI 核心组件 (`com.miui.core`, `com.miui.system`)
- 电话/SMS 相关

---

## 六、故障排查

### 6.1 打包失败

```bash
# 检查磁盘空间
df -h build/

# 检查文件权限
ls -la build/target/product/

# 使用 ext4 格式重新打包
sudo python3 main.py --stock mayfly.tgz --pack-type super --fs-type ext4 --phases repack
```

### 6.2 刷入后无法启动

```bash
# 可能原因:
# 1. 删除了关键系统应用
# 2. SELinux 上下文不正确

# 解决方法: 重新刷入原始线刷包恢复
```

---

## 七、附录

### A. 小米 12S 分区大小

| 分区 | 大小 |
|------|------|
| super | 9663676416 字节 (~9GB) |
| boot | ~64MB |
| dtbo | ~8MB |

### B. 常见预装应用路径

```
product/app/
├── MiBrowser          # 小米浏览器
├── MiuiVideo          # 小米视频
├── Music              # 音乐
├── Notes              # 便签
├── PhotoMovie         # 瞄片
└── ...

product/priv-app/
├── Mipay              # 小米支付
├── MiuiGallery        # 相册
├── MiuiScanner        # 扫一扫
├── SecurityCenter     # 安全中心
└── ...

product/preinstall/
├── SoGouInput         # 搜狗输入法 (如有)
├── ...                # 其他预装应用
```

---

**文档版本**: 1.0
**适用机型**: 小米 12S (mayfly)
**最后更新**: 2026-03-17
