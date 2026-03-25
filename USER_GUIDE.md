# HyperOS-Port-Python 使用指南

## 1. 环境准备

### 1.1 系统要求

| 项目     | 要求                       |
| -------- | -------------------------- |
| 操作系统 | Linux (推荐 Ubuntu 20.04+) |
| Python   | 3.8+                       |
| 磁盘空间 | 50GB+ 可用空间             |
| 内存     | 8GB+ (推荐 16GB)           |
| 权限     | sudo 权限 (用于挂载镜像)   |

### 1.2 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/yourusername/HyperOS-Port-Python.git
cd HyperOS-Port-Python

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. (可选) 安装开发依赖
pip install -r requirements-dev.txt
```

### 1.3 工具链准备

工具会在首次运行时自动下载 `otatools`，包含所有必要的二进制工具：

```
otatools/
├── bin/           # 可执行文件
│   ├── payload-dumper
│   ├── lpunpack
│   ├── mkfs.erofs
│   └── ...
├── lib64/         # 动态库
└── security/      # 签名密钥
```

---

## 1.3 工具链准备

工具会在首次运行时自动下载 `otatools`，包含所有必要的二进制工具：

```
otatools/
├── bin/           # 可执行文件
│   ├── payload-dumper
│   ├── lpunpack
│   ├── mkfs.erofs
│   └── ...
├── lib64/         # 动态库
└── security/      # 签名密钥
```

如果你 fork 了本项目，需要自行准备工具链，请参考 [第 14 章：工具链获取指南](#14-工具链获取指南)。

---

## 2. 基本使用

### 2.1 标准移植模式

将移植包 ROM 移植到底包设备：

```bash
sudo python3 main.py --stock <底包路径> --port <移植包路径>
```

**示例**:

```bash
# 将小米 14 ROM 移植到小米 13
sudo python3 main.py \
    --stock fuxi_hyperos_2.0.zip \
    --port shennong_hyperos_3.0.zip
```

### 2.2 官改模式

仅修改原厂 ROM，无需移植包：

```bash
sudo python3 main.py --stock <底包路径>
```

**示例**:

```bash
# 官改小米 13 ROM，启用 Wild Boost
sudo python3 main.py --stock fuxi_hyperos_2.0.zip
```

### 2.3 参数详解

| 参数          | 必需 | 默认值  | 说明                                           |
| ------------- | ---- | ------- | ---------------------------------------------- |
| `--stock`     | ✅   | -       | 底包 ROM 路径 (ZIP/目录)                       |
| `--port`      | ❌   | -       | 移植包 ROM 路径。省略则进入官改模式            |
| `--pack-type` | ❌   | payload | 输出格式: `payload` 或 `super`                 |
| `--fs-type`   | ❌   | erofs   | 文件系统: `erofs` 或 `ext4`                    |
| `--ksu`       | ❌   | false   | 注入 KernelSU                                  |
| `--work-dir`  | ❌   | build   | 工作目录                                       |
| `--clean`     | ❌   | false   | 开始前清理工作目录                             |
| `--debug`     | ❌   | false   | 开启调试日志                                   |
| `--eu-bundle` | ❌   | -       | EU 本地化资源包路径                            |
| `--phases`    | ❌   | 全部    | 执行阶段: system,apk,framework,firmware,repack |

---

## 3. 输出格式选择

### 3.1 Payload 模式 (推荐)

适用于 Recovery/OTA 刷入：

```bash
sudo python3 main.py --stock stock.zip --port port.zip --pack-type payload
```

**输出**:

```
out/
└── <device>-ota_full-<version>-<date>-<md5>-<android>.zip
    ├── payload.bin
    └── META-INF/
```

### 3.2 Super 模式

适用于 Fastboot/混合刷入：

```bash
sudo python3 main.py --stock stock.zip --port port.zip --pack-type super
```

**输出**:

```
out/
└── <device>-hybrid-<version>-<date>.zip
    ├── super.zst
    ├── boot.img
    ├── firmware-update/
    └── 刷机脚本
```

---

## 4. 功能配置

### 4.1 启用 Wild Boost

**方法一：设备配置**

编辑 `devices/<device>/config.json`:

```json
{
  "wild_boost": {
    "enable": true
  }
}
```

**方法二：CLI 参数**

Wild Boost 目前需要通过配置文件启用。

### 4.2 启用 KernelSU

**方法一：CLI 参数**

```bash
sudo python3 main.py --stock stock.zip --ksu
```

**方法二：设备配置**

```json
{
  "ksu": {
    "enable": true
  }
}
```

### 4.3 EU 本地化

为 Global/EU 底包恢复中国区功能：

**步骤一：生成 EU Bundle**

```bash
python3 tools/generate_eu_bundle.py \
    --rom CN_ROM.zip \
    --config devices/common/eu_bundle_config.json
```

**步骤二：应用 Bundle**

```bash
sudo python3 main.py \
    --stock EU_ROM.zip \
    --eu-bundle eu_localization_bundle_v1.0.zip
```

---

## 5. 分阶段执行

### 5.1 仅执行特定阶段

```bash
# 仅执行系统级修改
sudo python3 main.py --stock stock.zip --port port.zip --phases system

# 仅执行 APK 修改
sudo python3 main.py --stock stock.zip --port port.zip --phases apk

# 执行多个阶段 (逗号分隔)
sudo python3 main.py --stock stock.zip --phases system,apk

# 仅打包，跳过修改 (假设已有工作目录)
sudo python3 main.py --stock stock.zip --phases repack
```

### 5.2 阶段说明

| 阶段      | 功能                                | 耗时       |
| --------- | ----------------------------------- | ---------- |
| system    | 系统级修改 (Wild Boost, 文件替换等) | 1-3 分钟   |
| apk       | APK 级修改 (Settings, Joyose 等)    | 2-5 分钟   |
| framework | Framework Smali 补丁                | 1-2 分钟   |
| firmware  | 固件修改 (vbmeta, KSU)              | 1-2 分钟   |
| repack    | 镜像打包和生成刷机包                | 10-20 分钟 |

---

## 6. 设备配置

### 6.1 添加新设备支持

**步骤一：创建设备目录**

```bash
mkdir -p devices/<device_code>
```

**步骤二：创建配置文件**

`devices/<device>/config.json`:

```json
{
  "_comment": "<设备名称> 设备配置",
  "wild_boost": {
    "enable": true
  },
  "pack": {
    "type": "payload",
    "fs_type": "erofs",
    "super_size": 9663676416
  },
  "ksu": {
    "enable": false
  }
}
```

`devices/<device>/features.json`:

```json
{
  "xml_features": {
    "support_wild_boost": true
  },
  "build_props": {
    "product": {
      "ro.product.spoofed.name": "<伪装设备>"
    }
  }
}
```

**步骤三：添加覆盖文件 (可选)**

```bash
mkdir -p devices/<device>/override/product/app/MyApp
# 复制需要替换的文件到 override 目录
```

### 6.2 配置文件详解

#### config.json - 设备配置

| 字段                | 类型   | 说明                      |
| ------------------- | ------ | ------------------------- |
| `wild_boost.enable` | bool   | 启用 Wild Boost 性能模块  |
| `pack.type`         | string | 打包类型: payload / super |
| `pack.fs_type`      | string | 文件系统: erofs / ext4    |
| `pack.super_size`   | int    | Super 分区大小 (字节)     |
| `ksu.enable`        | bool   | 启用 KernelSU             |

#### features.json - 功能开关

| 字段                        | 类型   | 说明         |
| --------------------------- | ------ | ------------ |
| `xml_features.*`            | bool   | XML 功能开关 |
| `build_props.<partition>.*` | string | 属性覆盖     |

#### replacements.json - 文件替换

```json
[
  {
    "description": "替换系统 Overlay",
    "type": "file",
    "search_path": "product",
    "files": ["DevicesOverlay.apk"],
    "source": "override/DevicesOverlay.apk"
  }
]
```

---

## 7. 高级用法

### 7.1 使用 URL 下载 ROM

```bash
sudo python3 main.py \
    --stock https://example.com/stock.zip \
    --port https://example.com/port.zip
```

### 7.2 自定义工作目录

```bash
sudo python3 main.py \
    --stock stock.zip \
    --work-dir /mnt/ssd/work \
    --clean
```

### 7.3 调试模式

```bash
sudo python3 main.py --stock stock.zip --debug
```

日志输出到 `porting.log` 和控制台。

### 7.4 增量处理

工具会自动检测源文件变化：

- 如果源 ROM 未变化，使用缓存的镜像
- 使用 `--clean` 强制重新处理

---

## 8. 常见问题排查

### 8.1 工具链问题

**问题**: `payload-dumper: command not found`

**解决**:

```bash
# 检查 otatools 是否下载
ls otatools/bin/

# 手动下载
python3 -c "from src.utils.otatools_manager import OtaToolsManager; OtaToolsManager().download_otatools()"
```

### 8.2 权限问题

**问题**: `Permission denied` 错误

**解决**:

```bash
# 使用 sudo 运行
sudo python3 main.py --stock stock.zip

# 或赋予工作目录权限
sudo chown -R $USER:$USER build/
```

### 8.3 磁盘空间不足

**问题**: `No space left on device`

**解决**:

```bash
# 清理工作目录
rm -rf build/

# 使用其他磁盘
sudo python3 main.py --stock stock.zip --work-dir /mnt/external/work
```

### 8.4 ROM 类型识别失败

**问题**: `Unknown ROM type`

**解决**:

```bash
# 检查 ROM 文件
unzip -l ROM.zip | head -20

# 手动指定格式 (如果工具无法识别)
# 目前工具会自动检测，如遇问题请提 Issue
```

### 8.5 打包失败

**问题**: `Failed to pack partition`

**解决**:

```bash
# 检查文件系统类型
# 某些分区可能需要 ext4
sudo python3 main.py --stock stock.zip --fs-type ext4
```

---

## 9. 输出文件说明

### 9.1 OTA 模式输出

```
out/<device>-ota_full-<version>-<date>-<md5>-<android>.zip
│
├── payload.bin          # 主要系统数据
├── payload.properties    # 元数据
├── care_map.pb          # 分区校验信息
└── META-INF/            # 刷机脚本
    └── com/google/android/
        ├── update-binary
        └── updater-script
```

**刷入方式**: Recovery 模式 → Apply update → Select from storage

### 9.2 Hybrid 模式输出

```
out/<device>-hybrid-<version>-<date>.zip
│
├── super.zst            # 压缩的系统分区
├── boot.img             # 启动镜像
├── firmware-update/     # 固件文件
│   ├── vbmeta.img
│   ├── dtbo.img
│   └── ...
├── windows_flash_script.bat  # Windows 刷机脚本
├── mac_linux_flash_script.sh # Linux/macOS 刷机脚本
└── META-INF/
    ├── update-binary    # Recovery 刷机程序
    ├── updater-script
    └── zstd             # 解压工具
```

**刷入方式**:

- Fastboot: 运行刷机脚本
- Recovery: 直接刷入 ZIP

---

## 10. 最佳实践

### 10.1 移植前检查清单

- [ ] 确认底包设备代号
- [ ] 确认移植包 Android 版本兼容
- [ ] 备份重要数据
- [ ] 准备线刷包以备恢复
- [ ] 确认磁盘空间充足
- [ ] 阅读目标设备的已知问题

### 10.2 推荐工作流程

```
1. 首次移植
   └── 使用 --clean 确保干净环境

2. 测试输出
   └── 刷入测试机，验证基本功能

3. 调整配置
   └── 修改 devices/<device>/ 配置

4. 重新生成
   └── 不带 --clean，使用缓存加速

5. 最终验证
   └── 全面功能测试
```

### 10.3 性能优化建议

1. **使用 SSD**: 大幅提升解包/打包速度
2. **增加内存**: 减少交换分区使用
3. **并行处理**: 工具默认使用 4 线程
4. **增量处理**: 利用缓存机制

---

## 11. 扩展开发

### 11.1 编写自定义插件

```python
# devices/<device>/plugins/my_plugin.py

from src.core.modifiers.plugin_system import ModifierPlugin, ModifierRegistry

@ModifierRegistry.register
class MyCustomPlugin(ModifierPlugin):
    name = "my_custom"
    description = "自定义插件"
    priority = 100

    def check_prerequisites(self) -> bool:
        # 检查是否应该运行
        return self.get_config("my_feature", {}).get("enable", False)

    def modify(self) -> bool:
        # 实现修改逻辑
        target_dir = self.ctx.target_dir

        # 示例：修改某个文件
        prop_file = target_dir / "system" / "build.prop"
        content = prop_file.read_text()
        content = content.replace("old_value", "new_value")
        prop_file.write_text(content)

        return True
```

### 11.2 添加新的 ROM 格式支持

在 `src/core/rom/extractors.py` 中添加新的提取函数：

```python
def extract_new_format(package: RomPackage, partitions: Optional[List[str]]) -> None:
    # 实现新格式的解包逻辑
    pass
```

---

## 12. Super 分区大小限制与原理

### 12.1 概念说明

Android 10+ 使用 **动态分区 (Dynamic Partition)** 架构，`super` 是一个物理分区，内部包含多个逻辑分区：

```
super (物理分区，固定大小)
├── system_a (逻辑分区)
├── system_b (逻辑分区)
├── vendor_a
├── vendor_b
├── product_a
├── product_b
├── system_ext_a
├── system_ext_b
├── odm_a / odm_b
├── vendor_dlkm_a / vendor_dlkm_b
└── mi_ext_a / mi_ext_b
```

### 12.2 大小限制层级

| 层级       | 说明               | 限制来源         |
| ---------- | ------------------ | ---------------- |
| **物理层** | super 分区物理大小 | 设备分区表 (GPT) |
| **逻辑层** | 逻辑分区组大小上限 | lpmake metadata  |
| **实际层** | 各镜像文件大小     | 打包后的实际大小 |

**关键规则**：所有逻辑分区大小之和 ≤ 逻辑分区组上限 ≤ super 物理大小

### 12.3 查看分区信息

**方法一：查看 rawprogram0.xml**

```bash
grep "super" images/rawprogram0.xml
```

输出示例：

```xml
<program filename="super.img" label="super"
         num_partition_sectors="2228224"
         size_in_KB="8912896.0" .../>
```

计算 super 物理大小：

```
2228224 sectors × 4096 bytes = 9126805504 bytes ≈ 8.5 GB
```

**方法二：使用 lpdump 查看 metadata**

```bash
bin/linux/x86_64/android-lptools-static-x86_64/lpdump super_raw.img
```

输出示例：

```
Metadata version: 10.2
Metadata size: 1360 bytes
Metadata max size: 65536 bytes
Header flags: virtual_ab_device

Super partition layout:
------------------------
super: 2048 .. 37608: odm_a (35560 sectors)
super: 38912 .. 9337104: product_a (9298192 sectors)
super: 9338880 .. 10823504: system_a (1484624 sectors)
super: 10823680 .. 12330136: system_ext_a (1506456 sectors)
super: 12331008 .. 16091576: vendor_a (3760568 sectors)
super: 16093184 .. 16151648: vendor_dlkm_a (58464 sectors)
super: 16152576 .. 16152864: mi_ext_a (288 sectors)
------------------------
Block device table:
------------------------
Partition name: super
Size: 9126805504 bytes
------------------------
Group table:
------------------------
Name: qti_dynamic_partitions_a
Maximum size: 8589934592 bytes  (约 8 GB)
------------------------
Name: qti_dynamic_partitions_b
Maximum size: 8589934592 bytes
------------------------
```

### 12.4 大小计算方法

**扇区大小说明**：

- lpdump 显示的 sector 是 512 字节（传统磁盘扇区）
- super 分区使用的 block size 是 4096 字节

**计算示例**：

```
product_a: 9298192 sectors × 512 bytes = 4,764,674,304 bytes ≈ 4.4 GB
system_a:  1484624 sectors × 512 bytes = 760,127,488 bytes ≈ 725 MB
vendor_a:  3760568 sectors × 512 bytes = 1,925,410,816 bytes ≈ 1.8 GB
```

### 12.5 验证大小是否合规

**验证脚本**：

```bash
# 计算所有 _a 分区大小之和
ls -l build/target/*_a.img | awk '{sum+=$5} END {print "总大小:", sum/1024/1024/1024, "GB"}'

# 输出示例: 总大小: 7.6 GB
```

**验证规则**：

- 逻辑分区总和 ≤ qti_dynamic_partitions_a 最大值 (8 GB)
- 逻辑分区总和 ≤ super 物理大小 (8.5 GB)

### 12.6 常见设备 super 大小

| 设备                  | super 大小 | 逻辑分区组上限 |
| --------------------- | ---------- | -------------- |
| 小米 12S Ultra (thor) | 8.5 GB     | 8 GB           |
| 小米 13 (fuxi)        | 9 GB       | 8.5 GB         |
| 小米 14 (houdini)     | 10 GB      | 9.5 GB         |

> 注意：具体大小请以设备实际的 rawprogram0.xml 或 lpdump 输出为准。

### 12.7 打包失败排查

**问题**：`lpmake: partition would exceed group size`

**原因**：逻辑分区大小之和超过了 group 上限

**解决**：

1. 检查是否有分区异常增大
2. 精简不必要的应用减少 product 大小
3. 检查 super_size 配置是否正确

**问题**：刷入后无法启动

**可能原因**：

1. 分区大小超出物理限制
2. AVB 验证失败
3. metadata 损坏

**排查步骤**：

```bash
# 1. 验证 super.img 格式
file super.img
# 应输出: Android sparse image

# 2. 验证 metadata
bin/linux/x86_64/android-lptools-static-x86_64/lpdump super_raw.img

# 3. 验证大小
ls -l *.img
```

### 12.8 精简后空间释放

删除应用后，product 分区变小，释放的空间：

| 操作             | product 变化 | super 变化 |
| ---------------- | ------------ | ---------- |
| 删除讯飞输入法   | -50 MB       | -50 MB     |
| 删除多个预装应用 | -200~500 MB  | 同等减少   |

**释放空间去向**：

- 逻辑分区变小后，super 内部产生空闲区域
- 刷入后系统可动态使用这些空闲空间
- 不会自动扩展其他分区

---

## 14. 工具链获取指南

本节介绍如何从各种来源获取项目所需的工具链。如果你 fork 了本项目或需要手动准备工具，请参考以下内容。

### 14.1 Google Android CI（官方推荐）

Google 在 [ci.android.com](https://ci.android.com) 提供官方预构建工具，这是获取工具链的首选方式。

#### 访问步骤

1. 打开构建网格页面：https://ci.android.com/builds/branches/aosp-main/grid
2. 点击 `aosp_cf_x86_64_phone` 列的任意绿色方块（表示构建成功）
3. 进入 **Artifacts** 标签页

对于 ** 下载官方工具（如 lpmake/lpunpack）** 的需求：
优先选：aosp_cf_x86_64_phone + trunk_staging-userdebug
因为 cvd-host_package.tar.gz 通常绑定 Cuttlefish 目标构建。
避免选：带 coverage、soong-only、errorprone 后缀的版本，这些是特殊测试构建，工具链可能不稳定或包含额外调试开销。

https://ci.android.com/builds/submitted/13281750/aosp_cf_x86_64_phone-trunk_staging-userdebug/latest

#### 可下载的工具包

| 工具包                    | 内容                | 用途                              |
| ------------------------- | ------------------- | --------------------------------- |
| `otatools.zip`            | OTA 打包工具        | 生成 OTA 更新包、签名工具         |
| `cvd-host_package.tar.gz` | Cuttlefish 主机工具 | 包含 lpmake、lpunpack、avbtool 等 |

#### otatools.zip 包含的工具

```
otatools/
├── bin/
│   ├── ota_from_target_files  # OTA 包生成（Python 脚本）
│   ├── signapk                # APK/ZIP 签名
│   ├── avbtool                # Android Verified Boot 工具
│   ├── append2simg            # 追加到 sparse image
│   ├── e2fsdroid              # ext2/3/4 文件系统工具
│   ├── simg2img               # sparse image 转换
│   ├── img2simg               # 转换为 sparse image
│   ├── mkbootimg              # 创建 boot 镜像
│   ├── unpack_bootimg         # 解包 boot 镜像
│   └── ...
├── lib64/                     # 依赖的共享库
└── security/                  # 签名密钥（testkey 等）
```

> **注意**：Google CI 的 `otatools.zip` **不包含** `lpmake`、`lpunpack` 等分区工具，这些工具在 `cvd-host_package.tar.gz` 中。

#### cvd-host_package.tar.gz 包含的工具

```
cvd-host_package/
├── bin/
│   ├── lpmake                 # 创建 super.img
│   ├── lpunpack               # 解包 super.img
│   ├── lpadd                  # 添加分区到 super.img
│   ├── lpdump                 # 查看 super.img 信息
│   ├── lpflash                # 写入 super.img 到设备
│   ├── adb                    # Android Debug Bridge
│   ├── fastboot               # Fastboot 工具
│   ├── avbtool                # AVB 工具
│   ├── mkbootimg              # 创建 boot 镜像
│   ├── unpack_bootimg         # 解包 boot 镜像
│   └── launch_cvd             # Cuttlefish 启动（不需要）
└── lib64/
```

### 14.2 分区工具（lpmake/lpunpack）

如果只需要分区工具，可以从以下 GitHub 仓库获取预构建版本：

| 仓库                                                                                                                            | 说明                    | 平台           |
| ------------------------------------------------------------------------------------------------------------------------------- | ----------------------- | -------------- |
| [Rprop/aosp15_partition_tools](https://github.com/Rprop/aosp15_partition_tools)                                                 | Android 15 静态链接版本 | Linux, Windows |
| [northumber/android-partition-tools_prebuilt_binaries](https://github.com/northumber/android-partition-tools_prebuilt_binaries) | 预构建版本              | Linux          |
| [rendiix/termux-partition-tools](https://github.com/rendiix/termux-partition-tools)                                             | Termux/Android 版       | Android        |

#### 分区工具说明

| 工具       | 功能                               |
| ---------- | ---------------------------------- |
| `lpmake`   | 创建 super.img（动态分区镜像）     |
| `lpunpack` | 解包 super.img 到各个分区镜像      |
| `lpadd`    | 向 super.img 添加分区镜像          |
| `lpflash`  | 将 super.img 写入块设备            |
| `lpdump`   | 查看 super.img 分区布局和 metadata |

### 14.3 EROFS 文件系统工具

现代 Android (HyperOS/MIUI) 使用 EROFS 文件系统。

#### Linux 发行版安装

```bash
# Ubuntu/Debian
sudo apt install erofs-utils

# Arch Linux
sudo pacman -S erofs-utils

# Alpine Linux
apk add erofs-utils
```

#### 从源码构建

```bash
git clone https://github.com/erofs/erofs-utils.git
cd erofs-utils
./autogen.sh
./configure
make
sudo make install
```

#### EROFS 工具说明

| 工具         | 功能                    |
| ------------ | ----------------------- |
| `mkfs.erofs` | 创建 EROFS 镜像         |
| `fsck.erofs` | 检查 EROFS 镜像完整性   |
| `dump.erofs` | 分析 EROFS 镜像结构     |
| `erofsfuse`  | 挂载 EROFS 镜像（FUSE） |

### 14.4 Payload 工具

用于解包 OTA 的 `payload.bin` 文件。

| 工具                                                           | 说明            | 来源            |
| -------------------------------------------------------------- | --------------- | --------------- |
| [payload-dumper-go](https://github.com/ssut/payload-dumper-go) | Go 实现，速度快 | GitHub Releases |
| [payload-dumper](https://github.com/vm03/payload_dumper)       | Python 实现     | pip 安装        |
| `extract_android_ota_payload`                                  | 内置脚本        | 项目自带        |

#### Python 版本安装

```bash
pip install protobuf brotli
# 或使用 payload-dumper-go 预构建版本
```

### 14.5 从 AOSP 本地构建

如果你有 AOSP 编译环境，可以自己构建工具：

```bash
# 构建 otatools
make otatools-package
# 输出: out/target/product/<device>/otatools.zip

# 或使用 make dist
make dist
# 输出: out/dist/otatools.zip
```

### 14.6 组合工具链

本项目的 `otatools` 目录是以下工具的组合：

```
otatools/
├── 来自 otatools.zip (Google CI)
│   ├── ota_from_target_files
│   ├── signapk / apksigner
│   ├── avbtool
│   └── 其他签名工具
│
├── 来自 cvd-host_package.tar.gz (Google CI)
│   ├── lpmake
│   ├── lpunpack
│   ├── lpadd
│   └── lpdump
│
└── 来自系统包管理器
    ├── mkfs.erofs
    ├── fsck.erofs
    └── dump.erofs
```

### 14.7 快速设置脚本

创建你自己的 otatools 目录：

```bash
#!/bin/bash
# setup_otatools.sh

mkdir -p otatools/bin otatools/lib64 otatools/security

# 1. 从 Google CI 下载 otatools.zip
# 访问 https://ci.android.com/builds/branches/aosp-master/grid
# 下载 otatools.zip 并解压到 otatools/

# 2. 从 Google CI 下载 cvd-host_package.tar.gz
# 解压并将 bin/lpmake, bin/lpunpack 等复制到 otatools/bin/

# 3. 安装 EROFS 工具（如果系统没有）
# sudo apt install erofs-utils

# 4. 设置执行权限
chmod +x otatools/bin/*

echo "otatools 设置完成！"
```

### 14.8 工具清单

项目运行所需的完整工具列表：

| 工具             | 用途                | 来源                               |
| ---------------- | ------------------- | ---------------------------------- |
| `lpmake`         | 创建 super.img      | cvd-host_package / partition_tools |
| `lpunpack`       | 解包 super.img      | cvd-host_package / partition_tools |
| `lpdump`         | 查看 super.img 信息 | cvd-host_package / partition_tools |
| `mkfs.erofs`     | 创建 EROFS 镜像     | 系统包管理器                       |
| `fsck.erofs`     | 检查 EROFS 镜像     | 系统包管理器                       |
| `simg2img`       | sparse image 转换   | otatools.zip                       |
| `img2simg`       | 转换为 sparse image | otatools.zip                       |
| `avbtool`        | AVB 签名工具        | otatools.zip / cvd-host_package    |
| `signapk`        | APK/ZIP 签名        | otatools.zip                       |
| `payload-dumper` | 解包 payload.bin    | pip / payload-dumper-go            |
| `unpack_bootimg` | 解包 boot 镜像      | otatools.zip                       |
| `mkbootimg`      | 创建 boot 镜像      | otatools.zip                       |

### 14.9 常见问题

**Q: 为什么不把工具打包到仓库中？**

A: 工具体积较大（数百 MB），且包含平台相关的二进制文件，不适合放入 Git 仓库。通过自动下载或用户自行准备更灵活。

**Q: 工具版本兼容性如何？**

A: Android 工具通常向前兼容。建议使用与目标 ROM Android 版本相近的工具，但大多数情况下最新版本也能工作。

**Q: Windows 可以使用这些工具吗？**

A: 大部分工具是 Linux x86_64 二进制文件。Windows 用户需要使用 WSL 或下载 Windows 版本的分区工具（如 Rprop/aosp15_partition_tools）。

---

## 15. 获取帮助

- **GitHub Issues**: 报告问题和功能请求
- **项目文档**: 查看 `docs/` 目录
- **代码注释**: 阅读源码中的详细注释
