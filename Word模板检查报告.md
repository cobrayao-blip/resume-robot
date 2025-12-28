# Word模板检查报告

## 检查时间
2025-12-09

## 检查结果

### ✅ 没有使用自定义Word模板

**检查内容**：
1. 代码中创建文档的方式：`self.doc = Document()`
   - 使用 `Document()` 创建新文档，**没有加载任何模板文件**
   - 代码位置：`backend/app/services/word_exporter.py` 第18行和第26行

2. 文件系统检查：
   - ✅ 没有找到任何 `.docx` 模板文件
   - ✅ 没有找到 `*template*.docx` 文件
   - ✅ `backend` 目录下没有模板文件

3. 代码检查：
   - ✅ 没有 `Document(template_path)` 这样的调用
   - ✅ 没有加载外部模板文件的代码

### ⚠️ Word默认样式可能有段前间距

**问题分析**：
- Word的Normal样式可能有默认的段前间距（如6磅）
- 这个默认值可能来自：
  1. **python-docx库的默认行为**
  2. **Word应用程序的默认Normal样式设置**
  3. **系统或用户自定义的Word模板**

**当前代码**：
- `_setup_document_styles()` 方法只设置了字体（第204-216行）
- **没有清除Normal样式的段前间距**

## 解决方案

### 方案1：在Normal样式中清除段前间距（推荐）

尝试通过XML操作清除Normal样式的段前间距：

```python
def _setup_document_styles(self):
    """设置文档样式"""
    # 设置默认字体
    style = self.doc.styles['Normal']
    font = style.font
    font.name = '微软雅黑'
    font.size = Pt(10.5)
    
    # 设置中文字体
    self.doc.styles['Normal']._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    
    # 尝试清除Normal样式的默认段前间距
    try:
        # 获取样式的段落格式元素
        pPr = style._element.pPr
        if pPr is None:
            # 如果段落格式元素不存在，创建一个
            from docx.oxml import parse_xml
            pPr = parse_xml(r'<w:pPr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>')
            style._element.append(pPr)
        
        # 清除段前间距（设置为0）
        spacing = pPr.find(qn('w:spacing'))
        if spacing is not None:
            spacing.set(qn('w:before'), '0')
        else:
            spacing = OxmlElement('w:spacing')
            spacing.set(qn('w:before'), '0')
            pPr.append(spacing)
    except Exception as e:
        logger.warning(f"无法清除Normal样式的段前间距: {e}")
```

### 方案2：在每个段落显式设置（当前方案）

在每个项目段落显式设置段前间距，覆盖默认值：

```python
if idx > 0:
    project_paragraph.paragraph_format.space_before = Pt(12)
else:
    project_paragraph.paragraph_format.space_before = Pt(0)
```

### 方案3：检查Word应用程序设置

如果问题仍然存在，可能需要：
1. 检查Word应用程序的默认Normal样式设置
2. 检查是否有系统级别的Word模板（如 `Normal.dotm`）
3. 检查用户自定义的Word模板

## 建议

1. **优先尝试方案1**：在Normal样式中清除段前间距
2. **如果方案1不生效**：检查Word应用程序的默认设置
3. **如果仍然不生效**：可能需要使用更底层的XML操作来强制设置

## 相关文件

- `backend/app/services/word_exporter.py` - Word导出服务
- 没有找到任何Word模板文件

## 检查时间

2025-12-09

