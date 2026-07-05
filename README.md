# MEGA Translate

MEGA (Molecular Evolutionary Genetics Analysis) 本地化工具 — 从 EXE 提取 LFM 表单字符串，应用翻译生成本地化版本。

## 功能

- **extract**: 从 MEGA EXE 提取 LFM 表单字符串到独立 .ts 文件（按表单拆分）
- **patch**: 读取 .ts 翻译文件，修补 EXE（支持原地替换 + 资源重建）
- **build**: extract + patch 一步完成

## 用法

```bash
# 提取字符串（默认语言 zh_CN）
python mega_translate.py extract [exe] [lang]

# 应用翻译生成 EXE
python mega_translate.py patch [exe] [lang] [out]

# 提取 + 修补
python mega_translate.py build [exe] [lang] [out]
```

### 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| exe | MEGA_64.exe.bak | 原始 EXE 路径 |
| lang | zh_CN | 目标语言代码（zh_CN, ja_JP, ko_KR 等） |
| out | 自动生成 | 输出 EXE 路径（如 MEGA_64_zh_CN.exe） |

### 翻译文件结构

```
translations/
  zh_CN/              # 中文翻译
    TMEGAFORM.ts      # 每个表单一个 .ts 文件
    TABOUTBOX.ts
    ...
  ja_JP/              # 日文翻译（未来）
    ...
```

每个 `.ts` 文件可用 **Qt Linguist** 打开编辑。再次 `extract` 不会覆盖已有翻译。

## 技术细节

- **LFM 二进制格式**: Lazarus 表单资源，属性值类型 0x06=vaString, 0x0C=vaLString
- **原地替换**: 翻译字节 ≤ 原始字节时，直接覆盖，空格(0x20)填充
- **资源重建**: 翻译字节 > 原始字节时，重建整个 LFM 资源，追加到 .rsrc 段末尾
- **vaString→vaLString**: 翻译超过 255 字节时自动转换类型
- **PE 扩展**: 更新 .rsrc VSize/RawSize、SizeOfImage、Data Directory
- **签名移除**: 修改 EXE 后签名必然失效，自动清零
