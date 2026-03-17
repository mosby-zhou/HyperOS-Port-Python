# HyperOS-Port-Python 原理文档

## 1. ROM 移植核心原理

### 1.1 什么是 ROM 移植？

ROM 移植是指将一个设备（移植源设备）的 ROM 系统移植到另一个设备（目标设备）上运行的过程。由于不同设备的硬件差异，直接刷入其他设备的 ROM 会导致无法启动或功能异常，因此需要进行移植处理。

### 1.2 移植的核心挑战

| 挑战 | 描述 | 解决方案 |
|------|------|----------|
| 硬件驱动差异 | 不同设备有不同的硬件配置 | 保留原厂 vendor 分区 |
| 系统框架差异 | 不同 Android 版本的 API 差异 | 版本检测与兼容性处理 |
| 分区布局差异 | A-only vs A/B 分区 | 自动检测并适配 |
| 安全验证 | AVB/VBMeta 验证 | 禁用 AVB 或修补 vbmeta |
| 设备检测 | 应用检测设备型号 | 设备伪装技术 |

### 1.3 移植策略

本工具采用 **"保留底层，替换系统"** 的策略：

```
┌─────────────────────────────────────────────────────────────┐
│                    ROM 移植架构                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                    系统层 (来自移植包)                    ││
│  │  system, system_ext, product, mi_ext, product_dlkm      ││
│  │  - 系统框架                                              ││
│  │  - 预装应用                                              ││
│  │  - MIUI 特性                                             ││
│  └─────────────────────────────────────────────────────────┘│
│                           │                                  │
│                           ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                    硬件抽象层 (来自底包)                  ││
│  │  vendor, odm, vendor_dlkm, odm_dlkm, system_dlkm        ││
│  │  - 硬件驱动                                              ││
│  │  - HAL 模块                                              ││
│  │  - 内核模块                                              ││
│  └─────────────────────────────────────────────────────────┘│
│                           │                                  │
│                           ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                    固件层 (来自底包)                      ││
│  │  boot, vbmeta, dtbo, xbl, tz, modem...                  ││
│  │  - 启动镜像                                              ││
│  │  - 安全固件                                              ││
│  │  - 通信固件                                              ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. ROM 格式解析原理

### 2.1 Payload 格式 (OTA/Recovery ROM)

**结构**:
```
ROM.zip
├── payload.bin          # 主要系统数据
├── payload.properties    # 元数据
├── care_map.pb          # 分区校验信息
└── META-INF/            # 刷机脚本
```

**解析原理**:

`payload.bin` 使用 Google 的 AOSP OTA 更新格式，包含：
- Payload Header: 版本信息、分区列表
- Data Blobs: 压缩的分区数据
- Manifest: 分区元数据

```python
# payload-dumper 工作原理
1. 读取 payload.bin 头部
2. 解析 Manifest 获取分区列表
3. 按需解压并提取各分区镜像
4. 输出 .img 文件
```

### 2.2 Brotli 格式 (旧版 ROM)

**结构**:
```
ROM.zip
├── system.new.dat.br    # 系统分区数据 (Brotli 压缩)
├── system.transfer.list # 数据传输列表
├── system.patch.dat     # 增量补丁 (可选)
└── ...
```

**解析原理**:

```
.new.dat.br ──brotli解压──► .new.dat ──sdat2img──► .img
                                    │
                                    └── transfer.list 指导数据块重组
```

### 2.3 Fastboot 格式

**结构**:
```
ROM.zip / ROM.tgz
├── super.img            # 动态分区镜像
├── boot.img             # 启动镜像
├── vbmeta.img           # 验证元数据
├── firmware-update/     # 固件文件
└── ...
```

**解析原理**:

`super.img` 是 Android 动态分区容器：
```
super.img
├── Metadata (分区表)
├── system_a
├── vendor_a
├── product_a
└── ...
```

使用 `lpunpack` 解包：
```bash
lpunpack -p system super.img output_dir/
```

---

## 3. 镜像文件系统原理

### 3.1 EROFS (Enhanced Read-Only File System)

**特点**:
- 只读文件系统，启动后不可修改
- 使用 LZ4/LZ4HC 压缩，压缩比和速度平衡
- 支持块级去重
- Android 10+ 主流格式

**镜像结构**:
```
EROFS Image
├── Super Block           # 文件系统元信息
├── Inodes               # 文件/目录节点
├── Data Blocks          # 压缩数据块
└── Xattrs               # 扩展属性 (SELinux 标签)
```

**解包/打包**:
```bash
# 解包
extract.erofs -i system.img -o output_dir/

# 打包
mkfs.erofs -zlz4hc,9 --mount-point /system \
    --fs-config-file fs_config \
    --file-contexts file_contexts \
    system.img input_dir/
```

### 3.2 EXT4 (Fourth Extended Filesystem)

**特点**:
- 传统读写文件系统
- 支持 journal、ACL、扩展属性
- 兼容性好，但占用空间较大

**镜像创建流程**:
```
1. mke2fs  创建空镜像
2. e2fsdroid 填充数据、设置权限
3. resize2fs 优化大小
```

---

## 4. Android 启动流程与移植适配

### 4.1 标准启动流程

```
Boot ROM (硬件)
    │
    ▼
Bootloader (ABL/XBL)
    │ 验证 boot.img 签名
    ▼
boot.img
    │ 加载内核 + ramdisk
    ▼
Kernel
    │ 挂载 rootfs
    ▼
init 进程
    │ 解析 init.rc
    │ 挂载分区
    ▼
┌─────────────────────────────────────┐
│ 分区挂载                             │
│ ├── /system      (system.img)       │
│ ├── /vendor      (vendor.img)       │
│ ├── /product     (product.img)      │
│ ├── /system_ext  (system_ext.img)   │
│ └── ...                             │
└─────────────────────────────────────┘
    │
    ▼
Zygote → System Server → 应用启动
```

### 4.2 AVB (Android Verified Boot) 原理

**验证链**:
```
Boot ROM
    │ 验证 Bootloader 签名
    ▼
Bootloader
    │ 验证 vbmeta 签名
    ▼
vbmeta.img
    │ 包含各分区的哈希/哈希树
    ▼
各分区 (boot, system, vendor...)
    │ 启动时验证完整性
    ▼
系统启动
```

**vbmeta 结构**:
```
VBMeta Header (固定大小)
├── Magic: "AVB0"
├── Version
├── Flags (验证开关)
├── Release/Security Patch
└── Descriptors
    ├── Hash Descriptor (boot, dtbo)
    └── Hash Tree Descriptor (system, vendor)
```

**禁用 AVB 的方法**:

1. **修补 vbmeta 镜像** (本项目采用):
   ```python
   # 偏移 123 字节处设置 flags = 0x03
   FLAGS_OFFSET = 123
   FLAGS_TO_SET = b"\x03"  # 禁用验证
   ```

2. **修改 fstab** (Android 16 KMI 6.12):
   ```bash
   # 移除 AVB 相关挂载选项
   sed -i "s/,avb=vbmeta//g" fstab.qcom
   sed -i "s/,avb//g" fstab.qcom
   ```

### 4.3 KernelSU 注入原理

**GKI (Generic Kernel Image) 架构**:

Android 11+ 的 GKI 将内核分为：
- **GKI Kernel**: 通用内核镜像 (来自 Google)
- **Vendor Modules**: 厂商内核模块 (vendor_dlkm)
- **Boot Ramdisk**: 初始化 ramdisk (init_boot)

**KernelSU 注入点**:

```
init_boot.img / boot.img
├── kernel              # GKI 内核 (不修改)
└── ramdisk.cpio        # 初始化 ramdisk
    ├── init            # ← 注入点：替换为 ksuinit
    ├── init.real       # 原始 init (重命名)
    └── kernelsu.ko     # KernelSU 内核模块
```

**工作流程**:
```
1. ksuinit 启动
2. 加载 kernelsu.ko 到内核
3. ksuinit exec 到 init.real
4. 正常启动流程继续
5. KernelSU 在内核中拦截系统调用，实现 root
```

---

## 5. Wild Boost 性能增强原理

### 5.1 核心机制

Wild Boost 通过内核模块修改 CPU 调度行为：

```
perfmgr.ko
├── 修改 CPU 频率策略
├── 修改调度器参数
└── 绕过性能限制
```

### 5.2 设备伪装原理

小米应用通过 `ro.product.product.name` 等属性检测设备型号：

```java
// 小米应用检测示例
String device = SystemProperties.get("ro.product.product.name");
if (device.equals("fuxi")) {
    // 小米 13 功能限制
}
```

**绕过方法**:

1. **属性伪装** (features.json):
   ```json
   {
       "build_props": {
           "product": {
               "ro.product.spoofed.name": "vermeer"
           }
       }
   }
   ```

2. **HexPatch libmigui.so**:
   ```
   原始: ro.product.product.name
   修改: ro.product.spoofed.name
   ```
   
   应用读取 `ro.product.product.name` 时，实际读取到伪装的值。

### 5.3 安装位置选择

| 内核版本 | 位置 | 原因 |
|----------|------|------|
| 5.10 | vendor_boot ramdisk | GKI 1.0，vendor_dlkm 可能不存在 |
| 5.15+ | vendor_dlkm | GKI 2.0，推荐位置 |
| 6.12 | vendor_boot ramdisk | 特殊处理，绕过 Fastboot 卡死问题 |

---

## 6. 文件替换与功能恢复原理

### 6.1 replacements.json 工作原理

```json
[
    {
        "description": "替换设备 Overlay",
        "type": "file",
        "search_path": "product",
        "files": ["DevicesOverlay.apk"],
        "source": "override/DevicesOverlay.apk"
    }
]
```

**执行流程**:
```
1. 在目标分区搜索指定文件
2. 备份原文件 (可选)
3. 复制替换文件
4. 恢复 SELinux 上下文
```

### 6.2 SELinux 上下文处理

文件替换后需要正确设置 SELinux 标签：

```python
# file_contexts 格式
/system/bin/cameraserver    u:object_r:cameraserver_exec:s0

# 修补流程
1. 提取 file_contexts
2. 应用 contextpatch (修正路径差异)
3. 使用 restorecon 或 e2fsdroid 应用标签
```

### 6.3 fs_config 权限处理

```python
# fs_config 格式
system 0 2000 0755
system/bin 0 2000 0755
system/bin/app_process 0 2000 0755
# 文件路径 UID GID 模式

# 修补流程
1. 提取 fs_config
2. 应用 fspatch (修正路径差异)
3. 打包时使用 --fs-config-file 参数
```

---

## 7. 版本号生成原理

### 7.1 MIUI 版本号格式

```
1.0.5.0.UMCCNXM
│ │ │ │ │││└─── 设备区域标识 (XM = 国行)
│ │ │ │ ││└──── 区域代码 (CN)
│ │ │ │ │└───── 设备代号 (M)
│ │ │ │ └────── 版本前缀 (U = Android 14)
│ │ │ └──────── 小版本号
│ │ └────────── 次版本号
│ └──────────── 主版本号
└────────────── 大版本号
```

### 7.2 移植版本号生成

```python
# 底包版本: 1.0.5.0.UMCCNXM (小米 13C)
# 移植包版本: 2.0.8.0.VNBUXM (小米 14)

# 生成目标版本:
# 1. 提取底包设备代号段: MCC
# 2. 确定新前缀: V (Android 15)
# 3. 组合: VMCC
# 4. 替换: 2.0.8.0.VMCCNXM
```

---

## 8. 并行处理原理

### 8.1 分区并行处理

```python
with ThreadPoolExecutor(max_workers=4) as executor:
    futures = [
        executor.submit(extract_partition, part)
        for part in partitions
    ]
```

**可并行的操作**:
- 分区解包
- 分区打包
- APK 缓存构建

**不可并行的操作**:
- 有依赖关系的插件
- 修改共享资源的操作

### 8.2 插件并行执行

```
优先级分组:
├── Priority 10: WildBoost (单独执行)
├── Priority 20: FileReplacement, OtherPlugin (可并行)
├── Priority 30: FeatureUnlock (单独执行，依赖 Priority 10)
└── Priority 40+: 其他插件
```

---

## 9. 缓存与增量处理原理

### 9.1 源文件变更检测

```python
# 计算源文件 SHA256 哈希
current_hash = hashlib.sha256(source_file.read_bytes()).hexdigest()

# 与保存的哈希比较
if current_hash != saved_hash:
    # 源文件变更，重新处理
    reprocess()
else:
    # 使用缓存
    use_cache()
```

### 9.2 APK 查找缓存

```python
# 首次查找时构建缓存
_target_rom_cache: Dict[str, Path] = {}    # 文件名 → 路径
_target_package_cache: Dict[str, Path] = {} # 包名 → 路径

# 后续查找 O(1)
def find_apk_by_name(name: str) -> Path:
    return _target_rom_cache.get(name.lower())
```

---

## 10. 错误处理与回滚原理

### 10.1 事务系统

```python
class TransactionManager:
    def record_modification(self, path: Path, action: str) -> Path:
        # 创建备份
        backup_path = self.backup_dir / f"{path.name}.bak"
        shutil.copy2(path, backup_path)
        return backup_path
    
    def rollback_all(self) -> int:
        # 恢复所有备份
        for record in self.records:
            shutil.move(record.backup, record.original)
```

### 10.2 插件错误隔离

```python
try:
    success = plugin.modify()
except Exception as e:
    self.logger.error(f"Plugin {plugin.name} failed: {e}")
    # 继续执行其他插件
    results[plugin.name] = False
```
