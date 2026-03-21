# 禁用 Data 加密功能设计文档

**版本**: 1.0
**日期**: 2026-03-21
**状态**: 方案待实现

---

## 一、概述

### 1.1 目标

创建独立的命令行工具，用于禁用 Android FBE (File-Based Encryption) 加密，让新格式化的 data 分区不再加密。

### 1.2 背景
在 ROM 移植场景下，有时需要禁用 data 分区加密以便：
- 在 TWRP 中访问加密数据
- 进行数据取证或恢复
- 特殊场景测试

### 1.3 范围
- 输入: 已解包的 vendor 目录 或 super.img
- 输出: 修改后的 vendor.img
- 支持的加密类型: FBE (File-Based Encryption)

---

## 二、架构设计

### 2.1 目录结构

```
tools/disable_encryption/
├── disable_encryption.py    # 主入口和核心逻辑
├── fstab_parser.py        # fstab 文件解析和修改
├── erofs_packer.py       # EROFS 镜像打包
└── README.md              # 使用说明
```

### 2.2 依赖关系
- 纯 Python 实现，- 无外部工具依赖
- 可选依赖项目现有的 `src/utils/shell.py` 用于命令执行

---

## 三、核心功能

### 3.1 命令行接口
```bash
python tools/disable_encryption/disable_encryption.py [options]

选项:
  --vendor-dir PATH       vendor 目录路径 (必需)
  --output PATH           输出 vendor.img 路径 (可选，默认覆盖原文件)
  --cluster-size SIZE     EROFS 簇大小 (可选，默认自动检测)
  --force-cluster         强制使用指定的簇大小，不进行自动检测
  --dry-run              只显示将要修改的内容，不实际执行
  -v, --verbose           显示详细输出
```

### 3.2 簇大小自动检测逻辑

工具会按以下优先级确定簇大小：

1. **用户强制指定** (`--cluster-size` + `--force-cluster`)
   - 直接使用用户指定的值

2. **从原镜像检测** (推荐)
   - 检测是否存在原始 vendor.img
   - 使用 `dump.erofs` 或解析 EROFS superblock 获取簇大小
   - 这是默认行为

3. **根据分区大小估算** (兜底)
   - 分区 < 1GB: 4096 (4KB)
   - 分区 1-3GB: 16384 (16KB)
   - 分区 > 3GB: 65536 (64KB)

**自动检测代码示例**:
```python
def detect_cluster_size(vendor_dir: Path, original_img: Path = None) -> int:
    """检测 EROFS 簇大小"""

    # 1. 如果有原始镜像，从中读取
    if original_img and original_img.exists():
        cluster_size = read_erofs_cluster_size(original_img)
        if cluster_size:
            return cluster_size

    # 2. 根据目录大小估算
    dir_size = get_dir_size(vendor_dir)
    if dir_size < 1024 * 1024 * 1024:  # < 1GB
        return 4096
    elif dir_size < 3 * 1024 * 1024 * 1024:  # < 3GB
        return 16384
    else:
        return 65536

def read_erofs_cluster_size(img_path: Path) -> Optional[int]:
    """从 EROFS 镜像读取簇大小"""
    # EROFS superblock 位于偏移 1024
    # 偏移 20-24: blkszbits (log2 of block size)
    try:
        with open(img_path, 'rb') as f:
            f.seek(1024 + 20)
            blkszbits = struct.unpack('<I', f.read(4))[0]
            return 1 << blkszbits  # 2^blkszbits
    except:
        return None
```

### 3.2 fstab 修改逻辑

**查找文件**:
- `vendor/etc/fstab.qcom`
- `vendor/etc/fstab.postinstall`
- `vendor/etc/fstab.*`

**修改规则**:
删除以下挂载选项:
- `fileencryption=...`
- `forceencrypt=...`
- `encryptable=...`

**保留其他选项**: 如 `nosuid`, `nodev`, `noatime` 等

### 3.3 EROFS 打包
使用项目现有的 Python EROFS 打包逻辑:
- 调用 `src/core/packer.py` 中的相关函数
- 或实现独立的打包逻辑

**参数**:
- `-zlz4hc,9`: 压缩级别
- `-C16384`: 簇大小
- `--mount-point /vendor`
- `--fs-config-file`
- `--file-contexts`

---

## 四、数据流

```
┌─────────────────────────────────────────────────────────────┐
│                         用户输入                                │
│  --vendor-dir build/target/vendor                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     fstab_parser.py                     │
│  1. 查找 fstab 文件                                │
│  2. 解析并识别加密选项                        │
│  3. 删除 fileencryption 相关选项             │
│  4. 备份原始文件                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     erofs_packer.py                     │
│  1. 检查 vendor 目录结构                        │
│  2. 调用打包逻辑                            │
│  3. 生成 vendor.img                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       输出                                  │
│  - vendor.img 文件                           │
│  - 操作指南和注意事项                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 五、输出内容

### 5.1 终端输出
- 修改的 fstab 文件路径
- 删除的加密选项
- 打包进度
- 输出文件路径

### 5.2 操作指南
工具执行完成后显示:
```
========================================
Data 加密禁用完成
========================================

接下来的步骤:
1. 进入 fastbootd 模式:
   adb reboot bootloader
   选择 "Enter fastbootd" 或使用:
   fastboot reboot fastboot

2. 刷入修改后的 vendor 镜像:
   fastboot update-super vendor vendor.img
   (注意: 使用 update-super 而非 flash)

3. 关闭 vbmeta 校验:
   fastboot --disable-verity
   fastboot flash vbmeta --disable-verity

   或刷入修改后的 vbmeta:
   fastboot flash vbmeta vbmeta.img

4. 擦除 userdata 分区 (会清除所有用户数据):
   fastboot erase userdata
   fastboot erase metadata

5. 重启设备:
   fastboot reboot

注意:
- 此操作会清除所有用户数据
- 重启后 data 分区将不再加密
- 部分应用可能拒绝工作(如银行、支付应用)
```

---

## 六、错误处理

### 6.1 输入验证
- vendor 目录不存在
- vendor 目录中没有 fstab 文件
- 无法识别加密选项

### 6.2 处理失败
- 打包失败时恢复原始 fstab 文件
- 显示详细错误信息

---

## 七、测试用例
1. 正常流程: 输入有效 vendor 目录，成功禁用加密
2. 无加密选项: fstab 中没有加密选项,跳过修改
3. 多个 fstab: 存在多个 fstab 文件,全部处理
4. 打包失败: 恢复原始文件并报错

---

## 八、安全考虑
- 备份原始 fstab 文件
- dry-run 模式预览修改
- 打包失败时自动恢复

---

## 九、未来扩展
- 支持 FDE (Full-Disk Encryption)
- 支持从 super.img 提取 vendor
- 图形化界面
