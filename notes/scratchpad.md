# 1
I think there is something wrong with your algorithm
花 → 貨 靴 芯 華 苗 芳 芹 苦 著 蔦

In your algorithm ou should take into consideration that when it is the main component 
for example: these  椛 糀 硴 geniunely look more like 花 than the ones you picked, because
 花 is inside 椛 on the left side for example. 

# 2

 I geniunely want to bring back: 斐 because I did a quick check, it's really quite common 不甲斐 and 甲斐. and for 裟..  大袈裟 seems to be quite common.... 

# 3
So a fair "genuinely good everyday word" count is ~35... That's still a lot!
How many are 🌱 and ☘️ ?

# 4 
> But because all-shipped is the absolute first key, it sometimes picks a worse all-shipped word over a good unshipped one

This is really bad though. I don't want to pick a worse word. 

Two questions
1. Are there candidate kanjis that we can remove instead to minimize this problem? 
2. Can you claude just handpick better word for these kanji? what are all the kanji affected by this anyway? 




study assignments : 19
sample assignments: 86
TOTAL             : 105
non-shipped occurrences by source: {'external': 100, 'removed': 9}
distinct REMOVED kanji pulled in (5) — candidates to bring back: 惇憬斐蓉裟
distinct EXTERNAL kanji pulled in (75) — no data, can't ship: 倆凰剌勒哈哥嘩堡壷寇峨幌幟怯悧愍托掣撰斯柑桔桶椒汀汲洒洩淘渟濘瀚爛狡狽猾玻瓜瓢痺瘤癌盒瞞箆紐芭茸葱蒙蔭薹藁藪蘇蜀蟻袁袱覯訥贖雀韮飴餡饉駕鮫鱈鱒鱮鴨黍鼠


# Question 

# 1
Something wrong with flowchart.md
it says here: %% intermediate overrides (algo-written)
Not all are algo-written. only those with the suffix -algo.json are algo written. The rest are written manually which takes priority over the algo-written ones. 

# 2
Doesnt keyword_sources.py have a lot of overlap with algorithmic_overrides_keyword.py ? and need 
deduplication?

# 3

Why are there many changes in keywords-algo.json 

# 4
On sort build_filtered_kanji_json.py based on frequency data. (We have many frequency sources, how do we go about it? weighted average or something?)

Note

```
    jiten_frequency = kanji_load.load_jiten_frequency()
    jpdb_frequency = kanji_load.load_jpdb_frequency()
    for kanji in kanji_data.keys():
      kanji_extract.get_ranks(kanji_info, NO_NUM_DATA, jiten_frequency, jpdb_frequency),
```

# 5

please better similar-kanji algorithm given new raw input files 
modify build_similar_kanjis.py given the files in raw/structure-info/* folder and also raw/kanji_components.txt

# 6 

You mentioned that 

> The non-shipped kanji come from 86 sample-word and 19 study-word assignments. They split into two groups: 1. Perfectly good everyday words — the target kanji's best example just happens to pair with a kanji you don't ship:  2. Genuinely poor picks — ateji, names, or obscure form

Given this
1. How many kanji in kanji_to_remove.json do you think should we bring back?
2. Should we remove even more kanjis? 
3. We should print these 19 study-word and 86 sample word so we can manually inspect
4. Should we tweak the algorithm more to reduce these? 
5. How many of the 105 sample vocabulary are good everyday words and how many are geniunely poor picks? what are they? 

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

# About unknown kanji 

The single most important number: 100 of the 105 non-shipped partners are [external] kanji — characters not in merged_kanji.json at all (癌 飴 葱 痺 鼠 …). Those were never shippable; no amount of editing kanji_to_remove.json brings them back. Only 9 occurrences across 5 distinct removed kanji are [removed]: 惇 憬 斐 蓉 裟. 

1. How many to bring back? Essentially 0–2. Only those 5 removed kanji appear in any example word, and most aren't good standalone ship candidates:

斐 — defensible: 甲斐 (かい, "worth", as in 生き甲斐/やり甲斐) is genuinely common.
憬 — borderline: only 憧憬 (yearning).
惇 (惇睦, a name), 蓉 (芙蓉, a flower), 裟 (袈裟, monk's stole) — not worth shipping standalone.
But the cleaner fix isn't bring-back — it's picking a different example word (see #4 below). E.g. 甲 doesn't need 甲斐; it has 甲乙/装甲/甲板 (all shipped).

2. Remove more? A cluster of target kanji are themselves rare and have no everyday word that avoids an external partner: 芙(芙蓉), 袈(袈裟), 嵯(嵯峨), 璃(玻璃), 蕉(芭蕉), 怜(怜悧), 絢(絢爛), 爾 (伯剌西爾=Brazil, 哈爾浜=Harbin — both ateji!), 倭(倭寇). These are removal candidates — but only if they're outside your must-ship target set; I won't remove without your say.

4. Tweak the algorithm? Yes — this is the highest-leverage lever. Add an "all-shipped" preference: penalize candidate words containing a non-shipped kanji in both the sample- and study-word scoring. That would clear most of the 86 (玉→玉葱 has 水玉/目玉; 胃/肺→癌 have alternatives; 麻→麻痺 could be 麻薬/麻酔). Irreducible residue ≈ the ~10–15 kanji above that have no all-shipped word at all. I can implement this as a separate change if you want — flagging rather than doing it unprompted since it shifts vocab output and interacts with your manual overrides.

5. Good everyday vs poor picks (my read, ~judgment): roughly ~70 good / ~35 poor. Clear poor picks (ateji / names / obscure): 墨西哥(Mexico), 伯剌西爾(Brazil), 哈爾浜(Harbin), 袁彦道, 弥勒, 玉蜀黍, 矢鱈, 箆蝶鮫, 怜悧狡猾, 嵯峨野線, 瓢鮎図, 稀覯本, 愍諒, 贖宥, 掛袱紗, 倭寇, 稜堡, 鴨茅, 茅渟, 槍鱮, 窮鼠噛猫, 鳳駕, 汀渚, 瓦斯, 浩瀚, 惇睦, 芙蓉峰. The rest are legitimate (麻痺, 椎茸, 胡椒, 喧嘩, 蜜柑, 桔梗, 紫蘇, 棺桶, 漏洩, 飢饉, 蟻塚, 駄洒落, 欺瞞, 杜撰, 鳳凰, 狼狽える…) where only the partner happens to be unshipped.

Now moving to #5 (similar-kanji rewrite). Marking #6's deliverable complete.