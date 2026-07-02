import hashlib
import json
import os
import tomllib


def calculate_sha256(filepath: str):
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b''):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def main():
    addon_dir = os.environ["ADDON_DIR"]
    toml_path = os.path.join(addon_dir, "blender_manifest.toml")
    with open(toml_path, "rb") as f:
        manifest = tomllib.load(f)

    repo_name = os.environ["GITHUB_REPOSITORY"]
    tag_name = os.environ["TAG_NAME"]
    zip_name = os.environ["ZIP_NAME"]

    manifest["archive_url"] = f"https://github.com/{repo_name}/releases/download/{tag_name}/{zip_name}"
    manifest["archive_size"] = os.path.getsize(zip_name)
    manifest["archive_hash"] = f"sha256:{calculate_sha256(zip_name)}"
    manifest["extra"] = {"archive_releases": f"https://github.com/{repo_name}/releases"}

    with open("metadata.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("Successfully created metadata.json")


if __name__ == "__main__":
    main()