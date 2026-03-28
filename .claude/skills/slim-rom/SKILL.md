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
│  ├── 转换 sparse 格式                                           │
│  ├── 解包 super.img                                             │
│  └── 解包各分区文件系统                                          │
│                    ⚠️ 关键：去掉 su 权限                          │
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

### ⚠️ Step 1.5: 关键步骤 - 去掉 su 权限

> **必须执行此步骤！否则后续 Agent 无法操作文件。**

```bash
sudo chown -R $USER:$USER build/{project}/target/
```

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

**用户**: "我要精简 ROM，删除讯飞输入法，项目名是 12su，ROM 路径是 roms/12su/thor_images_OS3.0.2.0.VLACNXM_15.0"

**Agent**:
1. 提供 Phase 1 的解包命令（用户手动执行，需包含 `--project 12su`）
2. 等待用户确认"解包完成"
3. 自动执行 Phase 2-4
4. 输出精简后的线刷包
