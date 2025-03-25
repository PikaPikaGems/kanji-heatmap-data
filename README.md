# Kanji Heatmap Data

## Usage

### Requirements

Python 3.x:

```bash
python --version
# Python 3.13.2
```

#### Input Files

```bash
curl --output-dir input -OL https://github.com/PikaPikaGems/jmdict-furigana-map/releases/latest/download/jmdict-furigana-map.json.tar.gz
tar -xzf ./input/jmdict-furigana-map.json.tar.gz -C ./input/

curl --output-dir input -OL https://github.com/PikaPikaGems/kanji-data-releases/releases/latest/download/kanji-data.tar.gz
tar -xzf ./input/kanji-data.tar.gz -C ./input/
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

## License

The software is distributed under the [MIT License][mit-license].

The input data comes from [Kanji Data Releases][pika-data] and [JMdict Furigana Map][pika-furi],
both under [CC BY-SA 4.0][cc-by-sa-4].

[mit-license]: https://github.com/PikaPikaGems/kanji-heatmap-data/blob/main/LICENSE
[cc-by-sa-4]: https://creativecommons.org/licenses/by-sa/4.0
[pika-data]: https://github.com/PikaPikaGems/kanji-data-releases
[pika-furi]: https://github.com/PikaPikaGems/jmdict-furigana-map
