# 达菲郁素材署名

头像 portrait.png 与眨眼图集 idle.png 来自鲸鱼娘资源库收录的桌宠项目。
作者：YunYueSama
仓库：https://github.com/YunYueSama/codex-deepseek-pet
来源版本：7661c8b304c5400701f91da01b1a643a207331de
原文件：assets/whale/portrait.png、assets/whale/idle-front.png。文件保持原样；页面通过 CSS 裁切头像、切换眨眼帧并添加浮动动画。
许可全文见 LICENSE.txt；素材范围说明见 ASSET_LICENSE.md。

语气参考：ERUIHNIYHBKBNF / https://github.com/ERUIHNIYHBKBNF/dafeiyu-persona
本项目重新编写适用于编程教学的提示词，采用俏皮、轻微傲娇与海洋意象，不采用辱骂或伪造心声。原项目 MIT 许可见 PERSONA_LICENSE.txt。

资源入口：https://treapgogo.github.io/deepseek-whale-girl/
形象为社区二创，本应用不代表 DeepSeek 官方。

## 动作图集

`actions.webp` / `actions.json` 由同一来源版本的 `assets/whale/idle-front.png`、`inbetween-jump.png`、`dense-wave.png`、`inbetween-sleep.png`、`story-token.png`、`dense-dance.png` 中选取的完整角色帧编译。
修改：抽取 92 帧、缩放为 256×256 像素、合并成无损 WebP 图集；未重绘角色。12 个动作的播放顺序参考上游 `src/renderer/motion.js`，时长针对网页互动调整。编译脚本见 `scripts/build_pet_atlas.py`。
动作图集沿用本目录 LICENSE.txt 中的署名许可。
