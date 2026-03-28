---
name: slim-rom
description: |
  精简 ROM 内置应用的 skill。用于解包线刷包、删除指定应用、更新配置、重新打包。

  触发场景：
  - 用户说"精简 ROM"、"删除内置应用"、"删除预装软件"、"瘦身 ROM"
  - 用户说"删除 XX 输入法"、"删除 XX 应用"
  - 用户有线刷包需要去除预装软件
  - 用户提到 data-app 目录下的应用删除

  当用户请求精简 ROM 或删除内置应用时，必须使用此 skill。
---

# ROM 精简 Skill

本 skill 用于自动化精简 ROM 内置应用的流程，包括解包、删除应用、更新配置、重新打包。

---

## 流程概览

```
┌─────────────────────────────────────────────────────────────────┐
│  Phase 1: 解包 ROM (用户接管 - 需要 sudo)                        │
│  ├── Step 1.1: 初始化工作目录                                    │
│  ├── Step 1.2: 转换 sparse 格式                                  │
│  ├── Step 1.3: 解包 super.img                                    │
│  ├── Step 1.4: 解包各分区文件系统 (erofs)                        │
│  ├── Step 1.5: 去掉 su 权限 ⚠️ 关键                              │
│  ├── Step 1.6: 生成 APK 列表文档 (可选)                          │
│  ├── Step 1.7: 转换 userdata.img (可选)                          │
│  └── Step 1.8: Docker 挂载 f2fs (可选，需要 Docker)              │
├─────────────────────────────────────────────────────────────────┤
│  Phase 2-4: Agent 自动完成                                       │
│  ├── Phase 2: 删除指定应用                                       │
│  ├── Phase 3: 更新配置文件                                       │
│  └── Phase 4: 重新打包生成线刷包                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔴 用户接管部分 (Phase 1)

> **重要**: 以下步骤需要用户在终端手动执行，因为需要 sudo 权限。

### Step 1.1: 初始化工作目录

```bash
cd /home/zhouc/code/2026/HyperOS-Port-Python

sudo python3 main.py --project <PROJECT_NAME> --stock <ROM目录路径> --pack-type super --clean --phases system
```

> **注意：** `<PROJECT_NAME>` 对应 `roms/<PROJECT_NAME>/` 目录名。

### Step 1.2: 转换 sparse 格式为 raw 格式

```bash
sudo bin/linux/x86_64/simg2img build/{project}/target/repack_images/super.img build/{project}/target/repack_images/super_raw.img
```

### Step 1.3: 解包 super.img

```bash
sudo python3 src/utils/lpunpack.py build/{project}/target/repack_images/super_raw.img build/{project}/target/
```

### Step 1.4: 解包各分区文件系统

```bash
# 解包所有分区
sudo bin/linux/x86_64/extract.erofs -x -i build/{project}/target/product_a.img -o build/{project}/target/product
sudo bin/linux/x86_64/extract.erofs -x -i build/{project}/target/system_a.img -o build/{project}/target/system
sudo bin/linux/x86_64/extract.erofs -x -i build/{project}/target/vendor_a.img -o build/{project}/target/vendor
sudo bin/linux/x86_64/extract.erofs -x -i build/{project}/target/system_ext_a.img -o build/{project}/target/system_ext
sudo bin/linux/x86_64/extract.erofs -x -i build/{project}/target/odm_a.img -o build/{project}/target/odm
sudo bin/linux/x86_64/extract.erofs -x -i build/{project}/target/vendor_dlkm_a.img -o build/{project}/target/vendor_dlkm
sudo bin/linux/x86_64/extract.erofs -x -i build/{project}/target/mi_ext_a.img -o build/{project}/target/mi_ext
```

### Step 1.5: 关键步骤 - 去掉 su 权限

> **必须执行此步骤！否则后续 Agent 无法操作文件。**

```bash
sudo chown -R $USER:$USER build/{project}/target/
```

### Step 1.6: 生成 APK 列表文档（可选）

> Agent 可以自动生成 APK 列表文档，帮助用户了解 ROM 中包含的所有应用。

完成 Step 1.5 后，告诉 Agent "解包完成，生成 APK 列表"，Agent 将：
1. 扫描所有分区的 APK 文件
2. 提取应用名称（基于已知映射）
3. 生成 Markdown 文档到 `<ROM目录>/APK_LIST.md`

文档包含：
- 各分区的 APK 列表（data-app、priv-app、app 等）
- 推荐删除的应用
- 不应删除的系统核心应用

---

## 🟡 userdata.img 解包（可选）

> userdata.img 通常包含预安装的第三方应用和用户数据。
> 由于该分区使用 f2fs 文件系统，在 WSL2 下无法直接挂载（内核不支持 f2fs 模块）。

### 前提条件

- 需要有 Docker 环境
- userdata.img 通常使用 f2fs 文件系统

### Step 1.7: 转换 userdata.img 为 raw 格式

```bash
# 转换 sparse 格式为 raw 格式
# 注意：raw 文件会展开成分区完整大小（如 45GB），但实际数据只有原始大小
sudo bin/linux/x86_64/simg2img \
  roms/{project}/*/images/userdata.img \
  build/{project}/target/userdata_raw.img
```

### Step 1.8: 使用 Docker 挂载 f2fs

```bash
# 创建挂载目录
mkdir -p build/{project}/target/userdata

# 使用 Docker 容器挂载 f2fs 并复制文件
docker run --rm -it \
  -v $(pwd)/build/{project}/target/userdata_raw.img:/data/userdata.img \
  -v $(pwd)/build/{project}/target/userdata:/data/out \
  alpine sh -c "
    apk add f2fs-tools &&
    mkdir -p /mnt &&
    mount -t f2fs /data/userdata.img /mnt &&
    cp -a /mnt/. /data/out/ &&
    umount /mnt
  "

# 去掉 su 权限
sudo chown -R $USER:$USER build/{project}/target/userdata/
```

### userdata 分区说明

| 目录 | 说明 |
|------|------|
| `/data/app/` | 用户安装的应用 |
| `/data/data/` | 应用数据目录 |
| `/data/user/0/` | 用户 0 的数据 |
| `/data/system/` | 系统配置 |

### 注意事项

1. **Sparse vs Raw 大小**：
   - Sparse 格式：只存储实际数据（如 1.8GB）
   - Raw 格式：展开成分区大小（如 45GB），空洞填充零
   - 这是正常现象，不影响数据完整性

2. **WSL2 限制**：
   - WSL2 内核不支持 f2fs 模块
   - 必须使用 Docker 容器或其他支持 f2fs 的环境

3. **精简建议**：
   - 大多数预装应用已在 product/data-app 目录
   - userdata 中的应用通常是首次启动时安装的第三方应用
   - 可通过删除 product/data-app 中的应用达到精简目的

---

## 🟢 Agent 自动完成部分 (Phase 2-4)

完成 Phase 1 后，告诉 Agent "解包完成"，Agent 将自动执行以下步骤：

### Phase 2: 定位并删除应用

Agent 将：
1. 在 `build/{project}/target/product/product_a/data-app/` 或 `build/{project}/target/product/product_a/app/` 或 `build/{project}/target/product/product_a/priv-app/` 中定位目标应用
2. 删除指定应用目录
3. 验证删除成功

### Phase 3: 更新配置文件

Agent 将更新以下配置文件：
- `build/{project}/target/product/config/product_a_fs_config` - 删除相关条目
- `build/{project}/target/product/config/product_a_file_contexts` - 删除 SELinux 上下文条目

如果应用在其他分区，Agent 会相应更新该分区的配置文件。

### Phase 4: 重新打包

Agent 将执行：
1. 使用 `mkfs.erofs` 打包修改后的分区
2. 使用 `lpmake` 生成新的 `super.img`
3. 使用 `img2simg` 转换为 sparse 格式
4. 复制所有必要文件到输出目录

---

## 输出

最终输出位于 `out/thor-slim-<日期>/` 目录，包含：
- `super.img` - 精简后的系统分区
- `boot.img` - 启动镜像
- `vendor_boot.img` - vendor 启动镜像
- `dtbo.img` - 设备树覆盖
- `vbmeta.img` / `vbmeta_system.img` - AVB 元数据
- 其他固件文件

---

## 刷机方法

```bash
# 进入 fastboot
adb reboot bootloader

# 刷入 super（A/B 设备不需要指定 _a/_b）
fastboot flash super out/thor-slim-<日期>/super.img

# 刷入其他分区
fastboot flash boot out/thor-slim-<日期>/boot.img
fastboot flash vendor_boot out/thor-slim-<日期>/vendor_boot.img
fastboot flash dtbo out/thor-slim-<日期>/dtbo.img
fastboot flash vbmeta out/thor-slim-<日期>/vbmeta.img

# 重启
fastboot reboot
```

---

## 常见应用位置

| 应用类型 | 位置 |
|----------|------|
| 可卸载预装应用 | `product/data-app/` |
| 系统应用 | `product/app/` |
| 特权应用 | `product/priv-app/` |
| 系统核心应用 | `system/app/`, `system/priv-app/` |

---

## 注意事项

1. **不要删除系统核心应用** - 如 SystemUI、Settings 等
2. **AVB 验证** - 如果刷入后无法启动，可能需要禁用 AVB
3. **备份** - 刷机前务必备份数据

---

## 示例用法

### 示例 1: 基本精简流程

**用户**: "我要精简 ROM，删除讯飞输入法，项目名是 12su，ROM 路径是 roms/12su/thor_images_OS3.0.2.0.VLACNXM_15.0"

**Agent**:
1. 提供 Phase 1 的解包命令（用户手动执行，需包含 `--project 12su`）
2. 等待用户确认"解包完成"
3. 自动执行 Phase 2-4
4. 输出精简后的线刷包

### 示例 2: 查看所有应用后再精简

**用户**: "我有一个新的 ROM 包，先帮我列出所有应用"

**Agent**:
1. 提供解包命令（Phase 1 Step 1.1-1.5）
2. 用户执行后回复"解包完成，生成 APK 列表"
3. Agent 扫描所有分区生成 `<ROM目录>/APK_LIST.md`
4. 用户查看文档后告诉 Agent 要删除哪些应用
5. Agent 执行精简操作

### 示例 3: 解包 userdata 查看预装第三方应用

**用户**: "我想看看 userdata 里有什么预装应用"

**Agent**:
1. 提供解包命令（Phase 1 Step 1.7-1.8）
2. 提醒用户需要 Docker 环境
3. 用户执行后回复"userdata 解包完成"
4. Agent 扫描 `build/{project}/target/userdata/` 目录中的应用

---

## 快速参考

### 常用命令汇总

```bash
# 设置项目名
PROJECT=17u

# Phase 1 完整流程
cd /home/zhouc/code/2026/HyperOS-Port-Python
sudo python3 main.py --project $PROJECT --stock roms/$PROJECT/*/ --pack-type super --clean --phases system
sudo bin/linux/x86_64/simg2img build/$PROJECT/target/repack_images/super.img build/$PROJECT/target/super_raw.img
sudo python3 src/utils/lpunpack.py build/$PROJECT/target/super_raw.img build/$PROJECT/target/
sudo bin/linux/x86_64/extract.erofs -x -i build/$PROJECT/target/product_a.img -o build/$PROJECT/target/product
sudo bin/linux/x86_64/extract.erofs -x -i build/$PROJECT/target/system_a.img -o build/$PROJECT/target/system
sudo bin/linux/x86_64/extract.erofs -x -i build/$PROJECT/target/vendor_a.img -o build/$PROJECT/target/vendor
sudo bin/linux/x86_64/extract.erofs -x -i build/$PROJECT/target/system_ext_a.img -o build/$PROJECT/target/system_ext
sudo chown -R $USER:$USER build/$PROJECT/target/

# userdata 解包（需要 Docker）
sudo bin/linux/x86_64/simg2img roms/$PROJECT/*/images/userdata.img build/$PROJECT/target/userdata_raw.img
mkdir -p build/$PROJECT/target/userdata
docker run --rm -it \
  -v $(pwd)/build/$PROJECT/target/userdata_raw.img:/data/userdata.img \
  -v $(pwd)/build/$PROJECT/target/userdata:/data/out \
  alpine sh -c "apk add f2fs-tools && mkdir -p /mnt && mount -t f2fs /data/userdata.img /mnt && cp -a /mnt/. /data/out/ && umount /mnt"
sudo chown -R $USER:$USER build/$PROJECT/target/userdata/
```
