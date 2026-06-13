# Question 

# 1
Something wrong with flowchart.md
it says here: %% intermediate overrides (algo-written)
Not all are algo-written. only those with the suffix -algo.json are algo written. The rest are written manually which takes priority over the algo-written ones. 

# 2
Doesnt keyword_sources.py have a lot of overlap with algorithmic_overrides_keyword.py ? and need 
deduplication?

# TODOs

1. better similar-kanji algorithm given new raw input files 
2. sort build_filter_kanji.json based on frequency data. (We have many frequency sources, how do we go about it? weighted average or something?)

## Note

['亘', '亦', '允', '勺', '孟', '甫']: are these in sample words?
No. Those are component parts (kanji decomposition) of shipped kanji that lack a keyword — a different thing from sample words. 亘/亦/允/孟/甫 were already keyword-less before any of my changes (pre-existing). Only 勺 is a regression I introduced — it's a component of 的/約/釣/酌,

The 35 unsourceable kanji are the open item — they'd need an external kanji dictionary (kanjidic2) or the upstream merged_kanji to include them. 


The non-shipped kanji come from 86 sample-word and 19 study-word assignments. They split into two groups:

Perfectly good everyday words — the target kanji's best example just happens to pair with a kanji you don't ship:

玉葱 (onion) for 玉 · 胃癌/肺癌 (cancer) for 胃/肺 · 綿飴 (cotton candy) for 綿 · 麻痺 (paralysis) for 麻 · 札幌 (Sapporo) for 札 · 靴紐 (shoelace) for 靴 · 胡椒 (pepper) for 胡 · 孔雀 (peacock) for 孔 · 椎茸 (shiitake) for 椎 · 栗鼠 (squirrel) for 栗
Genuinely poor picks — ateji, names, or obscure forms:

墨西哥 (Mexico, ateji) for 墨 · 袁彦道 (a name) for 彦 · 箆蝶鮫 for 蝶 · 玉蜀黍 (corn, rare spelling) for 玉 · 矢鱈 for 矢 · 弥勒 (Maitreya) for 弥


# Resolve Notes

TODO: Need to inspect this (they say they have words with no meaning)
亦佑凜匡卿哉峻巌巽恕悌惟慧昴柊柾栞楓槍槻欽渚澪燎燦眸碩穣紬絃綸翠胤莞菫葵蔦蕉裟誼諄諒輔頌馨魁鵬麟麿黛


## Investigating 

##  Kanji where rare words were chosen as study (remove some and replace some and some leave as is)

# Rare Words 
康 → 健康
誉 → 誉める
衡 → 均衡 
貌 → 変貌
款 → 定款
帥 → 総帥
泌 → 分泌
穣 → 豊穣
昂 → 昂ぶる
叡 → 叡智
爵 → 叡智
阜 → 岐阜

亘楷  (remove)
Remove 亮郁玲槻榛惟渥毬笙椋莞耶衿勁勁璽坐


## 5 character words 
則 → 則る
慄 → 戦慄する,戦慄

## 4 character words 
猟 → 狩猟
朗 → 朗らか
娠 → 妊娠

晃 → 晃 (remove? more common in names) 
耀 → (remove? very uncommon)


## No-word kanji (4): 牲肪蓉裟

牲 → 犠牲
肪 → 脂肪
蓉 (remove)
裟 (remove)

## Thinking of removing (Kanji whose study word does NOT start with it (40))

tier one
耀 shimering
勺 spoon full of fluid
誼 familiarity
悌 respect for elders
誼 familiarity
恕 sensitive
麟 camelopard

tier two 
蕉 banana
佑 adjutant
瑚 coral reef
憬 long for
錮 weld


tier three
迭 alternate



## Manual Inspection Notes
COMMON 👽 健康?→ 康 → 康二 (こうじ) [🦉] Health, ease, peace; comfort and well-being
COMMON 👽 誉める is more common, 誉れ → 誉 → 誉れ (ほまれ) [🦉] honour, reputation, glory
COMMON 👽 均衡 40 entries in nadeshiko OR → 衡 → 衡 (くびき) [🦉] yoke
👽 use 変貌 because more common, 12 items → 貌 → 貌 (かお) [🦉] face, visage
👽 定款 (article of incorporation, found in nadeshiko just two items ) → 款 → 款 (かん) [🦉] title, heading, article
👽 総帥 32 items , 元帥 → 帥 → 帥 (そち) [🦉] director of the Dazaifu
👽 35 items 分泌 → 泌 → 泌尿 (ひにょう) [🦉] urination
👽 豊穣 <- yields 7 results on nadeshiko→ 穣 → 穣 (じょう) [🦉] 10^28, ten octillion
👽 25 items → more common spelling 昂ぶる → 昂 → 昂る (たかぶる) [🦉] to become aroused (of emotions, nerves, etc.), to become excited, to become stirred up
👽 54 items 叡智 this is more common → 叡 → 叡山 (えいざん) [🦉] Wise, sagacious; imperial wisdom; used in reference to emperors
👽 10 items a fairly common kanji, better word: 爵位→ 爵 → 爵 (しゃく) [🦉] jue (ancient 3-legged Chinese wine pitcher, usu. made of bronze)
👽 岐阜 8 items Gifu Prefecture (Chūbu region) is more common → 阜 → 阜 (つかさ) [🦉] mound, hill

  ✅  139 items in jpdb→ 玲 → 玲瓏 (れいろう) [🦉] clear, translucent, brilliant
  COMMON ✅ → 涯 → 涯 (はて) [🦉] horizon
  ✅ → 鵬 → 鵬 (おおとり) [🦉] peng (giant bird said to transform from a fish)
  ✅ 145 words on jpdb 綜合 → 綜 → 綜合 (そうごう) [🦉] synthesis, combination, integration
  ✅ Only 27 times found in JPDB.io  → 啄 → 啄木 (たくぼく) [🦉] woodpecker
  ✅ 10 results in nadeshiko → 匁 → 匁 (もんめ) [🦉] monme (unit of weight, 3.75 g)
  ✅ 125 words on jpdb → 虞 → 虞 (おそれ) [🦉] risk, fears
  ✅ 48 words on jpdb → 冶 → 冶金 (やきん) [🦉] metallurgy
  ✅ used in 644 entries in jpdb  → 凜 → 凜 (りん) [🦉] cold, frigid, bracing

  

  🤥 10 items nadeshiko proper noun → 亮 → 亮一 (りょういち) [🦉] Bright, clear, luminous; intelligent; to illuminate or clarify
  🤥 40 items nadeshiko, proper noun → 郁 → 郁子 (むべ) [🦉] Japanese staunton-vine (Stauntonia hexaphylla)
  🤥 proper noun → 孟 → 孟録 (まんろく) [🦉] First, eldest; the beginning of a season; used in classical names (Mencius)
  🤥 47 items more common in proper nouns → 毬 → 毬 (かさ) [🦉] ball (for sport, games, etc.)
  🤥 41 items more common in proper nouns → 椋 → 椋 (むくのき) [🦉] Aphananthe oriental elm (Aphananthe aspera), mukutree
  🤥 15 items More common in names → 耶 → 耶律 (やりつ) [🦉] Question particle (classical); used to transcribe foreign sounds; father (archaic)
  🤥 玲 50 entries
   🚩 →  座る is more common 坐 → 坐る (すわる) [🦉] to sit, to squat
   🚩 more common spelling 渡る → 亘 → 亘る (わたる) [🦉] [vi] extend over / for, range, span, last
  ❓ (it's a plant species) → 槻 → 槻 (けやき) [🦉] Japanese zelkova (Zelkova serrata)
  ❓ asian hazel → 榛 → 榛 (はしばみ) [🦉] Asian hazel (Corylus heterophylla var. thunbergii), Siberian hazel
  ❓ very rare kanji, very rare word 惟神, previously used for "kore, this"  → 惟 → 惟 (これ) [🦉] this, this one
  ❓ rare, used in 15, in JPDB.io → 渥 → 渥美 (あつみ) [🦉] Moist, wet; grace, favor; generous; rich (of color or liquid)
  ❓Japanese wind pipe → 笙 → 笙 (しょう) [🦉] traditional Japanese wind instrument resembling panpipes, free-reed instrument used in Japanese court music
  ❓ Not common → 莞 → 莞 (ふとい) [🦉] softstem bulrush (Scirpus tabernaemontani)
  ❓ Used in 1 in nadeshiko, 148 in jpdb → 捺 → 捺印 (なついん) [🦉] affixing a seal (to), putting one's seal (on)
  ❓ not common kanji, used in 83 wors in jpd→ 絃 → 絃 (つる) [🦉] bowstring
  ❓ uncommon kanji → 衿 → 衿子 (えりこ) [🦉] Collar, lapel of a garment; variant of 襟; used in names for elegance
  ❓ most commonly spelled in hiragana → 亦 → 亦 (また) [🦉] Again
  ❓ 9 used in legal documents→ 玖 → 玖 (きゅう) [🦉] nine, 9
  ❓ uncommon word → 梧 → 梧桐 (あおぎり) [🦉] Chinese parasol-tree (Firmiana simplex), Chinese-bottletree, Japanese varnishtree
  ❓ very uncommon → 勁 → 勁草 (けいそう) [🦉] wind-resistant blade of grass, resistant idea (metaphorically)
  ❓ not very common→ 璽 → 璽 (じ) [🦉] emperor's seal
  ❓ not common→ 楷 → 楷書 (かいしょ) [🦉] square / block Chinese character style [used in writing or printing]


## 5 or more kanji revealed an algorithm bug  

- 乞 → 乞い願わくは  ? why not 乞う (more common) or 乞食
- 刷 → 刷り上げる ? why not 刷り込む ? 
- 則 → 則を越える ? why not 則る ?
- 芳 → 芳しくない ? why not 芳しい ?
- 蔑 → 蔑ろにする ? why not 蔑む or 蔑ろ ?
- 慄 → 慄然とする ? why not 戦慄 ?

the algorithm should be if they're both in the v3 and textbook then the word gets whichever has the higher tag


# Output
-----------
 Kanji processed:   2386
  With word:         2382
  Without word:      4
  No meaning:        0
  No reading:        0

  Tag / source breakdown
    🌱  v3: 746  (31.3%)
    ☘️  v3: 588  (24.7%)
    🌷  v3: 555  (23.3%)
    📖  textbook: 341  (14.3%)
    📚  v3: 114  (4.8%)
    🤔  unknown: 0  (0.0%)  
    🦉  v3: 38  (1.6%)  康涯鵬亮衡款郁玲槻帥泌孟綜榛惟渥毬啄穣笙匁椋昂叡莞耶捺絃衿凜玖梧勁阜璽貌璧坐
  康 → 康二 (こうじ) [🦉] Health, ease, peace; comfort and well-being
  涯 → 涯 (はて) [🦉] horizon
  鵬 → 鵬 (おおとり) [🦉] peng (giant bird said to transform from a fish)
  🚩 亮 → 亮一 (りょういち) [🦉] Bright, clear, luminous; intelligent; to illuminate or clarify
  衡 → 衡 (くびき) [🦉] yoke
  款 → 款 (かん) [🦉] title, heading, article
  🚩 郁 → 郁子 (むべ) [🦉] Japanese staunton-vine (Stauntonia hexaphylla)
  🚩 玲 → 玲瓏 (れいろう) [🦉] clear, translucent, brilliant
  🚩 槻 → 槻 (けやき) [🦉] Japanese zelkova (Zelkova serrata)
  帥 → 帥 (そち) [🦉] director of the Dazaifu
  泌 → 泌尿 (ひにょう) [🦉] urination
  🚩 孟 → 孟録 (まんろく) [🦉] First, eldest; the beginning of a season; used in classical names (Mencius)
  綜 → 綜合 (そうごう) [🦉] synthesis, combination, integration
  🚩 榛 → 榛 (はしばみ) [🦉] Asian hazel (Corylus heterophylla var. thunbergii), Siberian hazel
  🚩 惟 → 惟 (これ) [🦉] this, this one
  🚩 渥 → 渥美 (あつみ) [🦉] Moist, wet; grace, favor; generous; rich (of color or liquid)
  🚩 毬 → 毬 (かさ) [🦉] ball (for sport, games, etc.)
  啄 → 啄木 (たくぼく) [🦉] woodpecker
  穣 → 穣 (じょう) [🦉] 10^28, ten octillion
  🚩 笙 → 笙 (しょう) [🦉] traditional Japanese wind instrument resembling panpipes, free-reed instrument used in Japanese court music
  匁 → 匁 (もんめ) [🦉] monme (unit of weight, 3.75 g)
  🚩 椋 → 椋 (むくのき) [🦉] Aphananthe oriental elm (Aphananthe aspera), mukutree
  昂 → 昂る (たかぶる) [🦉] to become aroused (of emotions, nerves, etc.), to become excited, to become stirred up
  叡 → 叡山 (えいざん) [🦉] Wise, sagacious; imperial wisdom; used in reference to emperors
  🚩 莞 → 莞 (ふとい) [🦉] softstem bulrush (Scirpus tabernaemontani)
  🚩 耶 → 耶律 (やりつ) [🦉] Question particle (classical); used to transcribe foreign sounds; father (archaic)
  捺 → 捺印 (なついん) [🦉] affixing a seal (to), putting one's seal (on)
  絃 → 絃 (つる) [🦉] bowstring
  🚩衿 → 衿子 (えりこ) [🦉] Collar, lapel of a garment; variant of 襟; used in names for elegance
  凜 → 凜 (りん) [🦉] cold, frigid, bracing
  玖 → 玖 (きゅう) [🦉] nine, 9
  🚩 梧 → 梧桐 (あおぎり) [🦉] Chinese parasol-tree (Firmiana simplex), Chinese-bottletree, Japanese varnishtree
  🚩 勁 → 勁草 (けいそう) [🦉] wind-resistant blade of grass, resistant idea (metaphorically)
  阜 → 阜 (つかさ) [🦉] mound, hill
  🚩 璽 → 璽 (じ) [🦉] emperor's seal
  貌 → 貌 (かお) [🦉] face, visage
  璧 → 璧 (へき) [🦉] ball, sphere, globe
  🚩 坐 → 坐る (すわる) [🦉] to sit, to squat

  Word length
    1 chars: 950  (39.9%)
    2 chars: 1225  (51.4%)
    3 chars: 187  (7.9%)
    4 chars: 14  (0.6%)  亡片柔朗繰懐娠晃猟囚凸耀拶羨

  亡 → 亡くなる (なくなる) [🌱] [vi] die, pass away, breathe one’s last
  片 → 片づける (かたづける) [☘️] to put in order, to tidy up, to clean up
  柔 → 柔らかい (やわらかい) [☘️] soft
  繰 → 繰り返す (くりかえす) [☘️] repeat, do over again
  懐 → 懐かしい (なつかしい) [☘️] dear, beloved; long for, miss
  羨 → 羨ましい (うらやましい) [☘️] envious, jealous; enviable
  囚 → 囚われる (とらわれる) [🌷] to be caught, to be captured, to be taken prisoner
  朗 → 朗らかな (ほがらかな) [📖] cheerful, bright
  娠 → 妊娠する (にんしんする) [📖] become pregnant, conceive
  晃 → 晃晃たる (こうこう煌煌たる) [📖] brilliant, bright, dazzling
  猟 → 猟をする (りょうをする) [📖] hunt, shoot
  凸 → 凸レンズ (とつレンズ) [📖] convex lens
  耀 → 眩耀する (げんようする) [📖] shine dazzlingly
  拶 → 挨拶する (あいさつする) [📖] greet, salute, present one's compliments

    5 chars: 6  (0.3%)  則召恥盛駆慄
  恥 → 恥ずかしい (はずかしい) [🌱] shy; ashamed; shameful
  召 → 召し上がる (めしあがる) [☘️] [vt] eat, drink
  盛 → 盛り上がる (もりあがる) [☘️] [vi] rise, swell; rouse, become excited
  駆 → 駆けつける (かけつける) [☘️] to run to, to come running, to rush (someplace)
  則 → 則を越える (のりをこえる) [📖] violate the laws of nature
  慄 → 慄然とする (りつぜんとする) [📖] to be filled with horror, to be horrified


  Kanji per word
    1 kanji: 1614  (67.8%)
    2 kanji: 766  (32.2%)
    3 kanji: 2  (0.1%)  雰莉

  雰 → 雰囲気 (ふんいき) [📚] atmosphere, mood, ambiance
  莉 → 茉莉花 (まつりか) [📚] jasmine flower
────────────────────────────────────────────

No-word kanji (4): 牲肪蓉裟

No meaning kanji (0): 

  Words starting with kanji:     2342
  Words NOT starting with kanji: 40

Kanji whose study word does NOT start with it (40):
  械績膚覧慮訟祉壌酬践娠穫轄迭剖蕉痢佑耀悌勺瑚璃誼莉耗恕麟汰賂粧拶戚蔽侶惧憬摯瘍錮
  械 → 機械 (きかい) [📖] machine
  績 → 成績 (せいせき) [📖] grades (school)
  膚 → 皮膚 (ひふ) [📖] skin
  覧 → 閲覧 (えつらん) [📖] する：to peruse, to inspect, to read
  慮 → 遠慮 (えんりょ) [📖] reserve, refraining
  訟 → 訴訟 (そしょう) [📖] lawsuit
  祉 → 福祉 (ふくし) [📖] welfare, well-being
  壌 → 土壌 (どじょう) [📖] soil
  酬 → 報酬 (ほうしゅう) [📖] a reward, remuneration, a fee
  践 → 実践 (じっせん) [📖] する：to put into practice
  娠 → 妊娠する (にんしんする) [📖] become pregnant, conceive
  穫 → 収穫 (しゅうかく) [📖] する：to harvest, to reap
  轄 → 管轄 (かんかつ) [📖] control, jurisdiction
  迭 → 更迭 (こうてつ) [📖] する：to make a switch (in the Cabinet, etc.)
  剖 → 解剖 (かいぼう) [📖] する：to perform an autopsy, to dissect
  痢 → 下痢 (げり) [📖] diarrhoea
  耀 → 眩耀する (げんようする) [📖] shine dazzlingly
  勺 → 一勺 (いっしゃく) [📖] 1 shaku (⅒ of a go 合)
  璃 → 玻璃 (はり) [📖] crystal; glass
  耗 → 消耗 (しょうもう) [📖] する：to consume [exhaust] (energy)
  汰 → 淘汰 (とうた) [📖] する：to select, to weed out, to screen, to sift
  賂 → 賄賂 (わいろ) [📖] bribe, corruption
  粧 → 化粧 (けしょう) [📖] する：to makeup, to put on make-up
  拶 → 挨拶する (あいさつする) [📖] greet, salute, present one's compliments
  戚 → 親戚 (しんせき) [📖] relatives
  蔽 → 隠蔽 (いんぺい) [📖] する：to hide, to conceal, to cover up
  侶 → 僧侶 (そうりょ) [📖] (Buddhist) priest, bonze, monk
  惧 → 危惧 (きぐ) [📖] する：to feel misgivings about, to be apprehensive about
  憬 → 憧憬 (しょうけい) [📖] する：to yearn
  摯 → 真摯な (しんしな) [📖] sincere
  瘍 → 腫瘍 (しゅよう) [📖] tumour
  錮 → 禁錮 (きんこ) [📖] imprisonment
  蕉 → 芭蕉 (ばしょう) [📚] banana plant; Japanese plantain
  佑 → 天佑 (てんゆう) [📚] divine blessing, providence, heavenly protection
  悌 → 孝悌 (こうてい) [📚] filial piety and fraternal love
  瑚 → 珊瑚 (さんご) [📚] coral
  誼 → 交誼 (こうぎ) [📚] friendship, goodwill, friendly relations
  莉 → 茉莉花 (まつりか) [📚] jasmine flower
  恕 → 寛恕 (かんじょ) [📚] forgiveness, leniency, pardon
  麟 → 麒麟 (きりん) [📚] giraffe; qilin (mythical creature)
