# SkyShards Parser
This is a fork of the SkyShards Parser that formats and splits recipe data into multiple files for use on the [Hypixel SkyBlock Wiki](https://hypixelskyblock.minecraft.wiki).

Running `format-fusions.py` will create individual recipe files for each shard in `dist/fusion data`.

---

### Python script to algorithmically generate all possible recipes based on info from the wiki

Fusion rules and per-shard data come from the admin-published [Attribute Fusion](https://hypixelskyblock.minecraft.wiki/w/User:Wiki_Editor_33/AttributeFusion) page

## Steps
1. Run `scrape-wiki.py` to pull the official data into `fusion-properties.json`
2. Adjust `override-fusion-properties.json` if the game disagrees with the wiki (see below)
3. Run `build-properties.py`
4. This will generate `dist/fusion-properties.json` with `fuse_amount`, `id_result`,
   `chameleon_result` and the origin lists derived from the official fusion rules
5. Run `find-all-recipes.py` which will generate `dist/fusion-recipes.json` of all possible
   fusions based on the rules of fusion and wiki data
6. Run `format-fusions.py` to format the data in a way that's easier to be used
7. This will create `dist/fusion-data.json` which is used by [SkyShards](https://skyshards.com)

`scrape-wiki.py --from-file <path>` parses a saved copy of the raw wikitext instead of
fetching, which keeps runs reproducible while debugging.

## Derived vs. scraped
`fusion-properties.json` stores the per-shard facts the fusion rules need — `synthesized`,
`chameleon` and `recipe_type` — alongside the recipe inputs. The fusion *results* are not
trusted from the wiki: `build-properties.py` recomputes `id_result` and `chameleon_result`
from those flags and then asserts they match the results the wiki publishes, so any drift
between our implementation and the official data fails the build. The scraped results are
kept in the `_wiki_`-prefixed fields for exactly that check and stripped before output.

## Overrides
`override-fusion-properties.json` holds hand-maintained corrections applied on top of the
scraped data, for when the game disagrees with the wiki or the wiki lags behind an update.
Entries are partial patches keyed by shard id; keys starting with `_` are ignored, so
`_name` is free to use as a label:

```json
{ "R43": { "_name": "Ladybug", "input1": "Earthworm Shard" } }
```

While any override is present the wiki drift assertions report as warnings rather than
failing the build, since an override is expected to move results away from the wiki.
