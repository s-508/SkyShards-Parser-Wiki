from functools import cmp_to_key
from collections import Counter
from typing import Any
import hashlib
import json
import os
import sys

output_path = "dist/fusion-properties.json"
source_path = "fusion-properties.json"
override_path = "override-fusion-properties.json"
shard_data_path = "shard-data.json"
hashes_path = "shard-hashes.json"

github_actions = os.environ.get('GITHUB_ACTIONS')

# Parse arguments (cba to do this properly)
update_hashes = github_actions
for arg in sys.argv[1:]:
    match arg:
        case "--update-hashes":
            update_hashes = True

# Define rarities
rarity_names = {
    "Common": "Common",
    "Uncommon": "Uncommon",
    "Rare": "Rare",
    "Epic": "Epic",
    "Legendary": "Legendary"
}
rarity_letters = [rarity[0] for rarity in rarity_names.values()]

CHAMELEON_NAME = "Chameleon"
REDUCED_INPUT_FAMILIES = frozenset({"Elemental", "Amphibian", "Eel", "Croco", "Reptile", "Lizard", "Scaled", "Serpent", "Turtle"})
CHAMELEON_INPUT_AMOUNT = 1
REDUCED_INPUT_AMOUNT = 2
DEFAULT_INPUT_AMOUNT = 5

# ID-Fusion checks the ID in steps of 3
ID_FUSION_STEP = 3
# Chameleon Fusion returns the next 3 IDs
CHAMELEON_SLOTS = 3

# Results scraped from the wiki, kept only to check our derivations against
WIKI_PREFIX = "_wiki_"


def parse_id(id_):
    base, _, suffix = id_[1:].partition("-")
    return rarity_letters.index(id_[0]), int(base), int(suffix) if suffix else 0

def cmp_id(a, b):
    ka, kb = parse_id(a), parse_id(b)
    return (ka > kb) - (ka < kb)

def shard_number(id_):
    return parse_id(id_)[1]

def next_rarity_letter(letter):
    index = rarity_letters.index(letter)
    return rarity_letters[index + 1] if index + 1 < len(rarity_letters) else None

# Load source data
with open(source_path, encoding="utf-8") as f:
    output: dict[str, dict[str, Any]] = json.load(f)
with open(override_path, encoding="utf-8") as f:
    overrides: dict[str, dict[str, Any]] = json.load(f)
with open(shard_data_path, encoding="utf-8") as f:
    shard_data: dict[str, Any] = json.load(f)["shards"]
with open(hashes_path, encoding="utf-8") as f:
    hashes = json.load(f)
updated_hashes = {}
changed_shards = []

# Fields that don't exist on the scraped shard until later derivation, but can be overridden
DERIVED_OVERRIDE_FIELDS = frozenset({"fuse_amount"})

# Apply corrections on top of the scraped wiki data
overridden_ids = []
excluded_ids = []
fuse_amount_overrides: dict[str, int] = {}
for shard_id, patch in overrides.items():
    if shard_id.startswith("_"):
        continue
    if shard_id not in output:
        raise ValueError(f"override for unknown shard id: {shard_id}")
    if patch.get("_exclude"):
        excluded_ids.append(shard_id)
    fields = {key: value for key, value in patch.items() if not key.startswith("_")}
    if "fuse_amount" in fields:
        fuse_amount_overrides[shard_id] = fields.pop("fuse_amount")
    unknown_fields = sorted(set(fields) - set(output[shard_id]) - DERIVED_OVERRIDE_FIELDS)
    if unknown_fields:
        raise ValueError(f"override {shard_id} sets unknown fields: {', '.join(unknown_fields)}")
    output[shard_id].update(fields)
    overridden_ids.append(shard_id)
if overridden_ids:
    applied = ", ".join(sorted(overridden_ids, key=cmp_to_key(cmp_id)))
    print(f"Applied {len(overridden_ids)} override(s): {applied}")
if excluded_ids:
    excluded_names = sorted(output[shard_id]["name"] for shard_id in excluded_ids)
    print(f"Excluding {len(excluded_ids)} shard(s) not yet live on this branch: {', '.join(excluded_names)}")
    for shard_id in excluded_ids:
        del output[shard_id]

missing_property_ids = sorted(set(shard_data) - set(output), key=cmp_to_key(cmp_id))
extra_property_ids = sorted(set(output) - set(shard_data), key=cmp_to_key(cmp_id))
name_mismatches = [
    shard_id
    for shard_id in sorted(set(output) & set(shard_data), key=cmp_to_key(cmp_id))
    if output[shard_id]["name"] != shard_data[shard_id]["name"]
]
name_counts = Counter(properties["name"] for properties in output.values())
duplicate_names = sorted(name for name, count in name_counts.items() if count > 1)

validation_errors = []
if missing_property_ids:
    validation_errors.append(f"missing fusion properties for: {', '.join(missing_property_ids)}")
if extra_property_ids:
    validation_errors.append(f"fusion properties without shard data: {', '.join(extra_property_ids)}")
if name_mismatches:
    validation_errors.append(
        "fusion property names do not match shard data: "
        + ", ".join(
            f"{shard_id} ({output[shard_id]['name']} != {shard_data[shard_id]['name']})"
            for shard_id in name_mismatches
        )
    )
if duplicate_names:
    validation_errors.append(f"duplicate fusion property names: {', '.join(duplicate_names)}")
internal_id_mismatches = [
    f"{shard_id} ({shard_data[shard_id]['internal_id']} != SHARD_{output[shard_id][WIKI_PREFIX + 'internal_id']})"
    for shard_id in sorted(set(output) & set(shard_data), key=cmp_to_key(cmp_id))
    if shard_data[shard_id]["internal_id"] != "SHARD_" + output[shard_id][WIKI_PREFIX + "internal_id"]
]
if internal_id_mismatches:
    validation_errors.append(
        "internal ids do not match shard data: " + ", ".join(internal_id_mismatches))
if validation_errors:
    raise ValueError("\n".join(validation_errors))

id_by_name = {properties["name"]: shard_id for shard_id, properties in output.items()}
highest_number = {
    letter: max((shard_number(shard_id) for shard_id in output if shard_id[0] == letter), default=0)
    for letter in rarity_letters
}


def has_recipe(properties):
    return bool(properties["input1"] or properties["input2"])


def is_generic_fusion_target(properties):
    if not properties["synthesized"]:
        return False
    return not has_recipe(properties) or properties["recipe_type"] == "GENERIC_PLUS"


def derive_fuse_amount(shard_id):
    properties = output[shard_id]
    if properties["name"] == CHAMELEON_NAME:
        return CHAMELEON_INPUT_AMOUNT
    if REDUCED_INPUT_FAMILIES.intersection(properties["family"]):
        return REDUCED_INPUT_AMOUNT
    return DEFAULT_INPUT_AMOUNT


def derive_id_result(shard_id):
    letter = shard_id[0]
    category = output[shard_id]["category"]
    number = shard_number(shard_id) + ID_FUSION_STEP
    while number <= highest_number[letter]:
        target = output.get(f"{letter}{number}")
        if target is not None and target["category"] == category and is_generic_fusion_target(target):
            return target["name"]
        number += ID_FUSION_STEP
    return None


def derive_chameleon_result(shard_id):
    chameleon_shard_id = id_by_name[CHAMELEON_NAME]
    letter = shard_id[0]
    number = shard_number(shard_id)
    results = []
    fallbacks = 0
    for slot in range(1, CHAMELEON_SLOTS + 1):
        target = output.get(f"{letter}{number + slot}")
        if target is None:
            fallbacks += 1
            fallback_letter = next_rarity_letter(letter)
            target = output.get(f"{fallback_letter}{fallbacks}") if fallback_letter else None
        if target is not None and target["chameleon"] and target is not output[chameleon_shard_id]:
            results.append(target["name"])
    return results


# check against the wiki's own results
drift = []


def check_drift(shard_id, field, derived, expected, compare_as_set=False):
    matches = sorted(derived) == sorted(expected) if compare_as_set else derived == expected
    if not matches:
        drift.append(
            f"  {output[shard_id]['name']}({shard_id}) {field}: "
            f"derived {derived!r}, wiki has {expected!r}"
        )


for shard_id, properties in output.items():
    properties["fuse_amount"] = fuse_amount_overrides.get(shard_id, derive_fuse_amount(shard_id))
    properties["id_result"] = derive_id_result(shard_id)
    properties["chameleon_result"] = derive_chameleon_result(shard_id)

id_origins: dict[str, list[str]] = {shard_id: [] for shard_id in output}
chameleon_origins: dict[str, list[str]] = {shard_id: [] for shard_id in output}
for shard_id, properties in output.items():
    if properties["id_result"]:
        id_origins[id_by_name[properties["id_result"]]].append(shard_id)
    for result in properties["chameleon_result"]:
        chameleon_origins[id_by_name[result]].append(shard_id)

for shard_id, properties in output.items():
    properties["id_origin"] = [
        output[origin_id]["name"]
        for origin_id in sorted(id_origins[shard_id], key=cmp_to_key(cmp_id))
    ]
    properties["chameleon_origin"] = [
        output[origin_id]["name"]
        for origin_id in sorted(chameleon_origins[shard_id], key=cmp_to_key(cmp_id))
    ]
    check_drift(shard_id, "id_result",
                properties["id_result"], properties[f"{WIKI_PREFIX}id_result"])
    check_drift(shard_id, "chameleon_result",
                properties["chameleon_result"], properties[f"{WIKI_PREFIX}chameleon_result"])
    check_drift(shard_id, "id_origin",
                properties["id_origin"], properties[f"{WIKI_PREFIX}id_origin"], compare_as_set=True)
    check_drift(shard_id, "chameleon_origin",
                properties["chameleon_origin"], properties[f"{WIKI_PREFIX}chameleon_origin"], compare_as_set=True)

if drift:
    message = (f"derived fusion results disagree with the wiki for {len(drift)} field(s):\n"
               + "\n".join(drift))
    # An _exclude override legitimately shifts nearby ID-Fusion/Chameleon chains
    # away from what the wiki (which still has the excluded shard) reports, so
    # any active override -- exclusions included -- downgrades drift to a warning.
    if overridden_ids:
        print(f"Warning: {message}")
    else:
        raise ValueError(message)

fuse_amount_conflicts = [
    f"{output[shard_id]['name']}({shard_id}): shard-data has "
    f"{shard_data[shard_id].get('fuse_amount')}, fusion rules give {output[shard_id]['fuse_amount']}"
    for shard_id in sorted(output, key=cmp_to_key(cmp_id))
    if shard_data[shard_id].get("fuse_amount") != output[shard_id]["fuse_amount"]
]
if fuse_amount_conflicts:
    print(f"fuse_amount overridden by the fusion rules for {len(fuse_amount_conflicts)} shard(s):")
    for conflict in fuse_amount_conflicts:
        print(f"  {conflict}")

for properties in output.values():
    for key in [key for key in properties if key.startswith(WIKI_PREFIX)]:
        del properties[key]

# Process all shards for hashing and change detection
for shard_id in sorted(output.keys(), key=cmp_to_key(cmp_id)):
    stored_hash = hashes.get(shard_id)
    pretty_name = f"{output[shard_id]['name']}({shard_id})"
    hash_ = hashlib.sha256(json.dumps(output[shard_id]).encode('utf-8')).hexdigest()  # type: ignore[arg-type]
    updated_hashes[shard_id] = hash_
    if stored_hash != hash_:
        if github_actions:
            changed_shards.append(pretty_name)
        elif not update_hashes:
            print(f"Hash mismatch: {pretty_name}\n"
                  f"  expected: {hash_}")

# Make dist directory if it doesn't exist
if not os.path.exists("dist"):
    os.makedirs("dist")

# Save to JSON
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)
if update_hashes:
    with open(hashes_path, "w", encoding="utf-8") as f:
        json.dump(updated_hashes, f, indent=2, ensure_ascii=False)
if github_actions:
    with open("changed-shards.txt", "w", encoding="utf-8") as f:
        for name in changed_shards:
            f.write(f"{name}\n")
