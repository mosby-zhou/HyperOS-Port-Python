# 多项目隔离实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 添加 `--project` 必填参数，实现 `build/` 目录下的多 ROM 项目隔离。

**Architecture:** 通过命令行参数指定项目名，工作目录由 `build/` 改为 `build/{project}/`，与 `roms/{project}/` 形成命名对应关系。

**Tech Stack:** Python 3.8+, argparse, pathlib

---

## 文件变更概览

| 文件 | 操作 | 说明 |
|------|------|------|
| `main.py` | 修改 | 添加 `--project` 参数，修改工作目录逻辑 |
| `README.md` | 修改 | 更新参数说明和示例 |
| `README_CN.md` | 修改 | 更新参数说明和示例 |
| `USER_GUIDE.md` | 修改 | 添加项目隔离章节，更新参数表和示例 |
| `SLIM_ROM_GUIDE.md` | 修改 | 更新示例命令，添加 `--project` 参数 |
| `.claude/skills/slim-rom/SKILL.md` | 修改 | 更新路径和示例命令 |

---

### Task 1: 修改 main.py 添加 --project 参数

**Files:**
- Modify: `main.py:36-51` (parse_args 函数)
- Modify: `main.py:151-159` (work_dir 逻辑)

- [ ] **Step 1: 添加 --project 参数**

在 `parse_args()` 函数中添加新参数，位于 `--stock` 参数之后：

```python
parser.add_argument(
    "--project",
    required=True,
    help="Project name, corresponds to roms/<project>/ directory"
)
```

修改位置：`main.py:38` 之后（`--stock` 参数定义之后）

- [ ] **Step 2: 添加项目名验证逻辑**

在 `main()` 函数中，`work_dir` 定义之前添加验证逻辑：

```python
# Validate project directory exists in roms/
roms_dir = Path("roms").resolve()
project_dir = roms_dir / args.project
if not project_dir.exists():
    available_projects = [d.name for d in roms_dir.iterdir() if d.is_dir()]
    logger.error(f"Error: --project is required.")
    logger.error(f"Project directory not found: roms/{args.project}/")
    logger.error(f"Available projects in roms/:")
    for p in available_projects:
        logger.error(f"  - {p}")
    sys.exit(1)
```

- [ ] **Step 3: 修改工作目录逻辑**

修改 `work_dir` 的计算逻辑，将项目名作为子目录：

修改前：
```python
work_dir = Path(args.work_dir).resolve()
```

修改后：
```python
work_dir = Path(args.work_dir).resolve() / args.project
```

位置：`main.py:151`

- [ ] **Step 4: 更新启动日志输出**

在日志输出部分添加项目信息：

```python
logger.info(f"Project:   {args.project}")
logger.info(f"ROM Source: roms/{args.project}/")
logger.info(f"Work Dir:   build/{args.project}/")
```

位置：`main.py:116-125` 的日志输出区域

- [ ] **Step 5: 验证变更**

运行帮助命令确认参数已添加：

```bash
python3 main.py --help
```

Expected output 应包含：
```
--project PROJECT   Project name, corresponds to roms/<project>/ directory
```

- [ ] **Step 6: Commit**

```bash
git add main.py
git commit -m "feat(cli): add required --project parameter for multi-project isolation

- Add --project argument (required)
- Validate project directory exists in roms/
- Work directory changed from build/ to build/{project}/
- Add startup logging for project info

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: 更新 README.md

**Files:**
- Modify: `README.md:85-101` (Basic Usage)
- Modify: `README.md:109-119` (Arguments Reference)

- [ ] **Step 1: 更新 Basic Usage 示例**

修改 `README.md` 中的 "2. Basic Usage" 章节，添加 `--project` 参数：

```markdown
### 2. Basic Usage
Prepare your Stock ROM and Port ROM ZIP files (or just Stock ROM for Official Modification), then run:

**OTA/Recovery Mode (Default):**
```bash
sudo python3 main.py --project <project_name> --stock <path_to_stock_zip> --port <path_to_port_zip>
```

**Official Modification Mode (Modify Stock ROM only):**
```bash
sudo python3 main.py --project <project_name> --stock <path_to_stock_zip>
```

**Hybrid/Fastboot Mode (Super Image):**
```bash
sudo python3 main.py --project <project_name> --stock <path_to_stock_zip> --port <path_to_port_zip> --pack-type super
```

> **Note:** `--project` is required. The project name corresponds to `roms/<project_name>/` directory.
```

- [ ] **Step 2: 更新 Arguments Reference 表格**

在 Arguments Reference 表格中添加 `--project` 行，放在表格最前面：

```markdown
| Argument | Description | Default |
| :--- | :--- | :--- |
| `--project` | **(Required)** Project name, corresponds to `roms/<project>/` | N/A |
| `--stock` | **(Required)** Path to the Stock ROM (Base) | N/A |
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(readme): add --project parameter documentation

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 3: 更新 README_CN.md

**Files:**
- Modify: `README_CN.md:84-100` (基本用法)
- Modify: `README_CN.md:104-119` (参数说明)

- [ ] **Step 1: 更新基本用法示例**

修改 `README_CN.md` 中的 "2. 基本用法" 章节：

```markdown
### 2. 基本用法
准备好底包 (Stock ROM) 和移植包 (Port ROM) 的 ZIP 文件（官改模式仅需底包），然后运行：

**OTA/Recovery 模式 (默认):**
```bash
sudo python3 main.py --project <项目名> --stock <底包路径> --port <移植包路径>
```

**官改模式 (仅修改底包):**
```bash
sudo python3 main.py --project <项目名> --stock <底包路径>
```

**Hybrid/Fastboot 模式 (Super Image):**
```bash
sudo python3 main.py --project <项目名> --stock <底包路径> --port <移植包路径> --pack-type super
```

> **注意：** `--project` 为必填参数。项目名对应 `roms/<项目名>/` 目录。
```

- [ ] **Step 2: 更新参数说明表格**

在参数说明表格中添加 `--project` 行：

```markdown
| 参数 | 说明 | 默认值 |
| :--- | :--- | :--- |
| `--project` | **(必填)** 项目名称，对应 `roms/<project>/` 目录 | 无 |
| `--stock` | **(必需)** 底包 (Stock ROM) 路径 | 无 |
```

- [ ] **Step 3: Commit**

```bash
git add README_CN.md
git commit -m "docs(readme-cn): add --project parameter documentation (Chinese)

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 4: 更新 USER_GUIDE.md

**Files:**
- Modify: `USER_GUIDE.md:65-113` (基本使用章节)
- Create: 新增项目隔离章节

- [ ] **Step 1: 在第2章开头添加项目隔离说明**

在 "## 2. 基本使用" 章节之前，添加新的章节：

```markdown
## 2. 项目隔离机制

本工具支持多 ROM 项目并行处理，通过 `--project` 参数实现项目隔离。

### 2.1 目录结构对应关系

```
roms/                           # ROM 源文件目录
├── 12su/                       # 项目目录
│   ├── xxx_images_.../         # 已解压的 ROM
│   └── xxx.tgz                 # ROM 压缩包
└── 17u/
    └── ...

build/                          # 工作目录
├── 12su/                       # 对应 roms/12su/ 的工作目录
│   ├── stockrom/
│   ├── portrom/
│   └── target/
└── 17u/                        # 对应 roms/17u/ 的工作目录
    └── ...
```

### 2.2 使用示例

```bash
# 处理 12su 项目
sudo python3 main.py --project 12su --stock roms/12su/xxx.tgz

# 处理 17u 项目
sudo python3 main.py --project 17u --stock roms/17u/xxx.tgz --port roms/17u/yyy.zip
```

> **重要：** `--project` 为必填参数。项目名必须对应 `roms/` 目录下的子目录名称。

---

## 3. 基本使用
```

注意：原有的 "## 2. 基本使用" 及后续章节编号需要 +1。

- [ ] **Step 2: 更新参数详解表格**

在参数详解表格中添加 `--project` 行，放在最前面：

```markdown
| 参数          | 必需 | 默认值  | 说明                                           |
| ------------- | ---- | ------- | ---------------------------------------------- |
| `--project`   | ✅   | -       | 项目名称，对应 `roms/<project>/` 目录          |
| `--stock`     | ✅   | -       | 底包 ROM 路径 (ZIP/目录)                       |
```

- [ ] **Step 3: 更新示例命令**

更新所有示例命令，添加 `--project` 参数：

标准移植模式示例：
```bash
# 将小米 14 ROM 移植到小米 13
sudo python3 main.py \
    --project fuxi \
    --stock fuxi_hyperos_2.0.zip \
    --port shennong_hyperos_3.0.zip
```

官改模式示例：
```bash
# 官改小米 13 ROM，启用 Wild Boost
sudo python3 main.py --project fuxi --stock fuxi_hyperos_2.0.zip
```

- [ ] **Step 4: Commit**

```bash
git add USER_GUIDE.md
git commit -m "docs(user-guide): add project isolation section and update examples

- Add section 2 for project isolation mechanism
- Update parameter table with --project
- Update all example commands with --project

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 5: 更新 SLIM_ROM_GUIDE.md

**Files:**
- Modify: `SLIM_ROM_GUIDE.md:37-56` (步骤1)
- Modify: `SLIM_ROM_GUIDE.md:156-167` (步骤4)

- [ ] **Step 1: 更新步骤1示例命令**

修改 "步骤 1: 解包 ROM" 中的示例命令：

```bash
cd /home/zhouc/code/2026/HyperOS-Port-Python

sudo python3 main.py \
    --project mayfly \
    --stock /path/to/mayfly_hyperos_xxx.tgz \
    --pack-type super \
    --clean \
    --phases system
```

同时更新参数说明：
```markdown
**参数说明**:
- `--project`: 项目名称 (必填)，对应 roms/<project>/ 目录
- `--stock`: 线刷包路径 (支持 .tgz / .zip / 目录)
- `--pack-type super`: 生成线刷格式的 super.img
- `--clean`: 清理旧的工作目录
- `--phases system`: 仅执行系统级处理，跳过 APK 修改
```

- [ ] **Step 2: 更新预期输出路径**

修改预期输出说明：

```markdown
**预期输出**:
```
build/mayfly/target/
├── system/          # 系统分区
├── product/         # 产品分区 (预装应用主要在此)
├── vendor/          # 厂商分区
├── system_ext/      # 系统扩展分区
├── mi_ext/          # MIUI 扩展分区
├── config/          # 配置文件
└── repack_images/   # 固件镜像 (boot, vbmeta 等)
```
```

- [ ] **Step 3: 更新步骤4示例命令**

修改 "步骤 4: 重新打包" 中的示例命令：

```bash
cd /home/zhouc/code/2026/HyperOS-Port-Python

sudo python3 main.py \
    --project mayfly \
    --stock /path/to/mayfly_hyperos_xxx.tgz \
    --pack-type super \
    --phases repack
```

- [ ] **Step 4: 更新快捷脚本**

修改 `slim_mayfly.sh` 脚本示例，添加项目名参数：

```bash
#!/bin/bash
set -e

PROJECT_DIR="/home/zhouc/code/2026/HyperOS-Port-Python"
PROJECT_NAME="$1"
ROM_PATH="$2"
APPS_TO_DELETE="$3"

if [ -z "$PROJECT_NAME" ] || [ -z "$ROM_PATH" ]; then
    echo "用法: ./slim_mayfly.sh <项目名> <线刷包路径> [应用列表文件]"
    echo "示例: ./slim_mayfly.sh mayfly /path/to/rom.tgz apps.txt"
    exit 1
fi

cd "$PROJECT_DIR"

echo "=== 步骤 1: 解包 ROM ==="
sudo python3 main.py --project "$PROJECT_NAME" --stock "$ROM_PATH" --pack-type super --clean --phases system

echo "=== 步骤 2: 删除应用 ==="
if [ -f "$APPS_TO_DELETE" ]; then
    while IFS= read -r app_path; do
        [ -z "$app_path" ] && continue
        [[ "$app_path" == \#* ]] && continue
        echo "删除: $app_path"
        sudo rm -rf "build/$PROJECT_NAME/target/$app_path"
    done < "$APPS_TO_DELETE"
fi

echo "=== 步骤 3: 重新打包 ==="
sudo python3 main.py --project "$PROJECT_NAME" --stock "$ROM_PATH" --pack-type super --phases repack

echo "=== 完成! ==="
echo "输出文件: out/mayfly-hybrid-*.zip"
ls -lh out/mayfly-hybrid-*.zip
```

- [ ] **Step 5: Commit**

```bash
git add SLIM_ROM_GUIDE.md
git commit -m "docs(slim-rom): update guide with --project parameter

- Add --project to all example commands
- Update work directory paths to build/{project}/target/
- Update slim script to accept project name argument

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 6: 更新 slim-rom SKILL.md

**Files:**
- Modify: `.claude/skills/slim-rom/SKILL.md:43-83` (Phase 1 步骤)
- Modify: `.claude/skills/slim-rom/SKILL.md:87-105` (Phase 2-4 说明)
- Modify: `.claude/skills/slim-rom/SKILL.md:169-177` (示例用法)

- [ ] **Step 1: 更新 Step 1.1 命令**

修改 Step 1.1 中的命令：

```markdown
### Step 1.1: 初始化工作目录

```bash
cd /home/zhouc/code/2026/HyperOS-Port-Python

sudo python3 main.py --project <PROJECT_NAME> --stock <ROM目录路径> --pack-type super --clean --phases system
```

> **注意：** `<PROJECT_NAME>` 对应 `roms/<PROJECT_NAME>/` 目录名。
```

- [ ] **Step 2: 更新 Step 1.2-1.4 路径**

将所有 `build/target/` 路径改为 `build/{project}/target/`：

```markdown
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
```

- [ ] **Step 3: 更新 Step 1.5 路径**

```markdown
### ⚠️ Step 1.5: 关键步骤 - 去掉 su 权限

> **必须执行此步骤！否则后续 Agent 无法操作文件。**

```bash
sudo chown -R $USER:$USER build/{project}/target/
```
```

- [ ] **Step 4: 更新 Phase 2 说明**

```markdown
### Phase 2: 定位并删除应用

Agent 将：
1. 在 `build/{project}/target/product/product_a/data-app/` 或 `build/{project}/target/product/product_a/app/` 或 `build/{project}/target/product/product_a/priv-app/` 中定位目标应用
2. 删除指定应用目录
3. 验证删除成功
```

- [ ] **Step 5: 更新 Phase 3 说明**

```markdown
### Phase 3: 更新配置文件

Agent 将更新以下配置文件：
- `build/{project}/target/product/config/product_a_fs_config` - 删除相关条目
- `build/{project}/target/product/config/product_a_file_contexts` - 删除 SELinux 上下文条目
```

- [ ] **Step 6: 更新示例用法**

```markdown
## 示例用法

**用户**: "我要精简 ROM，删除讯飞输入法，项目名是 12su，ROM 路径是 roms/12su/thor_images_OS3.0.2.0.VLACNXM_15.0"

**Agent**:
1. 提供 Phase 1 的解包命令（用户手动执行，需包含 `--project 12su`）
2. 等待用户确认"解包完成"
3. 自动执行 Phase 2-4
4. 输出精简后的线刷包
```

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/slim-rom/SKILL.md
git commit -m "docs(skill): update slim-rom skill with --project parameter

- Add --project to all example commands
- Update all paths from build/target/ to build/{project}/target/
- Update example usage with project name

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 7: 最终验证

- [ ] **Step 1: 验证命令行帮助**

```bash
python3 main.py --help
```

Expected: 应显示 `--project` 参数且标记为 required

- [ ] **Step 2: 验证错误提示**

```bash
python3 main.py --stock roms/12su/xxx.tgz
```

Expected: 应报错提示 `--project` 为必填参数

- [ ] **Step 3: 验证项目目录检查**

```bash
python3 main.py --project nonexistent --stock roms/12su/xxx.tgz
```

Expected: 应报错并列出 `roms/` 下可用的项目

- [ ] **Step 4: 验证文档一致性**

检查所有文档中的示例命令是否都包含 `--project` 参数。

---

## 完成检查清单

- [ ] main.py 添加 --project 参数并验证
- [ ] README.md 更新
- [ ] README_CN.md 更新
- [ ] USER_GUIDE.md 更新
- [ ] SLIM_ROM_GUIDE.md 更新
- [ ] slim-rom SKILL.md 更新
- [ ] 最终验证通过
