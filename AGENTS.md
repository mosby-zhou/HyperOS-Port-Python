# HyperOS-Port-Python AI Coding Agent Guide

本文档为 AI 编程助手提供项目上下文，帮助理解和维护 HyperOS-Port-Python 项目。

---

## 项目概述

**HyperOS-Port-Python** 是一个基于 Python 的自动化 ROM 移植工具，用于小米/Redmi 设备之间的 HyperOS ROM 移植。

### 核心功能

| 功能 | 描述 |
|------|------|
| ROM 移植 | 将一个设备的 ROM 移植到另一个设备 |
| 官改模式 | 直接修改原厂 ROM，无需移植源 |
| KernelSU 注入 | 集成 KernelSU 获取 root 权限 |
| EU 本地化 | 恢复中国区独占功能到全球/EU ROM |
| Wild Boost | 安装性能增强模块 |

### 技术栈

- **Python**: 3.8+
- **平台**: Linux (Ubuntu 20.04+ 推荐)
- **依赖**: requests (生产), pytest/black/ruff/mypy (开发)
- **外部工具**: magiskboot, apktool, payload-dumper, lpunpack, mkfs.erofs 等

---

## 架构设计

### 整体架构

```
用户接口层 (main.py)
        │
        ▼
核心业务层
├── PortingContext (状态管理)
├── RomPackage (ROM 处理)
├── Modifier System (修改系统)
│   ├── UnifiedModifier (统一修改入口)
│   ├── FrameworkModifier (Framework 补丁)
│   ├── FirmwareModifier (固件修改)
│   └── RomModifier (ROM 级修改)
└── Repacker (镜像打包)
        │
        ▼
插件扩展层 (Plugin System)
├── WildBoostPlugin
├── FileReplacementPlugin
├── FeatureUnlockPlugin
├── VndkFixPlugin
└── EuLocalizationPlugin
        │
        ▼
工具服务层 (src/utils/)
├── shell.py (命令执行)
├── downloader.py (资源下载)
├── smalikit.py (Smali 操作)
└── xml_utils.py (XML 处理)
        │
        ▼
配置数据层 (devices/)
├── common/ (通用配置)
└── <device>/ (设备配置)
```

### 目录结构

```
HyperOS-Port-Python/
├── main.py                      # 主入口脚本
├── src/
│   ├── core/                    # 核心 ROM 处理逻辑
│   │   ├── context.py           # PortingContext - 中央状态管理
│   │   ├── packer.py            # Repacker - 镜像重新打包
│   │   ├── props.py             # 属性管理
│   │   ├── config_loader.py     # 设备配置加载/合并
│   │   ├── config_merger.py     # 配置深度合并逻辑
│   │   ├── rom/                 # ROM 包处理
│   │   │   ├── package.py       # RomPackage 类
│   │   │   ├── extractors.py    # ROM 提取方法
│   │   │   └── constants.py     # 分区列表和 RomType 枚举
│   │   ├── modifiers/           # 修改系统
│   │   │   ├── base_modifier.py     # 修改器基类
│   │   │   ├── unified_modifier.py  # 统一修改入口
│   │   │   ├── system_modifier.py   # 系统级修改
│   │   │   ├── framework_modifier.py # Framework 修改
│   │   │   ├── firmware_modifier.py # 固件/VBMeta/KSU 补丁
│   │   │   ├── plugin_system.py     # 插件架构
│   │   │   ├── framework/           # Framework smali 补丁
│   │   │   └── plugins/             # 内置插件
│   │   └── monitoring/          # 监控/日志系统
│   └── utils/                   # 工具模块
├── devices/                     # 设备专用配置
│   ├── common/                  # 通用配置
│   └── <device_code>/           # 设备配置
├── bin/                         # 二进制工具
├── tools/                       # 辅助工具
└── tests/                       # 单元测试
```

---

## 核心组件

### 1. PortingContext (上下文管理器)

**文件**: `src/core/context.py`

中央状态管理对象，保存整个移植过程中的所有状态引用。

```python
class PortingContext:
    # ROM 引用
    stock: RomPackage        # 原厂 ROM
    port: RomPackage         # 移植源 ROM（可选）

    # 路径
    target_dir: Path         # 目标工作目录
    repack_images_dir: Path  # 固件镜像目录

    # 工具路径
    magiskboot: Path
    aapt2: Path
    apktool: Path

    # ROM 信息
    android_version: int
    target_device: str
    is_ab_device: bool
```

### 2. RomPackage (ROM 包处理器)

**文件**: `src/core/rom/package.py`

表示一个 ROM 包，提供统一的接口处理不同格式的 ROM。

**ROM 类型**:
- `PAYLOAD`: payload.bin 格式 (OTA/Recovery ROM)
- `BROTLI`: .new.dat.br 格式 (旧版 ROM)
- `FASTBOOT`: super.img 格式 (Fastboot ROM)
- `LOCAL_DIR`: 本地目录 (已解包)

### 3. Modifier System (修改器系统)

**架构**:
```
BaseModifier (基类)
    │
    ├── UnifiedModifier (统一修改器)
    │       ├── SystemModifier (系统修改)
    │       │       └── PluginManager
    │       └── ApkModifier (APK 修改)
    │               └── PluginManager
    │
    ├── FrameworkModifier (Framework 修改)
    ├── FirmwareModifier (固件修改)
    └── RomModifier (ROM 级修改)
```

### 4. Plugin System (插件系统)

**文件**: `src/core/modifiers/plugin_system.py`

**核心特性**:
- 基于优先级的执行顺序 (priority 数值越小越先执行)
- 依赖解析
- 并行执行支持
- 事务/回滚支持
- 超时控制

**插件基类**:
```python
class ModifierPlugin(ABC):
    name: str = ""              # 插件名称
    priority: int = 100         # 执行优先级
    dependencies: List[str]     # 必须依赖的插件
    parallel_safe: bool = True  # 是否可并行执行

    @abstractmethod
    def modify(self) -> bool:   # 执行修改逻辑
        pass

    def check_prerequisites(self) -> bool:  # 前置检查
        return True
```

**内置插件执行顺序**:
| 优先级 | 插件 | 功能 |
|--------|------|------|
| 10 | WildBoost | 性能模块安装 |
| 20 | FileReplacement | 文件/目录替换 |
| 30 | FeatureUnlock | 功能开关 |
| 40 | VndkFix | VNDK/VINTF 修复 |
| 50 | EuLocalization | EU bundle 应用 |

---

## 配置系统

### 配置层级

```
CLI 参数 > 设备配置 (devices/<device>/config.json) > 通用配置 (devices/common/config.json)
```

### 配置文件

| 文件 | 用途 |
|------|------|
| `config.json` | 设备配置 (wild_boost, pack, ksu) |
| `features.json` | 功能开关和属性覆盖 |
| `replacements.json` | 文件替换规则 |
| `props.json` | 属性覆盖 |
| `eu_bundle_config.json` | EU bundle 应用列表 |

### 配置合并

```python
# 深度合并示例
common_config = load_config("devices/common/config.json")
device_config = load_config("devices/<device>/config.json")
final_config = deep_merge(common_config, device_config)
```

---

## 编码规范

### 代码风格

- **格式化**: Black, line-length 100
- **Linting**: Ruff
- **类型检查**: MyPy

```bash
# 格式化
black src/ --line-length 100

# Linting
ruff check src/

# 类型检查
mypy src/ --ignore-missing-imports
```

### 命名约定

| 类型 | 约定 | 示例 |
|------|------|------|
| 类名 | PascalCase | `PortingContext` |
| 函数/方法 | snake_case | `get_rom_info()` |
| 私有方法 | _snake_case | `_detect_type()` |
| 常量 | UPPER_SNAKE | `AVB_MAGIC` |
| 模块变量 | snake_case | `logger` |

### 类型注解

项目使用 Python 类型注解:

```python
def find_apk_by_name(self, apk_name: str) -> Optional[Path]:
    ...

def pack_all(self, pack_type: str = "erofs", is_rw: bool = False) -> Dict[str, Path]:
    ...
```

### 日志规范

```python
import logging
logger = logging.getLogger(__name__)

logger.info("开始处理 ROM")
logger.debug(f"分区列表: {partitions}")
logger.warning("未找到配置文件，使用默认值")
logger.error(f"处理失败: {e}")
```

---

## 开发指南

### 添加新设备支持

1. 创建设备目录: `devices/<device_code>/`
2. 创建配置文件:
   - `config.json` - 设备配置
   - `features.json` - 功能开关
   - `props.json` - 属性覆盖
   - `replacements.json` - 文件替换规则
3. 添加覆盖文件到 `override/` 目录

### 添加新插件

1. 在 `src/core/modifiers/plugins/` 创建插件文件
2. 继承 `ModifierPlugin` 类
3. 实现必要的方法:

```python
from src.core.modifiers.plugin_system import ModifierPlugin, ModifierRegistry

@ModifierRegistry.register
class MyPlugin(ModifierPlugin):
    name = "my_plugin"
    priority = 100
    version = "1.0.0"

    def check_prerequisites(self) -> bool:
        return self.get_config("my_feature", {}).get("enable", False)

    def modify(self) -> bool:
        # 实现修改逻辑
        target_dir = self.ctx.target_dir
        return True
```

4. 插件会被自动发现和注册

### 添加新的 ROM 格式支持

在 `src/core/rom/extractors.py` 中添加新的提取函数。

### 添加新的修改器

1. 在 `src/core/modifiers/` 创建新的修改器文件
2. 继承 `BaseModifier` 类
3. 实现 `run()` 方法
4. 在 `main.py` 中集成

---

## 关键技术点

### 1. AVB 禁用

```python
# vbmeta 补丁
AVB_MAGIC = b"AVB0"
FLAGS_OFFSET = 123
FLAGS_TO_SET = b"\x03"  # 禁用 AVB 验证
```

### 2. KernelSU 注入

针对 GKI 2.0+ (内核 5.10+) 设备:
- 解压 boot.img / init_boot.img
- 备份原始 init → init.real
- 添加 ksuinit 和 kernelsu.ko
- 重新打包

### 3. Wild Boost 安装位置

| 内核版本 | 位置 | 原因 |
|----------|------|------|
| 5.10 | vendor_boot ramdisk | GKI 1.0 |
| 5.15+ | vendor_dlkm | GKI 2.0 |
| 6.12 | vendor_boot ramdisk | Android 16 KMI |

### 4. 设备伪装

通过 HexPatch 修改 `libmigui.so`:
```
ro.product.product.name → ro.product.spoofed.name
```

### 5. 分区来源策略

| 分区 | 来源 | 原因 |
|------|------|------|
| vendor, odm, vendor_dlkm, odm_dlkm, system_dlkm | Stock (底包) | 硬件驱动 |
| system, system_ext, product, mi_ext, product_dlkm | Port (移植包) | 系统框架 |

---

## 测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试
pytest tests/core/test_config_loader.py -v

# 覆盖率
pytest tests/ --cov=src --cov-report=html
```

---

## 常见问题

### 工具链问题

```bash
# 检查 otatools
ls otatools/bin/

# 手动下载
python3 -c "from src.utils.otatools_manager import OtaToolsManager; OtaToolsManager().download_otatools()"
```

### 权限问题

```bash
# 使用 sudo 运行
sudo python3 main.py --project <项目名> --stock stock.zip
```

### 磁盘空间不足

```bash
# 清理工作目录
rm -rf build/

# 使用其他磁盘
sudo python3 main.py --project <项目名> --stock stock.zip --work-dir /mnt/external/work
```

---

## 相关文档

- `ARCHITECTURE.md` - 完整架构文档
- `DETAILS.md` - 核心类和组件详解
- `PRINCIPLES.md` - 技术原理说明
- `USER_GUIDE.md` - 用户使用指南
- `FEASIBILITY.md` - 可行性评估
- `SLIM_ROM_GUIDE.md` - 精简 ROM 操作指南
