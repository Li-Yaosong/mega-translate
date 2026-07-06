# CLAUDE.md — MEGA Translate 项目指南

## 项目概述

MEGA (Molecular Evolutionary Genetics Analysis) 汉化工具 — 从 MEGA EXE 中提取 LFM 表单字符串，翻译后修补回 EXE 生成中文版。

- **目标软件**: MEGA 12 (分子进化遗传学分析软件，用于系统发育推断、序列比对、模型选择等)
- **开发框架**: Lazarus/Free Pascal (LFM 表单资源)
- **汉化方式**: 二进制级修补，不修改源码，直接操作 PE 文件中的 .rsrc 段

## 项目结构

```
mega_translate/
├── mega_translate.py          # 核心工具 (Python 3, 无外部依赖)
├── MEGA_64.exe                # MEGA 可执行文件
├── README.md                  # 中文文档
└── translations/
    └── zh_CN/                 # 简体中文翻译 (133 个 .ts 文件)
        ├── TMEGAFORM.ts       # 主窗口 (最大, ~1580行)
        ├── TTREEVIEWFORM.ts   # 树查看器
        ├── TV_SEQDATAEXPLORER.ts  # 序列数据浏览器
        └── ...                # 每个表单一个文件
```

## 工具命令

```bash
python mega_translate.py extract [exe] [lang]       # 提取字符串到 .ts 文件
python mega_translate.py patch   [exe] [lang] [out] # 应用翻译生成汉化 EXE
python mega_translate.py build   [exe] [lang] [out] # extract + patch 一步完成
```

- 默认 EXE: `d:\Software\MEGA12\MEGA_64.exe.bak`
- 默认语言: `zh_CN`
- 输出: `MEGA_64_zh_CN.exe`
- 再次 `extract` 不会覆盖已有翻译

## .ts 文件格式 (Qt Linguist TS XML 2.1)

```xml
<TS version="2.1" language="zh_CN" sourcelanguage="en">
  <context>
    <name>TALIGNEDITMAINFORM</name>
    <message>
      <source>&amp;Align Marked Sites</source>
      <comment>Caption (max 19 bytes)</comment>
      <translation type="finished">&amp;比对标记后序列</translation>
    </message>
    <message>
      <source>DeveloperAction</source>
      <comment>Caption (max 15 bytes)</comment>
      <translation type="unfinished"/>
    </message>
  </context>
</TS>
```

### 关键字段说明

| 字段 | 说明 |
|------|------|
| `<source>` | 英文原文 (来自 EXE 二进制) |
| `<comment>` | 属性名 + 字节长度限制，如 `Caption (max 19 bytes)` |
| `<translation type="finished">` | 已完成翻译 |
| `<translation type="unfinished"/>` | 未翻译 (空) |

### 翻译属性类型

- **Caption**: 菜单项、按钮、标签文字
- **Hint**: 鼠标悬停提示
- **Text**: 文本框内容
- **Title**: 窗口标题

## 翻译规则与约束

### 字节长度限制

- `<comment>` 中的 `max N bytes` 是原始字符串的存储空间大小
- **UTF-8 编码下**: 中文字符占 3 字节，英文/数字占 1 字节
- 翻译的 UTF-8 字节长度如果超过 max N，工具会自动触发资源重建 (rebuild)
- **翻译时无需刻意缩减**，优先保证翻译的自然流畅和专业准确，超长部分由 rebuild 机制处理

### 翻译风格

- **自然流畅**: 避免机翻味，翻译要像中文软件原生的表达
- **专业术语**: 使用生物信息学/进化遗传学领域标准中文术语
- **术语一致**: 同一英文术语在不同文件中应使用相同翻译
- **保留快捷键**: `&File` → `文件(&F)` 或 `&文件`，`&` 放在对应快捷字母前
- **保留格式标记**: 如 `\n`、`%s` 等占位符必须保留
- **中英间距**: 中文与英文/数字之间加空格，如 `DNA 序列`、`MEGA 格式`
- **Toggle 翻译**: Toggle X → 显示/隐藏 X 或 切换 X，视语境选择
- **block 翻译**: block 在比对编辑器中译为"区域"而非"块"
- **Complement**: 在 DNA 语境中译为"互补链"而非仅"互补"
- **Caption Expert**: MEGA 的序列标题编辑工具，译为"标题编辑器"
- **trace data**: 测序仪的 trace data 译为"峰图数据"（chromatogram/trace）
- **Motif**: 译为"基序"（生物信息学标准术语）
- **Codon**: 可保留英文 Codon 或译为"密码子"，视字节空间决定
- **Gap**: 在序列比对中译为"空位"

### 常见术语对照

| 英文 | 中文 | 说明 |
|------|------|------|
| Alignment | 比对 | 序列比对 |
| Phylogeny / Phylogenetic | 系统发育 | |
| Tree | 树 / 系统发育树 | 视语境 |
| Bootstrap | 自举 / Bootstrap | 常不译 |
| Maximum Likelihood (ML) | 最大似然 | |
| Parsimony | 简约 | 最大简约法 |
| Distance | 距离 | 遗传距离 |
| Model | 模型 | 替代模型 |
| Taxa / Taxon | 分类单元 | |
| Sequence | 序列 | |
| Clade | 进化支 | |
| Node | 节点 | |
| Branch | 分支 | |
| Substitution | 替换 | 核苷酸替换 |
| Selection | 选择 | 自然选择 |
| Divergence time | 分歧时间 | |
| Timetree | 时间树 | |
| Ancestral | 祖先 | 祖先状态重建 |
| Calibration | 校准 | 分子钟校准 |
| Clock | 分子钟 | |
| Likelihood | 似然 | |
| Matrix | 矩阵 | |
| Caption | 标题/标题栏 | 窗口标题 |
| Hint | 提示 | 鼠标悬停提示 |

## 当前进度

- **总翻译条目**: ~3,149 (2,177 finished + 972 unfinished)
- **完成率**: ~69%
- **文件数**: 133 个 .ts 文件
- **最大文件**: TMEGAFORM.ts (主窗口, ~1580 行)

## 技术细节

### LFM 二进制修补机制

1. **原地替换 (in-place)**: 翻译 UTF-8 字节 ≤ 原始字节 → 直接覆盖，空格 (0x20) 填充
2. **资源重建 (rebuild)**: 翻译字节 > 原始字节 → 重建整个 LFM 资源，追加到 .rsrc 段末尾
3. **vaString (0x06)**: 长度 ≤ 255 字节; **vaLString (0x0C)**: 长度 > 255 字节
4. **PE 扩展**: 更新 .rsrc VSize/RawSize、SizeOfImage、Data Directory
5. **签名移除**: 修改 EXE 后 Authenticode 签名失效，自动清零

### 注意事项

- 修改 EXE 后 Windows 可能报毒 (签名失效)，需添加排除项
- 始终从 `.bak` 备份提取，不要直接修改原始 EXE
- `patch` 命令会自动处理过长翻译 (资源重建)，但尽量控制在字节限制内

## 工作流程

1. 运行 `extract` 从 EXE 提取/更新 .ts 文件
2. 翻译 .ts 文件中的 `unfinished` 条目
3. 运行 `patch` 或 `build` 生成汉化 EXE
4. 测试汉化 EXE，检查界面显示

## 翻译工作注意事项

- 翻译前先检查 `<comment>` 中的字节限制
- 中文字符 UTF-8 占 3 字节，`&` 快捷键标记占 1 字节
- 翻译完成后将 `type="unfinished"` 改为 `type="finished"`
- 可用 Qt Linguist 打开 .ts 文件进行可视化编辑
- 也可直接编辑 XML 文本
