import json


with open("dist/fusion-properties.json", "r", encoding="utf-8") as f:
    data = json.load(f)


results_length = 3
all_ids = list(data.keys())
name_map = {v["name"]: k for k, v in data.items()}
rarities = ["Common", "Uncommon", "Rare", "Epic", "Legendary"]
rarity_letters = [rarity[0] for rarity in rarities]
categories = ["Forest", "Water", "Combat"]
families = set()
for attributes in data.values():
    family = attributes.get("family", None)
    if family and len(family) > 0:
        families.update(set(family))
shard_groups = {
    "Mining": ["Hideonleaf", "Miner Zombie", "Flitter", "Hideonsun", "Troglobyte", "Hideoncave",
               "Treasure Hoarder", "Honeymite", "Star Sentry", "Silentdepth", "Thyst", "Quartzfang",
               "Stalagmight", "Fungloom", "Snoozle", "Scrappy", "Stoneworm", "Abyssal Miner", "Bal",
               "Cavernshade", "Gemzie", "Scatha", "Nilbog"]
}
chameleon_id = name_map["Chameleon"]

# Output amounts, per the wiki's "Input and Output amounts" table
chameleon_output_amount = 1
special_output_amount = 2
id_fusion_output_amount = 1


def get_category(input_):
    return data.get(input_, {}).get("category", None)


def get_id_result(input_):
    return name_map.get(data.get(input_, {}).get("id_result"), None)


def find_chameleon_results(input_):
    return [name_map[name] for name in data[input_]["chameleon_result"]]


def fusion_sort_key(id_):
    base, _, suffix = id_[1:].partition("-")
    return len(rarity_letters) - rarity_letters.index(id_[0]), int(base), int(suffix) if suffix else 0


def id_rank_key(id_):
    base, _, suffix = id_[1:].partition("-")
    return rarity_letters.index(id_[0]), int(base), int(suffix) if suffix else 0


def find_id_fusion_results(input1, input2):
    if get_category(input1) == get_category(input2):
        chosen = max((input1, input2), key=id_rank_key)
        result = get_id_result(chosen)
        return [result] if result else []
    results = [result for result in (get_id_result(input1), get_id_result(input2)) if result]
    results.sort(key=fusion_sort_key)
    return results


def get_rarity_membership(input_, group):
    if "+" in group:
        input_index = rarity_letters.index(input_[0])
        group_index = rarity_letters.index(group[0])
        return input_index >= group_index
    else:
        return input_[0] == group[0]


def get_category_membership(input_, group):
    return data.get(input_, {}).get("category", None) == group


def get_family_membership(input_, group):
    return group in data.get(input_, {}).get("family", [])


def get_name(input_):
    return data.get(input_, {}).get("name", None)


def match_member(input_, member):
    if member == "Any":
        return True
    elif member.strip("+") in rarities:
        return get_rarity_membership(input_, member)
    elif member in categories:
        return get_category_membership(input_, member)
    elif member in families:
        return get_family_membership(input_, member)
    elif member in shard_groups:
        return get_name(input_) in shard_groups[member]
    else:
        if member.endswith(" Shard"):
            if get_name(input_) != member.replace(" Shard", ""):
                return False
        if get_name(input_) == member.replace(" Shard", ""):
            return True
        return False

def check_membership(input_, group):
    if "&" in group:
        members = group.split("&")
        return all(match_member(input_, member) for member in members)
    elif "|" in group:
        members = group.split("|")
        return any(match_member(input_, member) for member in members)
    else:
        return match_member(input_, group)


sp_fusion_map = {}
for id_, attributes in data.items():
    sp_input1 = attributes.get("input1", None)
    sp_input2 = attributes.get("input2", None)
    if not sp_input1 and not sp_input2:
        continue
    if sp_input1 and not sp_input2:
        sp_input2 = "Any"
    elif not sp_input1 and sp_input2:
        sp_input1 = "Any"
    sp_fusion_map[id_] = [sp_input1, sp_input2]


def find_special_fusion_results(input1, input2):
    matching_fusions = []
    generic_plus_fusions = []
    for id__, inputs in sp_fusion_map.items():
        if ((check_membership(input1, inputs[0]) and check_membership(input2, inputs[1])) or
            (check_membership(input1, inputs[1]) and check_membership(input2, inputs[0]))):
            if data[id__].get("recipe_type") == "GENERIC_PLUS":
                generic_plus_fusions.append(id__)
            else:
                matching_fusions.append(id__)
    matching_fusions.sort(key=fusion_sort_key)
    generic_plus_fusions.sort(key=fusion_sort_key)
    return matching_fusions, generic_plus_fusions


def test_fusion(input1_, input2_):

    if input1_ == chameleon_id or input2_ == chameleon_id:
        other = input2_ if input1_ == chameleon_id else input1_
        return [{"id": res, "count": chameleon_output_amount} for res in find_chameleon_results(other)]

    sp_results, generic_plus_results = find_special_fusion_results(input1_, input2_)
    id_results = find_id_fusion_results(input1_, input2_)

    results = []
    seen = {input1_, input2_}
    for tier, count in ((sp_results, special_output_amount),
                        (generic_plus_results, special_output_amount),
                        (id_results, id_fusion_output_amount)):
        for res in tier:
            if len(results) >= results_length:
                return results
            if res in seen:
                continue
            seen.add(res)
            results.append({"id": res, "count": count})
    return results


def generate_fusion_recipes():
    """test_fusion is symmetric (verified against in-game data: fusing A+B always
    yields the same results as B+A), so only the unordered pairs need generating."""
    fusion_recipes_ = {}
    for i in range(len(all_ids)):
        for j in range(i, len(all_ids)):
            input1 = all_ids[i]
            input2 = all_ids[j]
            result = test_fusion(input1, input2)
            if result:
                fusion_key = f"{input1}+{input2}"
                fusion_recipes_[fusion_key] = result
        print(f"Processed all combinations for {i+1}/{len(all_ids)} shards")
    return fusion_recipes_


fusion_data = {}
fusion_recipes = generate_fusion_recipes()
fusion_data["recipes"] = fusion_recipes
with open("dist/fusion-recipes.json", "w", encoding="utf-8") as f:
    json.dump(fusion_data, f, indent=2, ensure_ascii=False)
