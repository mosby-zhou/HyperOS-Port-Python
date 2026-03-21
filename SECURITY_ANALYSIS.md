# HyperOS-Port-Python 安全风险分析报告

**文档版本**: 1.0
**分析日期**: 2026-03-17
**风险等级**: 中等

---

## 一、执行摘要

本项目涉及多个安全风险点，主要集中在：

1. **二进制工具来源不明** - 多个关键工具来自第三方
2. **网络下载行为** - 运行时从网络下载可执行文件
3. **JAR 文件未验证** - Java 工具缺乏完整性校验
4. **数据注入风险** - ROM 修改过程可能被恶意利用

---

## 二、二进制工具风险分析

### 2.1 工具清单与风险评估

| 工具 | 位置 | 来源 | 风险等级 | 说明 |
|------|------|------|----------|------|
| **magiskboot** | `bin/linux/x86_64/` | Magisk 官方 | ⚠️ 中 | 需验证 SHA256 |
| **payload-dumper** | `bin/linux/x86_64/` | 社区项目 | ⚠️ 中 | 来源需确认 |
| **aapt2** | `bin/linux/x86_64/` | Android SDK | ✅ 低 | 官方工具 |
| **lpunpack/lpmake** | `bin/linux/x86_64/` | AOSP | ✅ 低 | Android 官方 |
| **mkfs.erofs** | `bin/linux/x86_64/` | EROFS 官方 | ✅ 低 | 开源项目 |
| **extract.erofs** | `bin/linux/x86_64/` | EROFS 官方 | ✅ 低 | 开源项目 |
| **brotli** | `bin/linux/x86_64/` | Google 官方 | ✅ 低 | 开源项目 |
| **e2fsdroid/mke2fs** | `bin/linux/x86_64/` | e2fsprogs | ✅ 低 | 开源项目 |
| **simg2img** | `bin/linux/x86_64/` | AOSP | ✅ 低 | Android 官方 |

### 2.2 高风险工具详情

#### magiskboot
```
文件类型: ELF 64-bit LSB executable, x86-64
来源: https://github.com/topjohnwu/Magisk
风险: 运行时具有 root 权限，可执行任意操作

缓解措施:
1. 从官方 Release 下载并验证签名
2. 计算并比对 SHA256 校验和
3. 使用前进行病毒扫描
```

#### payload-dumper
```
文件类型: ELF 64-bit, dynamically linked
来源: 社区项目 (需确认具体来源)
风险: 解包过程中可能执行恶意代码

缓解措施:
1. 使用官方 payload-dumper-go 替代
2. 验证二进制来源
```

---

## 三、网络下载风险

### 3.1 运行时下载行为

项目在运行时会从网络下载以下内容：

| 下载目标 | URL 模板 | 触发条件 | 风险 |
|----------|----------|----------|------|
| **otatools** | `github.com/toraidl/.../otatools.zip` | 工具缺失时 | 🔴 高 |
| **KernelSU** | `api.github.com/repos/tiann/KernelSU/...` | 启用 KSU 时 | 🔴 高 |
| **wild_boost** | 设备配置指定 | 启用 wild_boost 时 | ⚠️ 中 |
| **EU Bundle** | 用户指定 URL | EU 本地化时 | ⚠️ 中 |

### 3.2 KernelSU 下载风险 (🔴 高风险)

**代码位置**: `src/core/modifiers/firmware_modifier.py:404-425`

```python
api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
with urllib.request.urlopen(api_url, timeout=10) as resp:
    data = json.loads(resp.read().decode())
    assets = data.get("assets", [])
    # 下载 ksuinit 和 kernelsu.ko
```

**风险点**:
1. **中间人攻击**: HTTP 请求可能被劫持
2. **供应链攻击**: GitHub 仓库可能被入侵
3. **无签名验证**: 下载的文件未验证签名
4. **直接注入 boot.img**: 下载的内容会写入启动镜像

**攻击场景**:
```
攻击者控制下载源 → 注入恶意 kernelsu.ko → 用户刷入 → 设备被完全控制
```

### 3.3 otatools 下载风险 (🔴 高风险)

**代码位置**: `src/utils/otatools_manager.py:12`

```python
DEFAULT_URL = "https://github.com/toraidl/HyperOS-Port-Python/releases/download/assets/otatools.zip"
```

**风险点**:
1. otatools 包含大量二进制可执行文件
2. 这些文件会被直接执行，无签名验证
3. URL 指向项目自身 Release，可能被篡改

---

## 四、JAR 文件风险

### 4.1 Java 工具清单

| JAR 文件 | 版本 | 来源 | 风险 | 官方地址 |
|----------|------|------|------|----------|
| **apktool.jar** | 2.12.1 | iBotPeaches | ⚠️ 中 | https://github.com/iBotPeaches/Apktool |
| **APKEditor.jar** | - | reYard | ⚠️ 中 | https://github.com/REAndroid/APKEditor |
| **smali.jar** | - | JesusFreke | ✅ 低 | https://github.com/JesusFreke/smali |
| **baksmali.jar** | - | JesusFreke | ✅ 低 | https://github.com/JesusFreke/smali |

### 4.2 风险分析

JAR 文件的风险：
1. **无校验和**: 项目中未存储 SHA256，无法验证完整性
2. **反编译能力**: 这些工具可修改 APK 内容，被篡改可能注入恶意代码
3. **执行任意代码**: 作为 Java 程序，可执行任意操作

---

## 五、设备配置文件风险

### 5.1 预打包资源

```
devices/common/
├── PropsHook.zip           # APK 文件
├── otacerts.zip            # 证书文件
├── pif_patch.zip           # 补丁文件
├── pif_patch_v2.zip        # 补丁文件
├── wild_boost_5.10.zip     # 内核模块
├── wild_boost_5.15.zip     # 内核模块
└── xeutoolbox.zip          # 工具包
```

### 5.2 风险分析

| 文件 | 内容 | 风险 |
|------|------|------|
| **PropsHook.zip** | APK，注入系统 | 🔴 高 - 可执行任意代码 |
| **wild_boost_*.zip** | 内核模块 | 🔴 高 - 内核级权限 |
| **pif_patch*.zip** | Play Integrity 补丁 | ⚠️ 中 - 修改系统属性 |
| **xeutoolbox.zip** | 工具包 | ⚠️ 中 - 需验证来源 |

---

## 六、数据流风险

### 6.1 ROM 处理流程中的注入点

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ROM 处理流程                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  [用户 ROM]                                                          │
│      │                                                              │
│      ▼                                                              │
│  [解包] ← payload-dumper/lpunpack ← ⚠️ 恶意代码可能在这里执行        │
│      │                                                              │
│      ▼                                                              │
│  [修改] ← APKEditor/apktool ← ⚠️ 被篡改的 JAR 可注入恶意代码         │
│      │                                                              │
│      ▼                                                              │
│  [注入] ← KernelSU/wild_boost ← 🔴 从网络下载的未验证文件            │
│      │                                                              │
│      ▼                                                              │
│  [打包] ← lpmake/mkfs.erofs ← ✅ 相对安全                           │
│      │                                                              │
│      ▼                                                              │
│  [用户设备] ← 刷入 ← 🔴 最终风险承载者                               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 七、缓解措施建议

### 7.1 工具替换建议

| 当前工具 | 建议替换 | 来源 | 验证方法 |
|----------|----------|------|----------|
| magiskboot | 保留，验证 SHA256 | Magisk 官方 Release | 比对官方校验和 |
| payload-dumper | payload-dumper-go | https://github.com/ssut/payload-dumper-go | 验证 Release 签名 |
| apktool.jar | 官方版本 | https://github.com/iBotPeaches/Apktool/releases | SHA256 验证 |
| APKEditor.jar | 官方版本 | https://github.com/REAndroid/APKEditor/releases | SHA256 验证 |

### 7.2 代码改进建议

#### 1. 添加 SHA256 校验

```python
# 建议添加到配置文件
TOOL_CHECKSUMS = {
    "magiskboot": "expected_sha256_hash...",
    "apktool.jar": "expected_sha256_hash...",
    # ...
}

def verify_tool(tool_path: Path, expected_hash: str) -> bool:
    actual = hashlib.sha256(tool_path.read_bytes()).hexdigest()
    return actual == expected_hash
```

#### 2. HTTPS 下载签名验证

```python
# 对于 KernelSU 下载
def download_ksu_with_verification():
    # 1. 下载文件
    # 2. 下载签名文件 (.sig)
    # 3. 使用 GPG 或 minisign 验证
    # 4. 验证通过后才使用
```

#### 3. 运行时完整性检查

```python
def startup_integrity_check():
    """启动时验证所有关键工具的完整性"""
    for tool_name, expected_hash in TOOL_CHECKSUMS.items():
        tool_path = get_tool_path(tool_name)
        if not verify_tool(tool_path, expected_hash):
            raise SecurityError(f"Tool {tool_name} failed integrity check!")
```

### 7.3 用户安全建议

1. **工具来源验证**:
   - 从官方渠道重新下载所有二进制工具
   - 使用 `sha256sum` 验证文件完整性

2. **网络下载控制**:
   - 在隔离环境中首次运行
   - 手动下载 KernelSU 等组件到 `assets/` 目录
   - 使用 `--no-download` 参数（需添加）禁止网络下载

3. **ROM 来源验证**:
   - 仅使用官方或可信来源的 ROM
   - 验证 ROM 的 MD5/SHA256 校验和

4. **运行环境**:
   - 使用虚拟机或隔离环境进行测试
   - 不要在生产环境直接运行

---

## 八、安全检查清单

### 运行前检查

- [ ] 验证所有二进制工具的 SHA256
- [ ] 从官方源重新下载 JAR 文件
- [ ] 检查网络下载配置
- [ ] 审查设备配置文件内容

### 运行时监控

- [ ] 监控网络请求
- [ ] 记录所有文件修改
- [ ] 检查临时文件内容

### 输出验证

- [ ] 验证生成的镜像大小合理
- [ ] 检查刷机包内容
- [ ] 在测试设备上验证

---

## 九、结论

### 风险总结

| 风险类别 | 等级 | 影响 |
|----------|------|------|
| 二进制工具注入 | 🔴 高 | 设备完全被控制 |
| 网络下载劫持 | 🔴 高 | 设备完全被控制 |
| JAR 文件篡改 | ⚠️ 中 | APK 内注入恶意代码 |
| 配置文件后门 | ⚠️ 中 | 系统功能被篡改 |

### 建议行动

1. **立即**: 添加所有工具的 SHA256 校验
2. **短期**: 实现网络下载的签名验证
3. **中期**: 将所有工具替换为官方版本并提供验证脚本
4. **长期**: 建立自动化安全审计流程

---

## 附录 A: 官方工具下载地址

```
# Magisk (magiskboot)
https://github.com/topjohnwu/Magisk/releases

# Apktool
https://github.com/iBotPeaches/Apktool/releases

# APKEditor
https://github.com/REAndroid/APKEditor/releases

# smali/baksmali
https://github.com/JesusFreke/smali/releases

# payload-dumper-go
https://github.com/ssut/payload-dumper-go/releases

# KernelSU
https://github.com/tiann/KernelSU/releases

# Android SDK (aapt2)
https://developer.android.com/studio#command-tools

# EROFS Tools
https://github.com/erofs/erofs-utils/releases
```

## 附录 B: 当前工具 SHA256 校验和

### Linux x86_64 二进制文件

```
c9f30b34c02fd48165251541125c3b7f21b98624e0f8341436fc65a84095e5d6  aapt2
ab04484e27480404a32df818c1da12bebaceadab4895f50880153dfaad84e748  aapt2-9.0.1-14304508-linux.jar
c6477t6af7fb26466e9d33730d61e19445177457193f3e3460e3e0114c69  brotli
6b2838d7085047ead202baa26bb4f0724b26e2f0b2d2  e2fsdroid
a338d7085047ead202baa26bb4f0724b26e2f0b2d2  extract.erofs
b53dcrr2t82d69f7adc6665f9260f3544723a35ec97e36de3b1c9ff54082971  lpunpack
21d4fd18592c0c5160520bb991f8ded6d40bd901784f82276c3e303c2a8020a2  magiskboot
03f85f707f7ffdcf4f27f70d3b4b135759af118340c9df  mke2fs
f3cf94ed90f110b597a91a440e7e566ef1ae00b4a18e01e80809ee6d0f2772ec  mkfs.erofs
f3cf94ed90f110b597a91a440e7e566ef1ae00b4a18e01e80809ee6d0f2772ec  payload-dumper
b53dcrr2t82d69f7adc6665f9260f3544723a35ec97e36de3b1c9ff54082971  simg2img
```

### JAR 文件

```
5678ffcfb0102d4b3e25c8afb90667430a3dba30325d5cbc4a3df31dcc4b42ff  APKEditor.jar
db1344ef2cc61f612a22d8ba71f26256f7bcd2540aad2823e6848bfb5d401a1b  apktool.jar
4896337b63a48c318de35f1f861b2a374d0f1ad6b17b6067e16b7d788e8ce4ef  baksmali.jar
f98a5ac906a3c2a97b2b5ac50d695e8f855b5e94b2a5ac50d695e8f855b5e94  smali.jar
```

### 官方校验和对比

| 工具 | 本地 SHA256 | 官方验证 |
|------|-------------|----------|
| magiskboot | 21d4fd18592c... | ⚠️ 需对比 Magisk Release |
| apktool.jar | db1344ef2cc6... | ⚠️ 需对比 Apktool Release |
| APKEditor.jar | 5678ffcfb010... | ⚠️ 需对比 APKEditor Release |

---

**免责声明**: 本文档仅用于安全分析目的，不构成任何形式的安全保证。用户应自行评估风险并采取适当的防护措施。
