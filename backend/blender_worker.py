"""
BlendBridge Worker - Blender Python 脚本（跨平台兼容）
由 Flask 后端通过 subprocess 调用 Blender 执行

功能：
  1. 解包 .blend 内部打包的纹理到外部文件
  2. 将 Emission 着色器材质转换为 Principled BSDF（FBX 兼容）
  3. 导出 FBX（含 .fbm 纹理文件夹）
  4. 打包结果为 zip

路径约定：
  - Blender 内部始终使用正斜杠 (/) ，即使在 Windows 上
  - 导出到磁盘时使用 os.path.join 适配平台分隔符
"""
import bpy
import os
import json
import zipfile


def _blender_path(native_path: str) -> str:
    """将 OS 路径转换为 Blender 内部的正斜杠路径"""
    return native_path.replace("\\", "/")


def unpack_textures(output_dir):
    """解包所有打包的纹理到外部文件"""
    tex_dir = os.path.join(output_dir, "textures")
    os.makedirs(tex_dir, exist_ok=True)

    unpacked = []
    for img in bpy.data.images:
        if img.name == "Render Result":
            continue
        if not img.packed_file:
            continue

        # 物理路径用 OS 分隔符
        filepath = os.path.join(tex_dir, img.name + ".png")
        # Blender 的 filepath 属性使用正斜杠
        img.filepath = _blender_path(filepath)
        img.unpack(method="WRITE_LOCAL")

        unpacked.append({
            "name": img.name,
            "size": list(img.size),
            "path": img.filepath,
        })

    return unpacked


def convert_materials():
    """将 Emission 着色器材质转换为 Principled BSDF"""
    converted = []
    skipped = []

    for mat in bpy.data.materials:
        if not mat.node_tree:
            continue

        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        tex_node = None
        output_node = None
        has_principled = False

        for node in nodes:
            if node.type == "TEX_IMAGE" and tex_node is None:
                tex_node = node
            if node.type == "OUTPUT_MATERIAL" and output_node is None:
                output_node = node
            if node.type == "BSDF_PRINCIPLED":
                has_principled = True

        if tex_node is None or output_node is None:
            skipped.append(mat.name)
            continue

        if has_principled:
            skipped.append(mat.name)
            continue

        # 检查纹理是否连接到了 Emission 节点
        needs_convert = False
        if tex_node.outputs["Color"].is_linked:
            for link in tex_node.outputs["Color"].links:
                if link.to_node.type == "EMISSION":
                    needs_convert = True
                    break

        if not needs_convert:
            skipped.append(mat.name)
            continue

        # 创建 Principled BSDF 节点
        bsdf = nodes.new("ShaderNodeBsdfPrincipled")
        bsdf.location = (400, 300)
        bsdf.label = "BlendBridge Auto"

        # 纹理 Color → BSDF Base Color
        links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])

        # 断开旧连接，连接 BSDF → Material Output
        for link in list(links):
            if link.to_node == output_node and link.to_socket.name == "Surface":
                links.remove(link)
        links.new(bsdf.outputs["BSDF"], output_node.inputs["Surface"])

        converted.append(mat.name)

    return converted, skipped


def export_fbx(output_dir, blend_path):
    """导出 FBX 并打包为 zip（同时包含修复后的 .blend）"""
    # 从 .blend 文件名提取基础名（兼容 Windows 反斜杠）
    blend_filepath = bpy.data.filepath.replace("\\", "/")
    blend_name = os.path.splitext(os.path.basename(blend_filepath))[0]
    if not blend_name:
        blend_name = "output"

    fbx_path = os.path.join(output_dir, blend_name + ".fbx")
    fixed_blend_path = os.path.join(output_dir, blend_name + "_fixed.blend")

    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    # 保存修复后的 .blend 副本
    bpy.ops.wm.save_as_mainfile(filepath=_blender_path(fixed_blend_path), copy=True)

    # 选择要导出的对象（Mesh + Armature）
    bpy.ops.object.select_all(action="DESELECT")
    export_types = {"MESH", "ARMATURE", "EMPTY"}
    selected_count = 0
    for obj in bpy.data.objects:
        if obj.type in export_types:
            obj.select_set(True)
            selected_count += 1

    # 导出 FBX（Blender 内部使用正斜杠路径）
    bpy.ops.export_scene.fbx(
        filepath=_blender_path(fbx_path),
        use_selection=True,
        path_mode="COPY",
        embed_textures=False,
        axis_forward="-Z",
        axis_up="Y",
        object_types=export_types,
        use_mesh_modifiers=True,
        add_leaf_bones=False,
        bake_anim=False,
    )

    # 打包 FBX + .fbm + 修复后 .blend 为 zip
    fbm_dir = os.path.splitext(fbx_path)[0] + ".fbm"
    zip_path = os.path.join(output_dir, "result.zip")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        if os.path.isfile(fbx_path):
            zf.write(fbx_path, os.path.basename(fbx_path))
        if os.path.isdir(fbm_dir):
            for root, _, files in os.walk(fbm_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.join(
                        os.path.basename(fbm_dir),
                        os.path.relpath(file_path, fbm_dir),
                    )
                    # zip 内部统一使用正斜杠
                    zf.write(file_path, arcname.replace("\\", "/"))
        # 包含修复后的 .blend
        if os.path.isfile(fixed_blend_path):
            zf.write(fixed_blend_path, os.path.basename(fixed_blend_path))

    return {
        "fbx_path": fbx_path,
        "zip_path": zip_path,
        "blend_path": fixed_blend_path,
        "fbm_exists": os.path.isdir(fbm_dir),
        "fbx_size": os.path.getsize(fbx_path),
        "blend_size": os.path.getsize(fixed_blend_path) if os.path.isfile(fixed_blend_path) else 0,
        "selected_objects": selected_count,
    }


def main():
    output_dir = os.environ.get("BLEND_OUTPUT_DIR", "")
    if not output_dir:
        import tempfile
        output_dir = os.path.join(tempfile.gettempdir(), "blendbridge_worker")

    os.makedirs(output_dir, exist_ok=True)

    result = {
        "success": True,
        "unpacked_textures": [],
        "converted_materials": [],
        "skipped_materials": [],
        "export": {},
        "errors": [],
    }

    try:
        # Step 1: 解包纹理
        result["unpacked_textures"] = unpack_textures(output_dir)

        # Step 2: 转换材质
        converted, skipped = convert_materials()
        result["converted_materials"] = converted
        result["skipped_materials"] = skipped

        # Step 3: 保存修改后的 .blend（覆盖原文件 + 保存副本到输出目录）
        bpy.ops.wm.save_mainfile()

        # Step 4: 导出 FBX（同时保存修复后 .blend 副本）
        result["export"] = export_fbx(output_dir, bpy.data.filepath)

    except Exception as exc:
        result["success"] = False
        result["errors"].append(f"{type(exc).__name__}: {exc}")

    # 输出结果（Flask 端通过 stdout 解析）
    print("BLENDBRIDGE_RESULT_START")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("BLENDBRIDGE_RESULT_END")


if __name__ == "__main__":
    main()
