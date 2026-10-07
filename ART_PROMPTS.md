# 《双生纹》美术提示词

本版采用古老传说感的日漫手绘风格：清晰线稿、平涂上色、少量阴影和简洁背景。
正式素材按下面的文件名放进 `assets/` 目录，游戏启动时会自动加载；缺图时仍使用程序占位图。

| 放在哪里 | 文件名 | 建议尺寸 |
| --- | --- | --- |
| 卡面插画 | `assets/cards/<卡名>.png`，例如 `assets/cards/烈斩.png` | 400 × 260 |
| 纹兽本体 | `assets/beasts/<种类>.png`，例如 `assets/beasts/苍狼.png` | 512 × 512，透明背景 |
| 角色头像 | `assets/heroes/warrior.png`、`archmage.png`、`guardian.png` | 512 × 512 |

## 统一风格（每条提示词都加在后面）

为了 40 张卡和 9 种纹兽看起来是一套，所有提示词末尾都加上这段风格描述：

```
Ancient folklore legend Japanese hand-drawn 2D anime cel art: clean dark brown contour lines, simple flat muted color fills, only one restrained cel-shadow tone, warm nostalgic atmosphere, archaic bronze, wood, stone and linen where appropriate. Strong readable silhouette, very sparse details, no painterly or watercolor texture, no 3D, no photorealism, no intricate glow, no text, no lettering, no watermark.
```

颜色对应：红纹使用朱红与余烬橙，绿纹使用玉绿与苔绿，蓝纹使用靛蓝与水蓝。卡面采用横构图、简单背景；纹兽采用透明背景，本体不带纹路。

## 纹兽（9 种，按基础攻血）

数值越高越凶猛：1/1 小巧可爱，3/3 是压迫感很强的大型兽。纹兽本体不画纹路，纹路由游戏在进化时叠加上去
（2 级一道纹，3 级两道纹），所以一种纹兽只要一张图。

| 种类 | 攻/血 | 提示词 |
| --- | --- | --- |
| 灵雀 | 1/1 | `a tiny spirit sparrow made of smoke and stone, curious eyes, fragile, full body, transparent background` |
| 石龟 | 1/2 | `a small stone turtle spirit with a mossy shell, calm and sturdy, full body, transparent background` |
| 铁甲虫 | 1/3 | `an armored iron beetle spirit with heavy overlapping plates, slow but tough, full body, transparent background` |
| 疾狐 | 2/1 | `a lean swift fox spirit mid-leap, sharp ears, wispy tail, full body, transparent background` |
| 苍狼 | 2/2 | `a grey spirit wolf standing alert, balanced and loyal, full body, transparent background` |
| 棕熊 | 2/3 | `a large brown spirit bear, thick fur, protective stance, full body, transparent background` |
| 赤隼 | 3/1 | `a crimson falcon spirit diving with razor talons, aggressive, full body, transparent background` |
| 猎豹 | 3/2 | `a sleek hunting leopard spirit crouched to pounce, predatory focus, full body, transparent background` |
| 雷虎 | 3/3 | `a massive thunder tiger spirit, crackling lightning in its stripes, terrifying presence, full body, transparent background` |

## 角色头像

| 文件 | 提示词 |
| --- | --- |
| `warrior.png` | `portrait of a battle-scarred warrior, crimson sigils glowing on armor and blade, determined gaze, bust shot` |
| `archmage.png` | `portrait of an ancient sage, small blue charm stone in a raised hand, indigo linen robes, calm eyes, bust shot` |
| `guardian.png` | `portrait of a guardian with a tower shield, jade green sigils carved into the shield, steadfast, bust shot` |

## 卡面插画（40 张）

| 卡名 | 颜色 | 提示词 |
| --- | --- | --- |
| 迅斩 | 红 | `a blade cutting through the air in a single flash, motion streak` |
| 战吼 | 红 | `a warrior roaring, shockwave of red light bursting outward` |
| 试锋 | 红 | `a sword being drawn from its sheath, a thin red sigil running along the edge` |
| 裂风 | 红 | `wind torn apart by a sweeping slash, red crescent trail` |
| 斩兽 | 红 | `a greatsword cleaving a shadowy beast silhouette` |
| 碎域 | 红 | `a glowing rune circle on the ground shattering into shards` |
| 烈斩 | 红 | `a flaming sword strike, embers scattering` |
| 破甲 | 红 | `a spear piercing through a cracked metal shield` |
| 战意 | 红 | `a clenched gauntlet wrapped in burning red sigils` |
| 蓄势 | 红 | `a warrior crouched, gathering red energy into a drawn-back fist` |
| 狂怒 | 红 | `berserker eyes glowing red, veins of fire across the skin` |
| 重锤 | 红 | `a giant warhammer smashing down, ground cracking` |
| 连击 | 红 | `two afterimages of the same sword slash crossing` |
| 薄盾 | 绿 | `a thin translucent green barrier shimmering` |
| 生机 | 绿 | `a small green sprout glowing in cupped hands` |
| 木盾 | 绿 | `a wooden round shield with green leaf sigils` |
| 青藤 | 绿 | `green vines wrapping protectively around an arm` |
| 庇护 | 绿 | `a dome of green light sheltering a small beast` |
| 守望 | 绿 | `a sentinel standing on a wall at dusk, green lantern` |
| 铁盾 | 绿 | `a heavy iron kite shield, green runes along the rim` |
| 疗伤 | 绿 | `green light knitting a wound closed` |
| 坚守 | 绿 | `a shield planted firmly in the ground, roots growing from it` |
| 荆棘 | 绿 | `a shield covered in glowing green thorns` |
| 重铠 | 绿 | `full plate armor standing empty, green sigils on the chestplate` |
| 甘霖 | 绿 | `soft green rain falling from a clear sky` |
| 磐石 | 绿 | `a massive boulder engraved with green runes, unmovable` |
| 灵感 | 蓝 | `two glowing blue cards appearing from thin air above an open palm` |
| 召唤术 | 蓝 | `a blue summoning circle with a beast silhouette emerging` |
| 奥术飞弹 | 蓝 | `three blue arcane missiles streaking toward a target` |
| 燃魂 | 蓝 | `a soul-shaped blue flame clinging to a figure` |
| 法力回流 | 蓝 | `blue mana flowing back into a crystal like a reversed waterfall` |
| 混沌 | 蓝 | `a swirling sphere of unstable blue and violet energy` |
| 驱散 | 蓝 | `a blue wave dissolving a glowing shield into particles` |
| 洞察 | 蓝 | `a single blue eye opening in a rune circle, seeing through a face-down card` |
| 免伤符 | 蓝 | `a blue talisman paper hovering over a glowing floor rune` |
| 加固符 | 蓝 | `blue sigil braces locking around a rune circle on the ground` |
| 秘法盾 | 蓝 | `a hexagonal blue arcane shield made of simple ancient geometric sigil lines` |
| 封印 | 蓝 | `blue chains of runes binding a snarling beast` |
| 魔力风暴 | 蓝 | `a storm of blue lightning and runes sweeping across a battlefield` |
| 破法 | 蓝 | `a blue hand crushing a face-down card into fragments` |

## 场景与界面（9 张）

| 文件 | 内容 | 尺寸 |
| --- | --- | --- |
| `assets/backgrounds/battle.png` | 古树环绕的石庭战场，中央保留空旷地面 | 1010 × 800 |
| `assets/backgrounds/title.png` | 古老森林门庭，标题和按钮区域留白 | 1280 × 800 |
| `assets/ui/card_back.png` | 古铜纹章、三色纹石与简洁藤纹 | 248 × 352 |
| `assets/ui/card_frame_red.png` | 红纹卡框，空白深色内部 | 248 × 352 |
| `assets/ui/card_frame_green.png` | 绿纹卡框，空白深色内部 | 248 × 352 |
| `assets/ui/card_frame_blue.png` | 蓝纹卡框，空白深色内部 | 248 × 352 |
| `assets/fields/red.png` | 战意石庭、红纹徽记 | 400 × 260 |
| `assets/fields/green.png` | 守护石庭、绿纹与根系 | 400 × 260 |
| `assets/fields/blue.png` | 秘法石庭、蓝纹与星记 | 400 × 260 |

完整61张素材的生成提示词、目标尺寸和完成状态保存在 `assets/art_manifest.json`。
背景飘叶、微光、纹域脉动、伤害斩击和治疗波纹由程序绘制，不需要GIF或额外逐帧图片。
文字、费用和规则仍由程序绘制，插画本身不带文字。

## 检查素材

```bash
python -m pip install Pillow pygame-ce
python tools/check_art.py
```

该命令核对完整卡池与纹兽名称、尺寸、透明背景，以及实际Pygame图片加载与绘制。
制作中可加 `--allow-incomplete` 只检查已完成的图片。

## 小贴士

- 先只生成 9 种纹兽和 3 个头像（12 张），整个画面的感觉就出来了；卡面可以慢慢补。
- 同一个工具、同一套风格描述、固定随机种子（Midjourney 的 `--seed`）生成，风格会更统一。
- 纹兽要透明背景（PNG）。工具不支持透明的话，生成纯黑背景再用抠图工具去掉。

