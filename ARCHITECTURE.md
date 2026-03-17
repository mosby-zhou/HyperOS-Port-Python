# HyperOS-Port-Python 架构文档

## 1. 项目概述

**HyperOS-Port-Python** 是一个基于 Python 的自动化 ROM 移植工具，专门用于小米/Redmi 设备之间的 HyperOS ROM 移植。它能够处理 ROM 解包、智能补丁、功能恢复、重新打包和签名的完整生命周期。

### 1.1 核心能力

| 功能 | 描述 |
|------|------|
| ROM 移植 | 将一个设备的 ROM 移植到另一个设备（如小米14/15 ROM 移植到小米13） |
| 官方修改模式 | 无需移植源，直接修改原厂 ROM |
| KernelSU 注入 | 集成 KernelSU 获取 root 权限 |
| EU 本地化 | 恢复中国区独占功能到全球/EU ROM |
| Wild Boost | 安装性能增强模块 |

### 1.2 支持的 ROM 格式

| 类型 | 检测方式 | 解包方法 |
|------|----------|----------|
| PAYLOAD | zip 中包含 `payload.bin` | `payload-dumper` |
| BROTLI | 包含 `.new.dat.br` 文件 | `brotli` + `sdat2img` |
| FASTBOOT | `super.img` 或 `.tgz` | `lpunpack` |
| LOCAL_DIR | 目录路径 | 直接访问 |

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              main.py                                    │
│                        (主入口与流程编排)                                │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
┌───────────────┐          ┌───────────────┐          ┌───────────────┐
│   Phase 1     │          │   Phase 2     │          │   Phase 3     │
│   提取阶段    │          │   初始化阶段  │          │   修改阶段    │
│ RomPackage    │          │PortingContext │          │  Modifier     │
└───────────────┘          └───────────────┘          └───────────────┘
                                    │                           │
                                    ▼                           ▼
                           ┌───────────────┐          ┌───────────────┐
                           │   Config      │          │  Plugin       │
                           │   Loader      │          │  System       │
                           └───────────────┘          └───────────────┘
                                                              │
                                    │                         ▼
                                    ▼                 ┌───────────────┐
                           ┌───────────────┐        │   Built-in    │
                           │   Phase 4     │        │   Plugins     │
                           │   打包阶段    │        └───────────────┘
                           │   Repacker    │
                           └───────────────┘
```

### 2.2 核心模块关系图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            src/core/                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐     │
│  │   context.py    │◄───│  rom/package.py │    │    packer.py    │     │
│  │ PortingContext  │    │   RomPackage    │    │    Repacker     │     │
│  └────────┬────────┘    └─────────────────┘    └─────────────────┘     │
│           │                                                              │
│           │         ┌─────────────────────────────────────────┐        │
│           │         │              modifiers/                  │        │
│           │         ├─────────────────────────────────────────┤        │
│           └────────►│  ┌─────────────────────────────────┐    │        │
│                     │  │     unified_modifier.py          │    │        │
│                     │  │      UnifiedModifier             │    │        │
│                     │  └──────────────┬──────────────────┘    │        │
│                     │                 │                        │        │
│                     │    ┌────────────┼────────────┐          │        │
│                     │    ▼            ▼            ▼          │        │
│                     │ ┌──────┐   ┌──────┐   ┌──────┐         │        │
│                     │ │system│   │apk   │   │plugin│         │        │
│                     │ │_mod  │   │_mod  │   │_mgr  │         │        │
│                     │ └──────┘   └──────┘   └──────┘         │        │
│                     └─────────────────────────────────────────┘        │
│                                                                          │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐     │
│  │  props.py       │    │ config_loader.py│    │  conditions.py  │     │
│  │ PropertyManager │    │  ConfigLoader   │    │ ConditionEval   │     │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 目录结构

```
HyperOS-Port-Python/
├── main.py                      # 主入口脚本
├── pyproject.toml               # Python 项目配置
├── requirements.txt             # 生产依赖
├── requirements-dev.txt         # 开发依赖
├── requirements-test.txt        # 测试依赖
├── pytest.ini                   # Pytest 配置
├── LICENSE                      # Unlicense 许可证
├── README.md                    # 英文文档
├── README_CN.md                 # 中文文档
│
├── src/                         # 核心源代码
│   ├── core/                    # 核心 ROM 处理逻辑
│   │   ├── context.py           # PortingContext - 中央状态管理
│   │   ├── packer.py            # Repacker - 镜像重新打包
│   │   ├── props.py             # 属性管理
│   │   ├── config_loader.py     # 设备配置加载/合并
│   │   ├── config_merger.py     # 配置深度合并逻辑
│   │   ├── config_schema.py     # 配置验证模式
│   │   ├── conditions.py        # 替换条件评估
│   │   ├── modifier.py          # (已弃用) 向后兼容
│   │   │
│   │   ├── rom/                 # ROM 包处理
│   │   │   ├── package.py       # RomPackage 类
│   │   │   ├── extractors.py    # ROM 提取方法
│   │   │   ├── constants.py     # 分区列表和 RomType 枚举
│   │   │   └── utils.py         # ROM 工具函数
│   │   │
│   │   ├── modifiers/           # 修改系统 (模块化)
│   │   │   ├── base_modifier.py     # 所有修改器的基类
│   │   │   ├── unified_modifier.py  # 组合系统 + APK 修改
│   │   │   ├── system_modifier.py   # 系统级修改
│   │   │   ├── framework_modifier.py # Framework 修改入口
│   │   │   ├── firmware_modifier.py # 固件/VBMeta/KSU 补丁
│   │   │   ├── rom_modifier.py      # ROM 级修改
│   │   │   ├── smali_args.py        # Smali 参数工具
│   │   │   ├── transaction.py       # 事务/回滚系统
│   │   │   ├── plugin_system.py     # 插件架构
│   │   │   │
│   │   │   ├── framework/           # Framework smali 补丁
│   │   │   │   ├── base.py          # 基础类
│   │   │   │   ├── modifier.py      # 修改器
│   │   │   │   ├── patches.py       # 补丁定义
│   │   │   │   └── tasks.py         # 任务定义
│   │   │   │
│   │   │   └── plugins/             # 内置插件
│   │   │       ├── wild_boost.py     # 性能模块
│   │   │       ├── eu_localization.py # EU bundle 应用
│   │   │       ├── feature_unlock.py # 功能开关
│   │   │       ├── vndk_fix.py       # VNDK/VINTF 修复
│   │   │       ├── file_replacement.py # 文件替换
│   │   │       └── apk/              # APK 专用插件
│   │   │           ├── base.py, installer.py, settings.py
│   │   │           ├── joyose.py, powerkeeper.py
│   │   │           ├── securitycenter.py, devices_overlay.py
│   │   │
│   │   └── monitoring/          # 监控/日志系统
│   │       ├── console_ui.py
│   │       ├── plugin_integration.py
│   │       └── workflow_integration.py
│   │
│   └── utils/                   # 工具模块
│       ├── shell.py             # Shell 命令执行
│       ├── downloader.py        # ROM/aria2 下载管理器
│       ├── file_downloader.py   # 通用文件下载器
│       ├── download.py          # 资源下载器
│       ├── sync_engine.py       # ROM 同步/缓存
│       ├── otatools_manager.py  # OTA 工具设置
│       ├── smalikit.py          # Smali 操作
│       ├── lpunpack.py          # Python lpunpack 实现
│       ├── sdat2img.py          # Brotli dat 转换
│       ├── fspatch.py           # fs_config 补丁
│       ├── contextpatch.py      # SELinux 上下文补丁
│       └── xml_utils.py         # XML 操作
│
├── devices/                     # 设备专用配置
│   ├── common/                  # 通用配置
│   │   ├── config.json          # 默认设备配置
│   │   ├── features.json        # 功能开关
│   │   ├── replacements.json    # 文件替换规则
│   │   ├── eu_bundle_config.json # EU bundle 应用列表
│   │   ├── eu_localization.json # EU 本地化配置
│   │   ├── props_global.json    # 全局属性覆盖
│   │   ├── scheduler.json       # 插件调度器配置
│   │   ├── wild_boost_5.10.zip  # 内核 5.10 性能模块
│   │   ├── wild_boost_5.15.zip  # 内核 5.15 性能模块
│   │   └── override/            # 通用覆盖文件
│   │
│   ├── fuxi/                    # 小米13 (fuxi) 专用
│   │   ├── config.json, features.json
│   │   ├── props.json, replacements.json
│   │   └── override/            # 设备专用覆盖
│   │
│   └── mayfly/                  # 小米12S (mayfly) 专用
│       └── config.json, features.json, etc.
│
├── bin/                         # 二进制工具
│   ├── APKEditor.jar            # APK 编辑工具
│   ├── apktool.jar              # APK 反编译
│   ├── baksmali.jar, smali.jar  # Smali 工具
│   ├── flash/                   # 刷机脚本
│   │   ├── windows_flash_script.bat
│   │   ├── mac_linux_flash_script.sh
│   │   ├── update-binary, zstd
│   │   └── platform-tools-windows/ # Windows ADB/Fastboot
│   │
│   └── linux/x86_64/            # Linux 二进制文件
│       ├── aapt2, brotli, e2fsdroid
│       ├── extract.erofs, mkfs.erofs
│       ├── lpunpack, magiskboot, mke2fs
│       ├── payload-dumper, simg2img
│       └── lib64/libc++.so
│
├── tools/                       # 辅助工具
│   └── generate_eu_bundle.py    # EU bundle 生成器
│
├── tests/                       # 单元测试
│   ├── conftest.py              # Pytest fixtures
│   ├── test_unified_modifier.py
│   └── core/
│       ├── test_base_modifier.py
│       ├── test_config_loader.py
│       ├── test_shell.py
│       └── test_voice_trigger.py
│
├── examples/                    # 示例脚本
│   ├── monitoring_example.py
│   └── modifier_plugins_example.py
│
├── docs/                        # 文档
│   └── plugin_system.md         # 插件系统文档
│
└── out/                         # 输出目录 (生成)
```

---

## 4. 核心组件详解

### 4.1 PortingContext (上下文管理器)

**位置**: `src/core/context.py`

**职责**: 作为中央状态管理对象，保存整个移植过程中的所有状态引用。

**核心属性**:
```python
class PortingContext:
    # ROM 引用
    stock_rom: RomPackage        # 原厂 ROM
    port_rom: RomPackage         # 移植源 ROM（可选）

    # 路径
    target_dir: Path             # 目标工作目录
    stock_dir: Path              # 原厂解包目录
    port_dir: Path               # 移植源解包目录

    # 工具路径
    magiskboot: Path             # magiskboot 工具路径
    aapt2: Path                  # aapt2 工具路径
    apktool: Path                # apktool 工具路径

    # ROM 信息
    android_version: int         # Android 版本
    target_device: str           # 目标设备代号
    port_device: str             # 移植源设备代号

    # 缓存
    apk_cache: dict              # APK 快速查找缓存
    sync_engine: SyncEngine      # 文件同步引擎
```

### 4.2 RomPackage (ROM 包处理器)

**位置**: `src/core/rom/package.py`

**职责**: 表示一个 ROM 包，提供统一的接口处理不同格式的 ROM。

**类型检测流程**:
```python
def _detect_type(self) -> RomType:
    if zip 中包含 payload.bin:
        return RomType.PAYLOAD
    elif 包含 .new.dat.br 文件:
        return RomType.BROTLI
    elif 是 super.img 或 .tgz:
        return RomType.FASTBOOT
    elif 是目录:
        return RomType.LOCAL_DIR
```

**提取方法映射**:
| ROM 类型 | 提取方法 | 使用工具 |
|----------|----------|----------|
| PAYLOAD | `extract_payload()` | `payload-dumper` |
| BROTLI | `extract_brotli()` | `brotli` + `sdat2img` |
| FASTBOOT | `extract_fastboot()` | `lpunpack` |
| LOCAL_DIR | 直接访问 | 无 |

### 4.3 Modifier System (修改器系统)

**架构**:
```
BaseModifier (基类)
    │
    ├── UnifiedModifier (统一修改器)
    │       │
    │       ├── SystemModifier (系统修改)
    │       │       └── PluginManager (插件管理)
    │       │
    │       └── ApkModifier (APK 修改)
    │               └── PluginManager (APK 插件管理)
    │
    ├── FrameworkModifier (Framework 修改)
    │       └── SmaliPatcher (Smali 补丁)
    │
    ├── FirmwareModifier (固件修改)
    │       ├── VBMetaPatcher
    │       ├── KernelSUInjector
    │       └── VendorBootPatcher
    │
    └── RomModifier (ROM 级修改)
```

### 4.4 Plugin System (插件系统)

**位置**: `src/core/modifiers/plugin_system.py`

**核心特性**:
- 基于优先级的执行顺序
- 依赖解析
- 并行执行支持
- 事务/回滚支持
- 超时控制
- 版本兼容性检查

**插件生命周期**:
```
1. 发现 (Discovery)
   └── 扫描 plugins/ 目录

2. 注册 (Registration)
   └── 验证元数据，加入注册表

3. 初始化 (Initialization)
   └── 调用 plugin.initialize()

4. 执行 (Execution)
   └── 按优先级执行 plugin.run()

5. 清理 (Cleanup)
   └── 调用 plugin.cleanup()
```

**内置插件执行顺序**:
| 优先级 | 插件 | 功能 |
|--------|------|------|
| 10 | WildBoost | 性能模块安装 |
| 20 | FileReplacement | 文件/目录替换 |
| 30 | FeatureUnlock | 功能开关 |
| 40 | VndkFix | VNDK/VINTF 修复 |
| 50 | EuLocalization | EU bundle 应用 |

### 4.5 Repacker (打包器)

**位置**: `src/core/packer.py`

**职责**: 将修改后的分区目录重新打包为可刷写的镜像文件。

**打包流程**:
```
修改后的目录
    │
    ├── EROFS 打包
    │   └── mkfs.erofs
    │
    ├── EXT4 打包
    │   ├── mke2fs (创建镜像)
    │   ├── e2fsdroid (填充数据)
    │   └── 大小优化
    │
    └── 输出格式
        ├── payload 模式
        │   └── payload.bin in ZIP
        │
        └── super 模式
            ├── super.img / super.zst
            └── 刷机脚本
```

---

## 5. 数据流

### 5.1 ROM 输入流程

```
ROM 文件 (zip/tgz/dir)
    │
    ▼
RomPackage._detect_type()
    │
    ├─► PAYLOAD: payload-dumper 提取
    ├─► BROTLI: brotli + sdat2img 转换
    ├─► FASTBOOT: lpunpack 解包
    └─► LOCAL_DIR: 直接访问
    │
    ▼
提取的 .img 文件 (work_dir/images/)
```

### 5.2 分区提取流程

```
.img 文件
    │
    ▼
extract_partition_to_file()
    │
    ├─► EROFS: extract.erofs
    └─► EXT4: debugfs 或挂载
    │
    ▼
提取的目录 + fs_config + file_contexts
```

### 5.3 修改流程

```
PortingContext
    │
    ▼
UnifiedModifier.run()
    │
    ├─► SystemModifier.run()
    │       └── PluginManager.execute()
    │               ├── WildBoost.run()
    │               ├── FileReplacement.run()
    │               ├── FeatureUnlock.run()
    │               ├── VndkFix.run()
    │               └── EuLocalization.run()
    │
    └─► ApkModifier.run()
            └── PluginManager.execute()
                    ├── JoyosePlugin.run()
                    ├── PowerKeeperPlugin.run()
                    └── SecurityCenterPlugin.run()
    │
    ▼
FrameworkModifier.run()
    │
    └── Smali 补丁 (miui-services.jar, services.jar, framework.jar)
    │
    ▼
FirmwareModifier.run()
    │
    ├─► VBMeta 补丁 (禁用 AVB)
    ├─► KernelSU 注入
    └─► vendor_boot fstab 补丁
```

### 5.4 打包流程

```
修改后的目录
    │
    ▼
Repacker.pack_all()
    │
    ├─► 检测文件系统类型 (EROFS/EXT4)
    │
    ├─► 打包每个分区
    │       ├─► mkfs.erofs (EROFS)
    │       └─► mke2fs + e2fsdroid (EXT4)
    │
    ▼
.img 文件
    │
    ├─► payload 模式
    │       └── pack_ota_payload() → payload.bin
    │
    └─► super 模式
            └── pack_super_image() → super.img/super.zst
    │
    ▼
生成刷机 ZIP 包
```

### 5.5 配置加载流程

```
devices/common/config.json (基础配置)
    │
    ▼
+ devices/<device>/config.json (设备配置)
    │
    ▼
ConfigMerger.deep_merge()
    │
    ▼
合并后的设备配置
    │
    ├─► features.json → 功能开关
    ├─► props.json → 属性覆盖
    └─► replacements.json → 文件替换规则
```

---

## 6. 扩展机制

### 6.1 添加新设备支持

1. 创建设备目录: `devices/<device_code>/`
2. 创建配置文件:
   - `config.json` - 设备配置
   - `features.json` - 功能开关
   - `props.json` - 属性覆盖
   - `replacements.json` - 文件替换规则
3. 添加覆盖文件到 `override/` 目录

### 6.2 添加新插件

1. 在 `src/core/modifiers/plugins/` 创建插件文件
2. 继承 `BasePlugin` 类
3. 实现必要的方法:
   ```python
   class MyPlugin(BasePlugin):
       name = "my_plugin"
       priority = 100  # 执行优先级
       version = "1.0.0"

       def initialize(self, context: PortingContext) -> None:
           pass

       def run(self, context: PortingContext) -> bool:
           # 实现修改逻辑
           return True

       def cleanup(self, context: PortingContext) -> None:
           pass
   ```
4. 插件会被自动发现和注册

### 6.3 添加新的修改器

1. 在 `src/core/modifiers/` 创建新的修改器文件
2. 继承 `BaseModifier` 类
3. 实现 `run()` 方法
4. 在 `main.py` 中集成

---

## 7. 依赖关系

### 7.1 Python 依赖

**生产依赖** (`requirements.txt`):
- `requests>=2.28.0` - HTTP 库，用于下载资源

**开发依赖** (`requirements-dev.txt`):
- `black` - 代码格式化
- `ruff` - 快速 Python linter
- `mypy` - 类型检查
- `pre-commit` - Git hooks
- `pytest` + 覆盖率插件

### 7.2 外部工具依赖

| 工具 | 用途 | 位置 |
|------|------|------|
| payload-dumper | 提取 payload.bin | `bin/linux/x86_64/` |
| lpunpack | 解包 super.img | `bin/linux/x86_64/` |
| extract.erofs | 解包 EROFS 镜像 | `bin/linux/x86_64/` |
| mkfs.erofs | 创建 EROFS 镜像 | `bin/linux/x86_64/` |
| brotli | 解压 .br 文件 | `bin/linux/x86_64/` |
| magiskboot | 启动镜像操作 | `bin/linux/x86_64/` |
| aapt2 | APK 编译 | `bin/linux/x86_64/` |
| apktool | APK 反编译 | `bin/apktool.jar` |
| smali/baksmali | Smali 操作 | `bin/smali.jar`, `bin/baksmali.jar` |
| APKEditor | APK 编辑 | `bin/APKEditor.jar` |

---

## 8. 输出格式

| 格式 | 用途 | 生成的文件 |
|------|------|------------|
| payload | Recovery/OTA 刷入 | ZIP 中的 payload.bin |
| super | Fastboot/混合刷入 | super.img/super.zst + 刷机脚本 |

---

## 9. 架构优势

1. **模块化设计**: 插件系统允许灵活扩展
2. **多格式支持**: 支持 payload、brotli、fastboot、目录等多种 ROM 格式
3. **配置驱动**: 设备配置与代码分离，易于适配新设备
4. **事务支持**: 支持回滚，提高可靠性
5. **并行执行**: 无依赖的插件可并行执行，提高效率
6. **类型安全**: 使用 Python 类型注解，配合 mypy 进行静态检查

---

## 10. 架构图总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              用户接口层                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                              main.py                                 │   │
│  │                    (命令行参数解析 + 流程编排)                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              核心业务层                                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐            │
│  │  PortingContext │  │   RomPackage    │  │    Repacker     │            │
│  │   (状态管理)    │  │  (ROM 处理)     │  │   (镜像打包)    │            │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘            │
│                                      │                                      │
│                                      ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         Modifier System                              │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────┐ │   │
│  │  │Unified       │ │Framework     │ │Firmware      │ │Rom         │ │   │
│  │  │Modifier      │ │Modifier      │ │Modifier      │ │Modifier    │ │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              插件扩展层                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         Plugin System                                │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │   │
│  │  │WildBoost │ │File      │ │Feature   │ │VndkFix   │ │EuLocal   │ │   │
│  │  │          │ │Replace   │ │Unlock    │ │          │ │ization   │ │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              工具服务层                                      │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │
│  │  shell.py   │ │downloader.py│ │ smalikit.py │ │ xml_utils.py│          │
│  │ (命令执行)  │ │ (资源下载)  │ │ (Smali操作) │ │ (XML处理)   │          │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              配置数据层                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    devices/<device>/                                  │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │   │
│  │  │config.   │ │features. │ │props.    │ │replace-  │ │override/ │ │   │
│  │  │json      │ │json      │ │json      │ │ments.json│ │          │ │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              外部工具层                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  bin/linux/x86_64/    │    bin/*.jar    │    bin/flash/             │   │
│  │  payload-dumper       │    apktool      │    flash scripts          │   │
│  │  lpunpack             │    smali        │    platform-tools         │   │
│  │  extract.erofs        │    baksmali     │                           │   │
│  │  mkfs.erofs           │    APKEditor    │                           │   │
│  │  magiskboot           │                 │                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```
