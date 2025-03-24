# Publishing Releases

## Prepare archive file and version tag

After running the script to generate the output files, run the following:

```bash
./src/release.py <version>
```

where `<version>` is the chosen version number for the next release (e.g. v1.0.1, 2.0).

A new archive file, `kanji-heatmap-data.tar.gz`, should be created in the `releases` directory.
This contains the output files from `output` directory.

Verify that the chosen version number has been created locally and in remote.

```bash
git tag
git ls-remote --tags origin
```

You can also check the tags in GitHub [here][gh-tags].

## Publish in GitHub

Go to [Releases][gh-releases] and create a new release.

1. Select the version tag from the dropdown.
2. Release title: kanji-heatmap-data `<version>`
3. Add any notable changes in the Description.
4. Publish release

[gh-releases]: https://github.com/PikaPikaGems/kanji-heatmap-data/releases
[gh-tags]: https://github.com/PikaPikaGems/kanji-heatmap-data/tags
