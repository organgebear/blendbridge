# 🌉 BlendBridge

> Blender FBX 纹理修复工具 —— 一键解决 Unity/Unreal 导入白模问题

## 这是什么？

Blender 模型导出 FBX 到 Unity 后经常显示**白模**——贴图全丢。原因是两个问题叠加：

| 问题 | 说明 |
|------|------|
| 📦 纹理 Packed | 贴图嵌入 `.blend` 内部，`filepath` 为空，FBX 导出器找不到路径 |
| ⚡ Emission 材质 | MMD/动画风格模型用 Emission 着色器，FBX 只认 Principled BSDF |

**BlendBridge** 把这两步全自动化：上传 `.blend` → 自动修复 → 下载含贴图的 FBX。

---

## 🚀 快速开始

### 零依赖启动

**下载项目后直接运行，不需要 pip install，不需要下载任何东西。**

| 平台 | 启动方式 |
|------|---------|
| 🍎 macOS | 终端运行 `./start.sh` |
| 🐧 Linux | 终端运行 `./start.sh` |
| 🪟 Windows | 双击 `start.bat` |

### 前置条件

| 条件 | 说明 |
|------|------|
| Python 3.8+ | 系统自带或自行安装 |
| Blender 4.0+ | 用于处理 .blend 文件 |

> 💡 macOS 提示权限？先运行：`chmod +x start.sh`
>
> 💡 原理：后端纯 Python 标准库实现（`http.server`），没有任何第三方依赖。

---

## 使用流程

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│ 1. 上传  │ → │ 2. 诊断  │ → │ 3. 修复  │ → │ 4. 下载  │
│ .blend   │    │ 自动检测 │    │ Blender  │    │ FBX+贴图 │
└─────────┘    └─────────┘    └─────────┘    └─────────┘
```

1. **上传**：拖拽或点击上传 `.blend` 文件
2. **诊断**：自动检测纹理是否打包、材质是否为 Emission
3. **修复**：Blender 后台执行解包 + 材质转换 + FBX 导出
4. **下载**：获取 zip 包（FBX + `.fbm` 贴图文件夹）

### 导入 Unity

```
# 解压下载的 zip
unzip 模型名_fixed.zip

# 得到
模型名.fbx          ← FBX 模型
模型名.fbm/         ← 贴图文件夹
  ├── Image_0.png
  ├── Image_1.png
  └── ...
```

**将 `.fbx` 和 `.fbm` 文件夹一起拖入 Unity Assets**，Unity 会自动关联贴图。

> 💡 若仍白模：选中 FBX → Inspector → Materials → Extract Materials → Apply

---

## 项目结构

```
blendbridge/
├── backend/
│   ├── server.py              # 后端服务（纯标准库，无依赖）
│   └── blender_worker.py      # Blender Python 修复脚本
├── static/
│   ├── index.html             # Vue 3 + Element Plus 前端
│   ├── app.js                 # 前端逻辑
│   └── style.css              # 自定义样式
├── start.sh                   # 🔥 macOS / Linux 启动器
├── start.bat                  # 🔥 Windows 启动器
├── .gitignore
└── README.md
```

---

## 技术栈

| 层 | 技术 | 外部依赖 |
|----|------|---------|
| 前端 | Vue 3 + Element Plus（CDN） | 无 |
| 后端 | Python `http.server`（标准库） | **无** |
| 引擎 | Blender Python API | Blender 自带 |

### 为什么不用 Flask？

Flask 需要 `pip install`，在国内网络环境下容易超时/失败。
Python 标准库自带的 `http.server` 完全可以胜任这个简单的上传-处理-下载流程，零依赖，开箱即用。

---

## 修复原理

### Step 1：纹理解包

```python
for img in bpy.data.images:
    if img.packed_file:
        img.filepath = "//textures/" + img.name + ".png"
        img.unpack(method='WRITE_LOCAL')
```

### Step 2：材质转换

```python
# Emission → Principled BSDF（FBX 导出器能识别的 PBR 材质）
bsdf = nodes.new('ShaderNodeBsdfPrincipled')
links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
links.new(bsdf.outputs['BSDF'], output_node.inputs['Surface'])
```

### Step 3：FBX 导出

```python
bpy.ops.export_scene.fbx(
    path_mode='COPY',      # 贴图复制到 .fbm 文件夹
    embed_textures=False,  # 不嵌入（Unity 兼容性更好）
    axis_forward='-Z',
    axis_up='Y',           # Unity 坐标系
)
```

---

## 常见问题

### Q: 启动时提示 "未找到 Python 3"？

A: 安装 Python 3.8+：
- macOS: `brew install python@3`
- Windows: Microsoft Store 搜 "Python 3.12" 一键安装，或 [python.org](https://www.python.org/downloads/)
- Ubuntu: `sudo apt install python3`

### Q: 启动时提示 "Blender 未找到"？

A: 安装 Blender 4.0+ 到默认路径：
- 官网：[blender.org/download](https://www.blender.org/download/)
- macOS: `brew install --cask blender`
- Ubuntu: `sudo snap install blender --classic`

### Q: 修复后 Unity 中仍然白模？

A: 三个可能原因：
1. `.fbm` 文件夹和 `.fbx` 没有放在同一目录
2. Unity 材质未 Extract（FBX Inspector → Materials → Extract）
3. 渲染管线不匹配（URP/HDRP 需切换 Material Shader）

### Q: 支持哪些 Blender 版本？

A: Blender 4.0+。旧版 API（如 `image.unpack()` 枚举值）可能不同。

### Q: 会修改我的原始 .blend 吗？

A: **不会**。上传的文件被复制到临时目录处理，原始文件不受任何影响。

![材质渲染效果](screenshot.png)

## License

MIT — 随意使用、修改、分发。
