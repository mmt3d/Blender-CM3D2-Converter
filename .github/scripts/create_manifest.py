import ast
import json
import os
import tomllib


def extract_bl_info(script_path):
    """
    指定コードファイル から bl_info を抽出する
    """
    with open(script_path, "r", encoding="utf-8") as f:
        source_code = f.read()
    tree = ast.parse(source_code)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "bl_info":
                    try:
                        return ast.literal_eval(node.value)
                    except (ValueError, SyntaxError) as e:
                        raise ValueError(f"Failed to parse {node.value}: {e}")
    raise ValueError("Not found bl_info")


def main():
    addon_dir = os.environ["ADDON_DIR"]
    bl_info_script = os.environ["BL_INFO_SCRIPT"]
    base_toml_path = "blender_manifest_base.toml"

    with open(base_toml_path, "rb") as f:
        manifest = tomllib.load(f)
    addon_id = manifest["id"]

    bl_info = extract_bl_info(bl_info_script)
    version = ".".join(map(str, bl_info.get("version")))
    bl_version = ".".join(map(str, bl_info.get("blender")))

    zip_name = f"{addon_id}-{version}.zip"
    with open(os.environ['GITHUB_OUTPUT'], "a") as fh:
        print(f"zip_name={zip_name}", file=fh)
        print(f"version={version}", file=fh)

    # merge
    manifest["version"] = version
    manifest["name"] = bl_info["name"]
    manifest["tagline"] = bl_info["description"]
    manifest["maintainer"] = os.environ["GITHUB_REPOSITORY_OWNER"]
    manifest["blender_version_min"] = bl_version

    toml_lines = []
    for key, value in manifest.items():
        if isinstance(value, (str, int, float)):
            toml_lines.append(f'{key} = "{value}"' if isinstance(value, str) else f'{key} = {value}')
        elif isinstance(value, list):
            toml_lines.append(f'{key} = {json.dumps(value)}')
        elif isinstance(value, dict):
            toml_lines.append(f'[{key}]\n' + '\n'.join(f'{k} = "{v}"' for k, v in value.items()))

    toml_path = os.path.join(addon_dir, "blender_manifest.toml")
    with open(toml_path, "w", encoding="utf-8") as f:
        f.write("\n".join(toml_lines) + "\n")

    print(f"Successfully created manifest: {toml_path}")


if __name__ == "__main__":
    main()