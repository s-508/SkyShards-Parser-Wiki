import json
from collections import defaultdict
import re

# for sorting fusion recipes
prefix_order = {'C': 0, 'U': 1, 'R': 2, 'E': 3, 'L': 4}
def parse_component(component):
    match = re.match(r'([A-Z])(\d+)(?:-(\d+))?$', component)
    if match:
        prefix, number, suffix = match.groups()
        return prefix_order.get(prefix, 999), int(number), int(suffix) if suffix else 0
    return 999, 999, 999

# Returns fusion type based on recipe
def get_fusion_type(left_name, right_name, output_count):
    if output_count == 2:
        return "Special"
    if left_name == "Chameleon Shard" or right_name == "Chameleon Shard":
        return "Chameleon"
    return "ID"

# load recipe data
with open('dist/fusion-recipes.json', 'r') as f:
    data = json.load(f)

# load shard data
with open('shard-data.json', 'r') as f:
    shards = json.load(f)

# recipes each shard is used in as an input
# { "C1": [...], "C2": [...], etc. }
input_recipes = defaultdict(list)
# recipes each shard is an output from
output_recipes = defaultdict(list)

# get recipe lists
for input_combo, results in data['recipes'].items():
    inputs = input_combo.split('+') # 'C1+C2' --> ['C1', 'C2']

    left_shard = shards['shards'][inputs[0]]
    right_shard = shards['shards'][inputs[1]]

    # iterate through each result of the fusion
    for result in results:
        result_id = result['id']

        output_shard = shards['shards'][result_id]

        # recipe data
        recipe = {
            "left_name": left_shard['name'] + " Shard",
            "left_count": left_shard['fuse_amount'], # shards required for fusion
            "left_skyblock_id": left_shard['internal_id'],

            "right_name": right_shard['name'] + " Shard",
            "right_count": right_shard['fuse_amount'], # shards required for fusion
            "right_skyblock_id": right_shard['internal_id'],

            "output_name": output_shard['name'] + " Shard",
            "output_count": result['count'], # shards produced

            "fusion_type": get_fusion_type( # ID, Special, or Chameleon
                left_shard['name'] + " Shard",
                right_shard['name'] + " Shard",
                result['count']
            ),
        }

        input_recipes[inputs[0]].append(recipe)
        output_recipes[result_id].append(recipe)

# TODO: sort dictionaries

# maps input recipe to list
def map_input_recipe(recipe):
    return {
        "fusion_type": recipe['fusion_type'],

        # left shard data is implied

        "right_name": recipe['right_name'],
        "right_count": recipe['right_count'],
        "right_skyblock_id": recipe['right_skyblock_id'],

        "output_name": recipe['output_name'],
        "output_count": recipe['output_count']
    }

# maps output recipe to list
def map_output_recipe(recipe):
    return {
        "fusion_type": recipe['fusion_type'],

        "left_name": recipe['left_name'],
        "left_count": recipe['left_count'],
        "left_skyblock_id": recipe['left_skyblock_id'],

        "right_name": recipe['right_name'],
        "right_count": recipe['right_count'],
        "right_skyblock_id": recipe['right_skyblock_id'],

        # output shard name is implied
        "output_count": recipe['output_count']
    }

# split recipe data into individual JSON files
for shard_id in input_recipes.keys():
    shard_data = shards['shards'][shard_id]
    shard_name = shard_data['name'] + " Shard"

    out = {
        "name": shard_name,
        "fusion_required": shard_data['fuse_amount'],
        "skyblock_id": shard_data['internal_id'],
        
        "input_recipes": list(map(map_input_recipe, input_recipes[shard_id])),
        "output_recipes": list(map(map_output_recipe, output_recipes[shard_id])),
    }

    # write JSON to file
    with open(f'dist/fusion data/{shard_name}.json', 'w') as f:
        f.write(json.dumps(out, indent=2))