# Kanji Heatmap Data

## Usage

### Requirements

Python 3.x (standard library only — no packages to install):

```bash
python --version
# Python 3.13.2
```

### Overrides

Edit the following files to specify the values you want to override:

```
kanji_parts.json
kanji_to_remove.json
kanji_vocab.json
keywords.json
component_keyword.json   # keywords for components / non-shipped kanji used in decompositions
vocab_furigana.json
vocab_meaning.json
japanese_study_words.json
```

#### Input Files

Download aggregated kanji information from [Kanji Data Releases][pika-data]

```bash
curl --output-dir input -OL https://github.com/PikaPikaGems/kanji-data-releases/releases/latest/download/kanji-data.tar.gz
tar -xzf ./input/kanji-data.tar.gz -C ./input/
```

Download the map of vocabulary to its components from [JMdict Furigana Map][pika-furi]

```bash
curl --output-dir input -OL https://github.com/PikaPikaGems/jmdict-furigana-map/releases/latest/download/jmdict-furigana-map.json.tar.gz
tar -xzf ./input/jmdict-furigana-map.json.tar.gz -C ./input/
```

Download and prepare the Simplified JMdict JSON file from [Jmdict Simplified][jmdict-simplified]

```
# if all words
curl --output-dir input -OL https://github.com/scriptin/jmdict-simplified/releases/download/3.6.1%2B20250324123350/jmdict-eng-3.6.1+20250324123350.json.tgz
tar -xzf ./input/jmdict-eng-3.6.1+20250324123350.json.tgz -C ./input/
mv input/jmdict-eng-3.6.1.json input/scriptin-jmdict-eng.json

# If common words only
curl --output-dir input -OL https://github.com/scriptin/jmdict-simplified/releases/download/3.6.1%2B20250324123350/jmdict-eng-common-3.6.1+20250324123350.json.tgz
tar -xzf ./input/jmdict-eng-common-3.6.1+20250324123350.json.tgz -C ./input/
mv input/jmdict-eng-common-3.6.1.json input/scriptin-jmdict-eng.json

```

Remove the files which you don't need anymore, to reduce clutter

```
rm ./input/kanji-data.tar.gz
rm ./input/jmdict-furigana-map.json.tar.gz

# depending on what you chose
rm ./input/jmdict-eng-common-3.6.1+20250324123350.json.tgz
rm ./input/jmdict-eng-3.6.1+20250324123350.json.tgz
```

This leaves the `input` directory with the following files:

```
cum_use.json
jmdict-furigana-map.json # From: JMdict Furigana Map
kanji_vocab.json
merged_kanji.json
missing_components.json
phonetic_components.json
scriptin-jmdict-eng.json # From: Jmdict Simplified
vocab_furigana.json      # legacy, no longer read (furigana comes from jmdict-furigana-map)
vocab_meaning.json
```

Note: Some scripts rely folders or files such as  `./raw/kanji-textbook-words/*.json` (`kanji-text-book-words-min/`) and `./raw/kanji-words/v3/*.json` (`v3b/`) .
These files come from the repos which may or may not be public as of writing:
- https://github.com/PikaPikaGems/textbook-japanese-words
- https://github.com/PikaPikaGems/japanese-word-ranks/
- https://github.com/PikaPikaGems/japanese-word-frequency-archive
- https://github.com/PikaPikaGems/jp-word-ranks-data


### Transform Data

```bash
# IMPORTANT: 
# populate  `./raw/kanji-textbook-words/*.json` and `./raw/kanji-words/v3/*.json`

# ----------------
# Transform Data Script
# ----------------

# See: notes/flowchart.md
./generate.sh

```

Or just the final build step:

```bash
python3 src/build_filtered_kanji_json.py   # if input/filtered_kanji.json is missing
python3 src/kanji_build_output_jsons.py
```

The following output files should be generated in the `output` directory:

- component_keyword.json
- cum_use.json
- kanji_extended.json
- kanji_main.json
- phonetic.json
- vocab_meaning.json
- vocab_furigana.json
- kanji_representative_words.json
- similar-kanjis.json
- extra_kanji_keyword.json   # keywords for non-shipped kanji that appear inside sample/study words

Additionally, the following files will be created by running the script above
in the `input` directory. This will not be part of the release file.

```
jmdict-vocab-meaning.json
```

### Inspect Data

```bash
./src/kanji_inspect.py

$ head -n 20 raw/kanji-textbook-words/v3/<KANJI>.json
$ head -n 20 raw/kanji-textbook-words/<KANJI>.json 
```

## Prepare release

See `RELEASE.md`

## License and Credits

The software is distributed under the [MIT License][mit-license].

The input data comes from:

1. Dmitry Shpika's [jmdict-simplified][jmdict-simplified] which project uses the [JMdict/EDICT][jmdict-edict] file, which is the property of the Electronic Dictionary Research and Development Group (https://www.edrdg.org/),
   and used in conformance with the Group's [license](https://www.edrdg.org/edrdg/licence.html).
2. [Kanji Data Releases][pika-data] and [JMdict Furigana Map][pika-furi],
   both under [CC BY-SA 4.0][cc-by-sa-4].
3. [Jiten Frequency](https://jiten.moe/other), [JPDB Frequency](https://github.com/Kuuuube/yomitan-dictionaries/blob/main/data/jpdbv2_kanji_frequency_2026-02-09.csv), [KKLC Order](https://github.com/vadasambar/kanji_order/blob/master/final_order.txt)
4. Kanji structure data used to generate similarity search can be found on /raw/structure-info/SOURCES.md.

### JMdict and JMnedict

The original XML files - **JMdict.xml**, **JMdict_e.xml**, **JMdict_e_examp.xml**,and **JMnedict.xml** -
are the property of the Electronic Dictionary Research and Development Group,
and are used in conformance with the Group's [license][EDRDG-license].
All derived files are distributed under the same license, as the original license requires it.

[mit-license]: https://github.com/PikaPikaGems/kanji-heatmap-data/blob/main/LICENSE
[cc-by-sa-4]: https://creativecommons.org/licenses/by-sa/4.0
[pika-data]: https://github.com/PikaPikaGems/kanji-data-releases
[pika-furi]: https://github.com/PikaPikaGems/jmdict-furigana-map
[EDRDG-license]: http://www.edrdg.org/edrdg/licence.html
[jmdict-edict]: https://www.edrdg.org/wiki/index.php/JMdict-EDICT_Dictionary_Project
[jmdict-simplified]: https://github.com/scriptin/jmdict-simplified
