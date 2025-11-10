# Kanji Heatmap Data

## Usage

### Requirements

Python 3.x:

```bash
python --version
# Python 3.13.2
```

### Overrides

Edit the following files to specify the values you want to override:

```
kanji_parts.json
kanji_vocab.json
keywords.json
vocab_furigana.json
vocab_meaning.json
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
vocab_furigana.json
vocab_meaning.json
```

### Transform Data

```bash
./src/kanji_build_output_jsons.py
```

The following output files should be generated in the `output` directory:

- component_keyword.json
- cum_use.json
- kanji_extended.json
- kanji_main.json
- phonetic.json
- vocabulary_meaning.json
- vocabulary_furigana.json

Additionally, the following files will be created by running the script above
in the `input` directory. This will not be part of the release file.

```
jmdict-vocab-meaning.json
```

### Inspect Data

```bash
./src/kanji_inspect.py
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
