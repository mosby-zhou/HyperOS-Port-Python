# Data 加密禁用工具

一个独立的命令行工具，用于禁用 Android FBE (File-Based Encryption) 加密，让新格式化后的 data 分区不再加密。

## 使用场景

- 在 TWRP 中访问加密数据
- 进行数据取证或恢复
- 特殊场景测试
- 设备维修时访问加密数据

## 功能
- 查找 vendor 分区中的 fstab 文件
- 删除 `fileencryption=` 相关选项
- 重新打包 vendor.img
- 输出刷入指南和 注意事项

## 使用方法

### 基本用法
```bash
python tools/disable_encryption/disable_encryption.py --vendor-dir <vendor目录>
```

### 常用参数
```
--vendor-dir PATH       vendor 目录路径 (必需)
--output PATH           输出 vendor.img 路径 (可选，默认覆盖原文件)
--cluster-size SIZE     EROFS 簇大小 (可选，默认 16384)
--dry-run              只显示将要修改的内容，不实际执行
-v, --verbose           显示详细输出
```

### 示例
```bash
# 禁用加密
python tools/disable_encryption/disable_encryption.py \
    --vendor-dir build/target/vendor

# 只显示修改内容 (dry-run)
python tools/disable_encryption/disable_encryption.py \
    --vendor-dir build/target/vendor \
    --dry-run

```

### 宯整流程
```bash
# 1. 禁用加密
python tools/disable_encryption/disable_encryption.py \
    --vendor-dir build/target/vendor \
    --output build/target/vendor_disabled.img

```

输出:
```
========================================
Data 加密禁用完成
========================================

修改的 fstab: build/target/vendor/etc/fstab.qcom
删除: fileencryption=aes-256-xts:aes-256-cbc
备份: build/target/vendor/etc/fstab.qcom.bak

生成的 vendor.img: build/target/vendor_disabled.img

========================================
接下来的步骤
========================================
1. 进入 fastbootd 模式
   adb reboot bootloader
   选择 "Enter fastbootd" 或:
   fastboot reboot fastboot

2. 刷入修改后的 vendor 镜像
   fastboot update-super vendor vendor.img
   (注意: 使用 update-super 而非 flash)

3. 关闭 vbmeta 校验
   fastboot --disable-verity
   fastboot flash vbmeta vbmeta.img

   或使用修改后的 vbmeta:
   fastboot flash vbmeta build/target/vbmeta.img
   fastboot flash vbmeta_system build/target/vbmeta_system.img

4. 擦除 userdata 分区
   fastboot erase userdata
   fastboot erase metadata

5. 重启设备
   fastboot reboot
```

## 验证结果
启动后验证加密状态:
```bash
adb shell
# 方法 1
getprop ro.crypto.state
# unencrypted = 未加密
# encrypted = 已加密

```
### 故障排除

| 问题 | 解决方案 |
|------|------|
| vendor 目录不存在 | 检查路径是否正确 |
| 没有 fstab 文件 | 可能该设备不支持加密，打包时需要手动处理 |
| 打包失败 | 检查 vendor 目录是否有 `fs_config` 和 `file_contexts` 文件 |
| 无法挂载 | 确保已安装 `mkfs.erofs` 或 `extract.erofs` 工具 |
| 刷入后无法启动 | 检查 vbmeta 是否已正确禁用 |

## 安全警告
此操作会降低设备安全性:
- 设备丢失后数据可被直接读取
- 部分应用可能拒绝工作
- 重启后 data 分区不再加密
- 仅在可信设备上使用

