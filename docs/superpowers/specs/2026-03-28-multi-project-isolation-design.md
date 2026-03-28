---
title: 多项目隔离设计
date: 2026-03-28
status: draft
---

# 多项目隔离设计

## 背景

当前项目存在以下问题：一个 ROM 会直接解压到 `build/` 目录下，当需要同时处理多个 ROM 时会导致混乱。

## 目标

在 `build/` 目录下实现多 ROM 项目隔离，支持并行操作不同的 ROM 项目。

## 设计方案

### 目录结构映射

```
roms/                           # ROM 源文件目录
├── 12su/                       # 项目目录
│   ├── thor_images_.../        # 已解压的 ROM
│   └── xxx.tgz                 # ROM 压缩包
└── 17u/
    ├── nezha_images_.../
    └── xxx.tgz

build/                          # 工作目录
├── 12su/                       # 对应 roms/12su/ 的工作目录
│   ├── stockrom/
│   │   ├── images/
│   │   └── extracted/
│   ├── portrom/
│   │   ├── images/
│   │   └── extracted/
│   └── target/
│       ├── config/
│       ├── repack_images/
│       ├── system/
│       ├── vendor/
│       └── ...
└── 17u/                        # 对应 roms/17u/ 的工作目录
    └── ...
```

**对应关系**：`roms/{project}/` <-> `build/{project}/`（仅名字对应，内容完全独立）

### 命令行参数

**新增参数**：
```
--project PROJECT_NAME    项目名称（必填），对应 roms/{PROJECT_NAME}/ 目录
```

**行为**：
- 必须指定 — 未指定时直接报错退出
- 项目名用于创建独立的工作目录 `build/{PROJECT_NAME}/`

**错误提示示例**：
```
Error: --project is required.
Usage: --project <name>  (corresponds to roms/<name>/ directory)

Available projects in roms/:
  - 12su
  - 17u
```

### 使用示例

```bash
# 处理 12su 项目
python main.py --project 12su --stock roms/12su/xxx.tgz --port roms/12su/yyy.zip

# 处理 17u 项目
python main.py --project 17u --stock roms/17u/xxx.tgz
```

## 变更范围

### 代码变更

| 文件 | 变更内容 |
|------|----------|
| `main.py` | 新增 `--project` 参数（必填），修改工作目录逻辑 |

**main.py 改动点**：

```python
# 1. 新增参数
parser.add_argument(
    "--project",
    required=True,
    help="Project name, corresponds to roms/<project>/ directory"
)

# 2. 修改工作目录逻辑
work_dir = Path(args.work_dir) / args.project  # build/{project}/

# 3. 启动时验证并提示
logger.info(f"Project:   {args.project}")
logger.info(f"ROM Source: roms/{args.project}/")
logger.info(f"Work Dir:   build/{args.project}/")
```

**其他文件**：`context.py`、`packer.py` 等无需改动（已使用相对路径，由 `main.py` 传入）

### 文档变更

| 文件 | 更新内容 |
|------|----------|
| `main.py --help` | 参数帮助信息 |
| `README.md` | 使用说明中添加 `--project` 参数说明 |
| `README_CN.md` | 使用说明中添加 `--project` 参数说明 |
| `USER_GUIDE.md` | 添加项目隔离章节，说明 `roms/` 与 `build/` 的对应关系 |
| `SLIM_ROM_GUIDE.md` | 更新示例命令，添加 `--project` 参数 |
| `.claude/skills/slim-rom/SKILL.md` | 所有 `build/target/` 路径改为 `build/{project}/target/`，示例命令添加 `--project` 参数 |

## 向后兼容性

**不兼容变更**：未指定 `--project` 时将报错退出。

这是有意设计，避免多项目混乱。现有用户的脚本/工作流需要添加 `--project` 参数。

## 实现步骤

1. 修改 `main.py`：添加 `--project` 参数，修改工作目录逻辑
2. 更新 `README.md` 和 `README_CN.md`
3. 更新 `USER_GUIDE.md`
4. 更新 `SLIM_ROM_GUIDE.md`
5. 更新 `.claude/skills/slim-rom/SKILL.md`
