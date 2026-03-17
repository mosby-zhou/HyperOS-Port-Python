# HyperOS-Port-Python 细节文档

## 1. 核心类详解

### 1.1 PortingContext (移植上下文)

**文件位置**: `src/core/context.py`

`PortingContext` 是整个移植流程的中央状态管理器，保存所有必要的状态引用和工具路径。

#### 核心属性

```python
class PortingContext:
    # ROM 引用
    stock: RomPackage              # 原厂 ROM 包对象
    port: RomPackage               # 移植源 ROM 包对象
    is_official_modify: bool       # 是否为官改模式
    
    # 目录路径
    project_root: Path             # 项目根目录
    bin_root: Path                 # 二进制工具根目录
    target_dir: Path               # 目标工作目录 (build/target/)
    target_config_dir: Path        # 配置文件目录 (build/target/config/)
    repack_images_dir: Path        # 固件镜像目录 (build/target/repack_images/)
    
    # 工具路径 (自动检测平台)
    tools.magiskboot: Path         # magiskboot 路径
    tools.aapt2: Path              # aapt2 路径
    tools.apktool_jar: Path        # apktool JAR 路径
    tools.apkeditor_jar: Path      # APKEditor JAR 路径
    
    # ROM 信息
    base_android_version: str      # 底包 Android 版本
    port_android_version: str      # 移植包 Android 版本
    base_android_sdk: str          # 底包 SDK 版本
    port_android_sdk: str          # 移植包 SDK 版本
    stock_rom_code: str            # 底包设备代号
    port_rom_code: str             # 移植包设备代号
    target_rom_version: str        # 目标 ROM 版本号
    is_ab_device: bool             # 是否为 A/B 分区设备
    security_patch: str            # 安全补丁日期
    is_port_eu_rom: bool           # 移植包是否为 EU ROM
    
    # 功能开关
    enable_ksu: bool               # 是否启用 KernelSU
    
    # 辅助对象
    syncer: ROMSyncEngine          # ROM 同步引擎
    shell: ShellRunner             # Shell 命令执行器
```

#### 关键方法

| 方法 | 功能 | 返回值 |
|------|------|--------|
| `initialize_target()` | 初始化目标工作区，复制分区文件 | `None` |
| `get_rom_info()` | 获取并分析 ROM 信息 | `None` |
| `get_target_prop_file(part_name)` | 获取分区 build.prop 路径 | `Optional[Path]` |
| `build_apk_caches(force)` | 构建 APK 快速查找缓存 | `Dict[str, int]` |
| `find_apk_by_name(apk_name)` | 按文件名查找 APK | `Optional[Path]` |
| `find_apk_by_package(package_name)` | 按包名查找 APK | `Optional[Path]` |
| `clear_apk_caches()` | 清除 APK 缓存 | `None` |

#### 平台检测逻辑

```python
def _init_tools(self) -> None:
    system = platform.system().lower()    # windows, linux, darwin
    machine = platform.machine().lower()  # x86_64, amd64, aarch64, arm64
    
    # 架构统一化
    if machine in ["amd64", "x86_64"]:
        arch = "x86_64"
    elif machine in ["aarch64", "arm64"]:
        arch = "arm64"
    
    # 平台目录和扩展名
    if system == "windows":
        plat_dir, exe_ext = "windows", ".exe"
    elif system == "linux":
        plat_dir, exe_ext = "linux", ""
    elif system == "darwin":
        plat_dir, exe_ext = "macos", ""
    
    self.platform_bin_dir = self.bin_root / plat_dir / arch
```

---

### 1.2 RomPackage (ROM 包处理器)

**文件位置**: `src/core/rom/package.py`

`RomPackage` 表示一个 ROM 包，提供统一的接口处理不同格式的 ROM 文件。

#### ROM 类型枚举

```python
class RomType(Enum):
    UNKNOWN = 0      # 未知类型
    PAYLOAD = 1      # payload.bin 格式 (OTA/Recovery ROM)
    BROTLI = 2       # .new.dat.br 格式 (旧版 ROM)
    FASTBOOT = 3     # super.img 格式 (Fastboot ROM)
    LOCAL_DIR = 4    # 本地目录 (已解包)
```

#### 类型检测逻辑

```python
def _detect_type(self) -> None:
    if self.path.is_dir():
        self.rom_type = RomType.LOCAL_DIR
        return
    
    if zipfile.is_zipfile(self.path):
        with zipfile.ZipFile(self.path, "r") as z:
            namelist = z.namelist()
            if "payload.bin" in namelist:
                self.rom_type = RomType.PAYLOAD
            elif any(x.endswith("new.dat.br") for x in namelist):
                self.rom_type = RomType.BROTLI
            elif "super.img" in namelist or "images/super.img" in namelist:
                self.rom_type = RomType.FASTBOOT
    elif self.path.suffix == ".tgz":
        self.rom_type = RomType.FASTBOOT
```

#### 提取流程

| ROM 类型 | 提取工具 | 输出 |
|----------|----------|------|
| PAYLOAD | `payload-dumper` | `.img` 文件 |
| BROTLI | `brotli` + `sdat2img` | `.img` 文件 |
| FASTBOOT | `lpunpack` | `.img` 文件 |
| LOCAL_DIR | 无需提取 | 直接访问 |

#### 变更检测机制

```python
# 使用 SHA256 哈希检测源文件变更
source_hash_path = self.work_dir / "source_file.hash"
current_source_hash = compute_file_hash(self.path)

if source_hash_path.exists():
    saved_hash = source_hash_path.read_text().strip()
    source_changed = saved_hash != current_source_hash
else:
    source_changed = True

# 如果源文件未变更，使用缓存
if not source_changed and has_valid_cache():
    use_cached_images()
```

---

### 1.3 UnifiedModifier (统一修改器)

**文件位置**: `src/core/modifiers/unified_modifier.py`

`UnifiedModifier` 是系统级和 APK 级修改的统一入口点。

#### 架构设计

```
UnifiedModifier
    │
    ├── system_manager (PluginManager)
    │       ├── WildBoostPlugin
    │       ├── FileReplacementPlugin
    │       ├── FeatureUnlockPlugin
    │       ├── VNDKFixPlugin
    │       └── EULocalizationPlugin
    │
    └── apk_manager (PluginManager)
            ├── InstallerModifier
            ├── SecurityCenterModifier
            ├── SettingsModifier
            ├── JoyoseModifier
            ├── PowerKeeperModifier
            └── DevicesOverlayModifier
```

#### 执行流程

```python
def run(self, phases: Optional[List[str]] = None) -> bool:
    phases = phases or ["system", "apk"]
    
    # Phase 1: 系统级修改
    if "system" in phases:
        results = self.system_manager.execute()
        # 统计成功/失败/跳过数量
    
    # Phase 2: APK 级修改
    if "apk" in phases and self.apk_manager:
        # 构建 APK 缓存
        self.ctx.build_apk_caches()
        results = self.apk_manager.execute()
    
    return all_success
```

---

## 2. 插件系统详解

### 2.1 ModifierPlugin 基类

**文件位置**: `src/core/modifiers/plugin_system.py`

```python
class ModifierPlugin(ABC):
    # 元数据
    name: str = ""                  # 插件名称
    description: str = ""           # 描述
    version: str = "1.0"            # 版本
    priority: int = 100             # 执行优先级 (数值越小越先执行)
    min_version: Optional[str]      # 最低 ROM 版本要求
    max_version: Optional[str]      # 最高 ROM 版本支持
    dependencies: List[str] = []    # 必须依赖的插件
    soft_dependencies: List[str]    # 可选依赖
    timeout: Optional[float]        # 超时时间 (秒)
    parallel_safe: bool = True      # 是否可并行执行
    
    # 核心方法
    @abstractmethod
    def modify(self) -> bool:
        """执行修改逻辑，返回成功/失败"""
        pass
    
    def check_prerequisites(self) -> bool:
        """前置条件检查，返回 False 则跳过执行"""
        return True
```

### 2.2 PluginManager (插件管理器)

```python
class PluginManager:
    def __init__(
        self,
        context: Any,
        logger: Optional[logging.Logger] = None,
        backup_dir: Optional[Path] = None,
        enable_transactions: bool = True,
        max_workers: int = 4,
        dry_run: bool = False,
    ):
        self._plugins: Dict[str, ModifierPlugin] = {}
        self._hooks: Dict[str, List[Callable]] = {
            "pre_modify": [],
            "post_modify": [],
            "on_error": [],
        }
        self._transaction_manager: Optional[TransactionManager] = None
```

#### 插件排序算法

```python
def _sort_plugins(self) -> List[ModifierPlugin]:
    """按优先级排序并解析依赖关系"""
    plugins = [p for p in self._plugins.values() if p.enabled]
    
    resolved = []
    unresolved = set(p.name for p in plugins)
    
    while unresolved:
        # 找到所有依赖已满足的插件
        ready = []
        for name in list(unresolved):
            plugin = self._plugins[name]
            deps_satisfied = all(
                dep in [r.name for r in resolved]
                for dep in plugin.dependencies
            )
            if deps_satisfied:
                ready.append(plugin)
        
        if not ready:
            # 循环依赖或缺失依赖
            break
        
        # 按优先级排序
        ready.sort(key=lambda p: p.priority)
        resolved.extend(ready)
        
        for plugin in ready:
            unresolved.remove(plugin.name)
    
    return resolved
```

#### 并行执行逻辑

```python
def execute(self, plugin_names: Optional[List[str]] = None) -> Dict[str, bool]:
    plugins = self._sort_plugins()
    
    # 按优先级分组
    priority_groups = self._group_by_priority(plugins)
    
    for priority in sorted(priority_groups.keys()):
        group = priority_groups[priority]
        
        # 检查是否所有插件都支持并行
        parallel_safe = all(p.parallel_safe for p in group)
        
        if parallel_safe and len(group) > 1:
            # 并行执行
            with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
                futures = {
                    executor.submit(self._execute_single_plugin, p): p
                    for p in group
                }
                # 收集结果...
        else:
            # 串行执行
            for plugin in group:
                results[plugin.name] = self._execute_single_plugin(plugin)
    
    return results
```

---

## 3. 内置插件详解

### 3.1 WildBoostPlugin (性能增强插件)

**文件位置**: `src/core/modifiers/plugins/wild_boost.py`

**功能**: 安装 wild_boost 性能增强内核模块，实现设备伪装。

#### KMI 版本检测

```python
def _get_kernel_version(self) -> str:
    boot_img = self.ctx.repack_images_dir / "boot.img"
    kmi = self._analyze_kmi(boot_img)
    # 返回格式: "android14-5.15"
    return kmi

def _analyze_kmi(self, boot_img: Path) -> str:
    # 解压 boot.img
    magiskboot unpack boot.img
    
    # 从 kernel 文件中提取字符串
    # 查找 "5.15.78-android14-11" 模式
    pattern = re.compile(r"(?:^|\s)(\d+\.\d+)\S*(android\d+)")
    for s in strings:
        if "Linux version" in s or "android" in s:
            match = pattern.search(s)
            if match:
                return f"{match.group(2)}-{match.group(1)}"
```

#### 安装策略

| 内核版本 | 安装位置 | 原因 |
|----------|----------|------|
| 5.10 | vendor_boot ramdisk | 旧版 GKI 设备 |
| 5.15+ | vendor_dlkm | 新版 GKI 设备 |
| 6.12 | vendor_boot ramdisk | Android 16 KMI |

#### 设备伪装 (HexPatch)

```python
def _apply_libmigui_hexpatch(self) -> bool:
    patches = [
        {
            "old": bytes.fromhex("726F2E70726F647563742E70726F647563742E6E616D65"),
            "new": bytes.fromhex("726F2E70726F647563742E73706F6F6665642E6E616D65"),
        },
        # ro.product.product.name -> ro.product.spoofed.name
    ]
    
    for libmigui in target_dir.rglob("libmigui.so"):
        content = libmigui.read_bytes()
        for patch in patches:
            content = content.replace(patch["old"], patch["new"])
        libmigui.write_bytes(content)
```

---

### 3.2 FirmwareModifier (固件修改器)

**文件位置**: `src/core/modifiers/firmware_modifier.py`

**功能**: VBMeta 补丁、KernelSU 注入、vendor_boot fstab 修改。

#### VBMeta 补丁

```python
def _patch_vbmeta(self):
    AVB_MAGIC = b"AVB0"
    FLAGS_OFFSET = 123
    FLAGS_TO_SET = b"\x03"  # 禁用 AVB 验证
    
    for img_path in self.ctx.target_dir.rglob("vbmeta*.img"):
        with open(img_path, "r+b") as f:
            magic = f.read(4)
            if magic == AVB_MAGIC:
                f.seek(FLAGS_OFFSET)
                f.write(FLAGS_TO_SET)
```

#### vendor_boot fstab 补丁 (Android 16)

```python
def _patch_vendor_boot_fstab(self):
    """针对 KMI 6.12 的特殊处理"""
    # 解压 vendor_boot.img
    magiskboot unpack vendor_boot.img
    
    # 解压 ramdisk.cpio
    magiskboot decompress ramdisk.cpio
    
    # 提取并修改 fstab
    for fstab_path in extract_dir.rglob("fstab.*"):
        content = fstab_path.read_text()
        new_content = self._disable_avb_verify(content)
        fstab_path.write_text(new_content)
    
    # 重新打包
    magiskboot repack vendor_boot.img

def _disable_avb_verify(self, content: str) -> str:
    # 移除所有 AVB 相关标志
    content = re.sub(r",avb_keys=[^, \n]*avbpubkey", "", content)
    content = re.sub(r",avb=vbmeta_system", "", content)
    content = re.sub(r",avb=vbmeta_vendor", "", content)
    content = re.sub(r",avb=vbmeta", "", content)
    content = re.sub(r",avb", "", content)
    return content
```

#### KernelSU 注入

```python
def _apply_ksu_patch(self, target_img, kmi_version):
    # 解压 boot/init_boot
    magiskboot unpack boot.img
    
    # 备份原始 init
    magiskboot cpio ramdisk.cpio "mv init init.real"
    
    # 添加 ksuinit
    magiskboot cpio ramdisk.cpio "add 0755 init init"
    
    # 添加 kernelsu.ko
    magiskboot cpio ramdisk.cpio "add 0755 kernelsu.ko kernelsu.ko"
    
    # 重新打包
    magiskboot repack boot.img
```

---

## 4. Repacker (打包器) 详解

**文件位置**: `src/core/packer.py`

### 4.1 分区打包流程

```python
def pack_all(self, pack_type: str = "EROFS", is_rw: bool = False):
    # 获取所有分区目录
    partitions = [
        item.name for item in self.ctx.target_dir.iterdir()
        if item.is_dir() and item.name not in ["config", "repack_images"]
    ]
    
    # 并行打包
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(self._pack_partition, part, pack_type, is_rw)
            for part in partitions
        ]
```

### 4.2 EROFS 打包

```python
def _pack_erofs(self, part_name, src_dir, img_output, fs_config, file_contexts):
    cmd = [
        "mkfs.erofs",
        "-zlz4hc,9",                    # LZ4HC 压缩，级别 9
        "-T", self.fix_timestamp,       # 固定时间戳
        "--mount-point", f"/{part_name}",
        "--fs-config-file", str(fs_config),
        "--file-contexts", str(file_contexts),
        str(img_output),
        str(src_dir),
    ]
    self.shell.run(cmd)
```

### 4.3 EXT4 打包

```python
def _pack_ext4(self, part_name, src_dir, img_output, fs_config, file_contexts, is_rw):
    # 计算大小
    size_orig = self._get_dir_size(src_dir)
    if size_orig < 1048576:       # < 1MB
        size = 1048576
    elif size_orig < 104857600:   # < 100MB
        size = int(size_orig * 1.15)
    elif size_orig < 1073741824:  # < 1GB
        size = int(size_orig * 1.08)
    else:
        size = int(size_orig * 1.03)
    
    # 创建镜像
    self._make_ext4_image(part_name, src_dir, img_output, size, ...)
    
    # 优化大小
    self.shell.run(["resize2fs", "-f", "-M", str(img_output)])
    
    # 计算空闲块，可能重新生成
    free_blocks = self._get_free_blocks(img_output)
    if free_blocks > 0:
        # 重新生成更小的镜像
        ...
```

### 4.4 Super Image 打包

```python
def pack_super_image(self):
    lpmake_path = self.ota_tools_dir / "bin" / "lpmake"
    super_size = self._get_super_size()  # 从设备配置或硬编码获取
    
    base_args = [
        str(lpmake_path),
        "--metadata-size", "65536",
        "--super-name", "super",
        "--block-size", "4096",
        "--device", f"super:{super_size}",
        "--output", str(super_img),
    ]
    
    if not self.ctx.is_ab_device:
        # A-only设备
        base_args.extend([
            "--metadata-slots", "2",
            "--group", f"qti_dynamic_partitions:{super_size}",
        ])
    else:
        # A/B设备
        base_args.extend([
            "--virtual-ab",
            "--metadata-slots", "3",
            "--group", f"qti_dynamic_partitions_a:{super_size}",
            "--group", f"qti_dynamic_partitions_b:{super_size}",
        ])
    
    self.shell.run(base_args)
```

---

## 5. 配置系统详解

### 5.1 配置层级

```
devices/
├── common/                    # 第一层：通用配置
│   ├── config.json           # 默认配置
│   ├── features.json         # 通用功能开关
│   ├── replacements.json     # 通用文件替换
│   └── props_global.json     # 全局属性覆盖
│
└── <device_code>/            # 第二层：设备配置
    ├── config.json           # 设备配置 (覆盖通用)
    ├── features.json         # 设备功能开关
    ├── props.json            # 设备属性覆盖
    └── replacements.json     # 设备文件替换
```

### 5.2 配置合并逻辑

```python
class ConfigMerger:
    def deep_merge(self, base: dict, override: dict) -> dict:
        result = base.copy()
        
        for key, value in override.items():
            if key.startswith("_"):  # 跳过元数据
                continue
            
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self.deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def load_device_config(self, device_codename: str) -> dict:
        # 加载通用配置
        common_config = self.load_config(devices_dir / "common" / "config.json")
        
        # 加载设备配置
        device_config = self.load_config(devices_dir / device_codename / "config.json")
        
        # 深度合并
        return self.deep_merge(common_config, device_config)
```

### 5.3 配置优先级

```
CLI 参数 > 设备配置 (devices/<device>/config.json) > 通用配置 (devices/common/config.json)
```

---

## 6. 工具模块详解

### 6.1 ShellRunner (命令执行器)

**文件位置**: `src/utils/shell.py`

```python
class ShellRunner:
    def run(
        self,
        cmd: Union[str, List[str]],
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        capture_output: bool = False,
        check: bool = True,
        shell: bool = False,
    ) -> subprocess.CompletedProcess:
        # 执行命令并处理错误
        ...
```

### 6.2 ROMSyncEngine (同步引擎)

**文件位置**: `src/utils/sync_engine.py`

**功能**: APK 快速查找缓存管理。

```python
class ROMSyncEngine:
    def find_apk_by_name(self, apk_name: str, target_dir: Path) -> Optional[Path]:
        # 构建名称缓存 (首次调用)
        if not self._target_rom_cache:
            self._build_name_cache(target_dir)
        return self._target_rom_cache.get(apk_name.lower())
    
    def find_apk_by_package(self, package_name: str, target_dir: Path) -> Optional[Path]:
        # 构建包名缓存 (首次调用)
        if not self._target_package_cache:
            self._build_package_cache(target_dir)
        return self._target_package_cache.get(package_name)
```

### 6.3 OtaToolsManager (OTA 工具管理器)

**文件位置**: `src/utils/otatools_manager.py`

```python
class OtaToolsManager:
    DEFAULT_URL = "https://github.com/.../otatools.zip"
    
    def ensure_otatools(self) -> bool:
        if self.check_otatools_exists():
            return True
        return self.download_otatools()
```

---

## 7. 分区映射策略

### 7.1 分区来源

| 分区 | 来源 | 原因 |
|------|------|------|
| vendor | Stock (底包) | 硬件驱动，必须使用原厂 |
| odm | Stock (底包) | ODM 定制内容 |
| vendor_dlkm | Stock (底包) | 内核模块 |
| odm_dlkm | Stock (底包) | ODM 内核模块 |
| system_dlkm | Stock (底包) | 系统内核模块 |
| system | Port (移植包) | 系统框架 |
| system_ext | Port (移植包) | 系统扩展 |
| product | Port (移植包) | 产品分区 |
| mi_ext | Port (移植包) | MIUI 扩展 |
| product_dlkm | Port (移植包) | 产品内核模块 |

### 7.2 固件镜像

固件镜像直接从底包复制，不进行修改：

- boot.img
- dtbo.img
- vbmeta*.img
- xbl*.img
- tz*.img
- 等等...
