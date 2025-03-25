# Kanji Heatmap Data

## Usage

### Requirements

Python 3.x:

```bash
python --version
# Python 3.13.2
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

Download and prepare the the Simplified JMdict JSON file

```
curl --output-dir input -OL https://github.com/scriptin/jmdict-simplified/releases/download/3.6.1%2B20250324123350/jmdict-eng-common-3.6.1+20250324123350.json.tgz
tar -xzf ./input/jmdict-eng-common-3.6.1+20250324123350.json.tgz -C ./input/
mv input/jmdict-eng-common-3.6.1.json input/scriptin-jmdict-eng-common.json

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
- vocabulary.json

## License and Credits

The software is distributed under the [MIT License][mit-license].

The input data comes from:

1. Dmitry Shpika's [jmdict-simplified](https://github.com/scriptin/jmdict-simplified) which project uses the [JMdict/EDICT][jmdict-edict] file, which is the property of the Electronic Dictionary Research and Development Group (https://www.edrdg.org/),
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
