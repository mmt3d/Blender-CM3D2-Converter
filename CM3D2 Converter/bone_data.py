import mathutils


DEFAULT_THRESHOLD = 0.0001


def calc_bone_data_diff(old: dict, new: dict) -> tuple[float, float, float]:
    """
    BoneData の位置・回転・スケールの各要素ごとの差分を算出する
    """
    d_co = (mathutils.Vector(new['co']) - mathutils.Vector(old['co'])).length
    q_new = mathutils.Quaternion(new['rot']).normalized()
    q_old = mathutils.Quaternion(old['rot']).normalized()
    d_rot = min((q_new - q_old).magnitude, (q_new + q_old).magnitude)
    d_scl = abs(new['scl'] - old['scl'])
    if 'scale' in new and 'scale' in old:
        d_scl = max(d_scl, (mathutils.Vector(new['scale']) - mathutils.Vector(old['scale'])).length)
    return d_co, d_rot, d_scl


def calc_local_bone_data_diff(old: dict, new: dict) -> float:
    """
    LocalBoneData の行列数値の最大要素差分を算出する
    """
    return max(abs(a - b) for a, b in zip(old['matrix'], new['matrix']))


def parent_name_map(bone_data: list[dict]) -> dict[str, str]:
    """
    parent_index を親ボーン名へ変換する
    """
    return {
        data['name']: bone_data[data['parent_index']]['name']
        for data in bone_data
        if data['parent_index'] >= 0
    }


def rebuild_parent_indices(bone_data: list[dict]) -> list[dict]:
    """
    parent_name を parent_index に戻し、シリアライズ用の形へ整える
    """
    name_to_index = {data['name']: index for index, data in enumerate(bone_data)}
    result = []
    for data in bone_data:
        item = data.copy()
        parent_name = item.pop('parent_name', 'None')
        item['parent_index'] = name_to_index.get(parent_name, -1)
        result.append(item)
    return result


def merge_bone_data_with_parent_names(
    old_data: list[dict], new_data: list[dict], threshold: float | None = None,
    update_map: dict[str, set[str]] | None = None, deleted_names: set[str] | None = None, inserted_names: set[str] | None = None,
) -> list[dict]:
    """
    BoneData をしきい値または選択済みフィールドに従ってマージする
    """
    old_by_name = {data['name']: data for data in old_data}
    new_by_name = {data['name']: data for data in new_data}
    old_parents = parent_name_map(old_data)
    new_parents = parent_name_map(new_data)
    deleted_names = set(old_by_name) - set(new_by_name) if deleted_names is None else deleted_names
    inserted_names = set(new_by_name) - set(old_by_name) if inserted_names is None else inserted_names

    merged = []
    for name, old in old_by_name.items():
        if name in deleted_names:
            continue
        new = new_by_name.get(name)
        if new is None:
            merged.append({**old, 'parent_name': old_parents.get(name, 'None')})
            continue

        item = old.copy()
        if update_map is None:
            diff_loc, diff_rot, diff_scl = calc_bone_data_diff(old, new)
            fields = set()
            if diff_loc >= threshold:
                fields.add('co')
            if diff_rot >= threshold:
                fields.add('rot')
            if diff_scl >= threshold:
                fields.add('scl')
            update_parent = True
        else:
            fields = update_map.get(name, set())
            update_parent = 'parent_name' in fields
        for field in fields & {'co', 'rot', 'scl'}:
            item[field] = new[field]
        if 'scl' in fields and 'scale' in new:
            item['scale'] = new['scale']
        item['parent_name'] = old_parents.get(name, 'None')
        if update_parent and name in new_parents:
            item['parent_name'] = new_parents.get(name)
        merged.append(item)

    for name, new in new_by_name.items():
        if name not in old_by_name and name in inserted_names:
            merged.append({**new, 'parent_name': new_parents.get(name, 'None')})
    return merged


def merge_bone_data(old_data: list[dict], new_data: list[dict], threshold: float = DEFAULT_THRESHOLD) -> list[dict]:
    """
    既存データと新解析データをしきい値ベースでマージする
    """
    return rebuild_parent_indices(merge_bone_data_with_parent_names(old_data, new_data, threshold))


def merge_local_bone_data(
    old_data: list[dict], new_data: list[dict], threshold: float,
    update_names: set[str] | None = None, deleted_names: set[str] | None = None, inserted_names: set[str] | None = None,
) -> list[dict]:
    """
    LocalBoneData をしきい値または選択済みボーン名に従ってマージする
    """
    old_by_name = {data['name']: data for data in old_data}
    new_by_name = {data['name']: data for data in new_data}
    deleted_names = set(old_by_name) - set(new_by_name) if deleted_names is None else deleted_names
    inserted_names = set(new_by_name) - set(old_by_name) if inserted_names is None else inserted_names

    merged = []
    for name, old in old_by_name.items():
        if name in deleted_names:
            continue
        new = new_by_name.get(name)
        should_update = False
        if new is not None:
            if update_names is not None:
                should_update = name in update_names
            else:
                should_update = calc_local_bone_data_diff(old, new) >= threshold
        if should_update:
            merged.append(new.copy())
        else:
            merged.append(old.copy())

    for name, new in new_by_name.items():
        if name not in old_by_name and name in inserted_names:
            merged.append(new.copy())

    return merged
