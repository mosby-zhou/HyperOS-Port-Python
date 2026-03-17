# HyperOS-Port-Python 使用指南

## 1. 环境准备

### 1.1 系统要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Linux (推荐 Ubuntu 20.04+) |
| Python | 3.8+ |
| 磁盘空间 | 50GB+ 可用空间 |
| 内存 | 8GB+ (推荐 16GB) |
| 权限 | sudo 权限 (用于挂载镜像) |

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

| 参数 | 必需 | 默认值 | 说明 |
|------|------|--------|------|
| `--stock` | ✅ | - | 底包 ROM 路径 (ZIP/目录) |
| `--port` | ❌ | - | 移植包 ROM 路径。省略则进入官改模式 |
| `--pack-type` | ❌ | payload | 输出格式: `payload` 或 `super` |
| `--fs-type` | ❌ | erofs | 文件系统: `erofs` 或 `ext4` |
| `--ksu` | ❌ | false | 注入 KernelSU |
| `--work-dir` | ❌ | build | 工作目录 |
| `--clean` | ❌ | false | 开始前清理工作目录 |
| `--debug` | ❌ | false | 开启调试日志 |
| `--eu-bundle` | ❌ | - | EU 本地化资源包路径 |
| `--phases` | ❌ | 全部 | 执行阶段: system,apk,framework,firmware,repack |

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

| 阶段 | 功能 | 耗时 |
|------|------|------|
| system | 系统级修改 (Wild Boost, 文件替换等) | 1-3 分钟 |
| apk | APK 级修改 (Settings, Joyose 等) | 2-5 分钟 |
| framework | Framework Smali 补丁 | 1-2 分钟 |
| firmware | 固件修改 (vbmeta, KSU) | 1-2 分钟 |
| repack | 镜像打包和生成刷机包 | 10-20 分钟 |

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

| 字段 | 类型 | 说明 |
|------|------|------|
| `wild_boost.enable` | bool | 启用 Wild Boost 性能模块 |
| `pack.type` | string | 打包类型: payload / super |
| `pack.fs_type` | string | 文件系统: erofs / ext4 |
| `pack.super_size` | int | Super 分区大小 (字节) |
| `ksu.enable` | bool | 启用 KernelSU |

#### features.json - 功能开关

| 字段 | 类型 | 说明 |
|------|------|------|
| `xml_features.*` | bool | XML 功能开关 |
| `build_props.<partition>.*` | string | 属性覆盖 |

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

## 12. 获取帮助

- **GitHub Issues**: 报告问题和功能请求
- **项目文档**: 查看 `docs/` 目录
- **代码注释**: 阅读源码中的详细注释
