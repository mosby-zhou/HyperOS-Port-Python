# 线刷包精简操作步骤文档

> **重要**: 本操作需要 sudo 权限，请在终端中执行命令。

## 项目信息

| 项目 | 值 |
|------|------|
| 设备 | 小米 12S Ultra (thor) |
| ROM 版本 | OS3.0.2.0.VLACNXM (HyperOS 3.0) |
| Android 版本 | 15.0 |
| 操作类型 | 精简内置应用 |
| 删除目标 | 讯飞输入法 (iFlytekIME) |

---

## 执行记录

### Step 1: 解包 ROM [x] 已完成

**执行时间**: 2026-03-17 16:21 - 16:49

**实际执行的命令**:
```bash
# 1. 初始化工作目录
sudo python3 main.py --stock roms/12su/thor_images_OS3.0.2.0.VLACNXM_15.0 --pack-type super --clean --phases system

# 2. 转换 sparse 格式为 raw 格式
sudo bin/linux/x86_64/simg2img build/target/repack_images/super.img build/target/repack_images/super_raw.img

# 3. 解包 super.img
sudo python3 src/utils/lpunpack.py build/target/repack_images/super_raw.img build/target/

# 4. 解包各分区文件系统
sudo bin/linux/x86_64/extract.erofs -x -i build/target/product_a.img -o build/target/product
sudo bin/linux/x86_64/extract.erofs -x -i build/target/system_a.img -o build/target/system
sudo bin/linux/x86_64/extract.erofs -x -i build/target/vendor_a.img -o build/target/vendor
sudo bin/linux/x86_64/extract.erofs -x -i build/target/system_ext_a.img -o build/target/system_ext
sudo bin/linux/x86_64/extract.erofs -x -i build/target/odm_a.img -o build/target/odm
sudo bin/linux/x86_64/extract.erofs -x -i build/target/vendor_dlkm_a.img -o build/target/vendor_dlkm
sudo bin/linux/x86_64/extract.erofs -x -i build/target/mi_ext_a.img -o build/target/mi_ext

# 5. 修改权限（避免后续 sudo 需求）
sudo chown -R $USER:$USER build/target/
```

**输出**:
- `build/target/product/` - product 分区目录
- `build/target/system/` - system 分区目录
- `build/target/vendor/` - vendor 分区目录
- `build/target/system_ext/` - system_ext 分区目录
- `build/target/odm/` - odm 分区目录
- `build/target/vendor_dlkm/` - vendor_dlkm 分区目录
- `build/target/mi_ext/` - mi_ext 分区目录

---

### Step 2: 删除讯飞输入法 [x] 已完成

**执行时间**: 2026-03-17 17:02

**目标路径**: `build/target/product/product_a/data-app/iFlytekIME/`

**执行命令**:
```bash
rm -rf build/target/product/product_a/data-app/iFlytekIME
```

**验证**:
```bash
ls build/target/product/product_a/data-app/iFlytekIME/
# 输出: No such file or directory
```

---

### Step 3: 更新配置文件 [x] 已完成

**执行时间**: 2026-03-17 17:03

**配置文件路径**:
- `build/target/product/config/product_a_fs_config`
- `build/target/product/config/product_a_file_contexts`

**删除的条目**:
```
# fs_config (2 行)
product_a/data-app/iFlytekIME 0 0 0755
product_a/data-app/iFlytekIME/iFlytekIME.apk 0 0 0644

# file_contexts (2 行)
/product_a/data-app/iFlytekIME u:object_r:system_file:s0
/product_a/data-app/iFlytekIME/iFlytekIME\.apk u:object_r:system_file:s0
```

**执行命令**:
```bash
sed -i '/iFlytekIME/d' build/target/product/config/product_a_fs_config
sed -i '/iFlytekIME/d' build/target/product/config/product_a_file_contexts
```

**验证**:
```bash
grep -c "iFlytekIME" build/target/product/config/product_a_fs_config
# 输出: 0
grep -c "iFlytekIME" build/target/product/config/product_a_file_contexts
# 输出: 0
```

---

### Step 4: 重新打包 [x] 已完成

**执行时间**: 2026-03-17 17:05 - 17:09

**执行命令**:
```bash
# 1. 打包 product 分区
bin/linux/x86_64/mkfs.erofs \
  -zlz4hc,9 \
  -T 1230768000 \
  --mount-point /product_a \
  --fs-config-file build/target/product/config/product_a_fs_config \
  --file-contexts build/target/product/config/product_a_file_contexts \
  build/target/product_a_new.img \
  build/target/product/product_a

# 2. 替换原镜像
mv build/target/product_a_new.img build/target/product_a.img

# 3. 生成 super.img
otatools/bin/lpmake \
  --metadata-size 65536 \
  --super-name super \
  --block-size 4096 \
  --device super:9126805504 \
  --metadata-slots 2 \
  --group qti_dynamic_partitions:9126805504 \
  --partition odm_a:readonly:18206720:qti_dynamic_partitions \
  --image odm_a=build/target/odm_a.img \
  --partition odm_b:readonly:0:qti_dynamic_partitions \
  --partition product_a:readonly:4609880064:qti_dynamic_partitions \
  --image product_a=build/target/product_a.img \
  --partition product_b:readonly:0:qti_dynamic_partitions \
  --partition system_a:readonly:760127488:qti_dynamic_partitions \
  --image system_a=build/target/system_a.img \
  --partition system_b:readonly:0:qti_dynamic_partitions \
  --partition system_ext_a:readonly:771305472:qti_dynamic_partitions \
  --image system_ext_a=build/target/system_ext_a.img \
  --partition system_ext_b:readonly:0:qti_dynamic_partitions \
  --partition vendor_a:readonly:1925410816:qti_dynamic_partitions \
  --image vendor_a=build/target/vendor_a.img \
  --partition vendor_b:readonly:0:qti_dynamic_partitions \
  --partition vendor_dlkm_a:readonly:29933568:qti_dynamic_partitions \
  --image vendor_dlkm_a=build/target/vendor_dlkm_a.img \
  --partition vendor_dlkm_b:readonly:0:qti_dynamic_partitions \
  --partition mi_ext_a:readonly:147456:qti_dynamic_partitions \
  --image mi_ext_a=build/target/mi_ext_a.img \
  --partition mi_ext_b:readonly:0:qti_dynamic_partitions \
  --output build/target/super_new.img

# 4. 转换为 sparse 格式
otatools/bin/img2simg build/target/super_new.img build/target/super.img
```

---

## 输出结果

**输出目录**: `out/thor-slim-20260317/`

**输出文件大小**:
```
总大小: 9.2G
super.img: 7.6G (原: 7.65G, 减少 ~50MB)
文件数量: 68 个
```

**主要文件**:
| 文件 | 大小 |
|------|------|
| super.img | 7.6G |
| boot.img | 192M |
| vendor_boot.img | 96M |
| dtbo.img | 23M |
| vbmeta.img | 8.0K |
| vbmeta_system.img | 4.0K |
| recovery.img | 100M |
| cust.img | 862M |

---

## 刷机方法

### 方法 1: Fastboot 线刷

```bash
# 进入 Fastboot 模式
adb reboot bootloader

# 刷入
fastboot flash super out/thor-slim-20260317/super.img
fastboot flash boot out/thor-slim-20260317/boot.img
fastboot flash vendor_boot out/thor-slim-20260317/vendor_boot.img
fastboot flash dtbo out/thor-slim-20260317/dtbo.img
fastboot flash vbmeta out/thor-slim-20260317/vbmeta.img
fastboot flash vbmeta_system out/thor-slim-20260317/vbmeta_system.img

# 重启
fastboot reboot
```

### 方法 2: 使用 MiFlash

1. 将 `out/thor-slim-20260317/` 目录作为刷机包目录
2. 打开 MiFlash
3. 选择该目录
4. 点击"加载设备"
5. 点击"刷机"

---

## 完成检查清单

- [x] Step 1: ROM 解包完成
- [x] Step 2: 应用删除完成
- [x] Step 3: 配置文件更新完成
- [x] Step 4: 重新打包完成
- [x] 输出文件验证通过

---

## 技术说明

### 分区结构

本 ROM 为 A/B 分区设备，包含以下逻辑分区：
- `system_a` / `system_b`
- `vendor_a` / `vendor_b`
- `product_a` / `product_b`
- `system_ext_a` / `system_ext_b`
- `odm_a` / `odm_b`
- `vendor_dlkm_a` / `vendor_dlkm_b`
- `mi_ext_a` / `mi_ext_b`

### 文件系统

所有分区使用 **EROFS** (Enhanced Read-Only File System) 格式：
- 压缩算法: LZ4HC, 级别 9
- 只读文件系统，启动更快

### 注意事项

1. **AVB 验证**: 如遇启动失败，可能需要禁用 AVB 验证
2. **dm-verity**: 删除系统应用后可能触发 dm-verity 校验失败
3. **备份**: 刷机前请务必备份重要数据
