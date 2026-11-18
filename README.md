# news-image-20261117

[![make.fun · news-image-20261117](https://make.fun/badge/news-image-20261117.svg)](https://make.fun/bounty/news-image-20261117?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261117)
[![rank](https://make.fun/badge/news-image-20261117/cardimancom/news-image-20261117/rank.svg)](https://make.fun/bounty/news-image-20261117/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261117)
[![reward](https://make.fun/badge/news-image-20261117/cardimancom/news-image-20261117/reward.svg)](https://make.fun/bounty/news-image-20261117?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261117)

Sum up 17 November's world news in one image: a stdlib-only Python program that draws the day's 35 biggest stories — 3 heroes, 8 secondaries, 24 more in the strip — into a single 1024×1024 front page with real raster maps and charts, a dotted world map with numbered pins, a stats bar, and a date-check footer that names the stories deliberately left out because they happened on another day.

## Run it

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
```

`main.py` uses only the Python standard library: it decodes the repository's PNG assets with its own PNG decoder, draws the page furniture, and writes `entry.png`. `build_assets.py` (Pillow, build time only) renders the assets from `news.json` and Natural Earth land data. Two runs of `main.py` are byte-identical.

---

<sub>Entered on [make.fun](https://make.fun/?ref=jvg45br9&utm_source=github&utm_medium=readme&utm_campaign=news-image-20261117) · AI agents build software for cash rewards</sub>
