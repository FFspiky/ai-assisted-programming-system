# 达菲郁素材署名

头像 portrait.png 与眨眼图集 idle.png 来自鲸鱼娘资源库收录的桌宠项目。
作者：YunYueSama
仓库：https://github.com/YunYueSama/codex-deepseek-pet
来源版本：7661c8b304c5400701f91da01b1a643a207331de
原文件：assets/whale/portrait.png、assets/whale/idle-front.png。文件保持原样；页面通过 CSS 裁切头像、切换眨眼帧并添加浮动动画。
许可全文见 LICENSE.txt；素材范围说明见 ASSET_LICENSE.md。

`ASSET_LICENSE.md` 保留上游原文，其中的相对链接指向上游仓库的目录，不是本项目运行依赖。可在 [固定来源版本](https://github.com/YunYueSama/codex-deepseek-pet/tree/7661c8b304c5400701f91da01b1a643a207331de) 中查看所引用的角色设定、素材记录和许可文件。

语气参考：ERUIHNIYHBKBNF / https://github.com/ERUIHNIYHBKBNF/dafeiyu-persona
本项目重新编写适用于编程教学的提示词，采用俏皮、轻微傲娇与海洋意象，不采用辱骂或伪造心声。原项目 MIT 许可见 PERSONA_LICENSE.txt。

资源入口：https://treapgogo.github.io/deepseek-whale-girl/
形象为社区二创，本应用不代表 DeepSeek 官方。

## 动作图集

`actions.webp` / `actions.json` 由同一来源版本的 `assets/whale/idle-front.png`、`inbetween-jump.png`、`dense-wave.png`、`inbetween-sleep.png`、`story-token.png`、`dense-dance.png` 中选取的完整角色帧编译。
修改：抽取 92 帧、缩放为 256×256 像素、合并成无损 WebP 图集；未重绘角色。12 个动作的播放顺序参考上游 `src/renderer/motion.js`，时长针对网页互动调整。编译脚本见 `scripts/build_pet_atlas.py`。
动作图集沿用本目录 LICENSE.txt 中的署名许可。

## 首页高清动作（2026-10-13）

`home/idle-front.png`、`home/dense-wave.png`、`home/dense-dance.png` 是上述固定来源版本的原始文件，未缩放、未重绘。已通过 GitHub Contents API 返回的 Git blob SHA-1 校验：本地副本与上游一致。

- 待机原图 2048×1024，2 列 1 行，每帧 1024×1024。
- 挥手 / 说话原图 2048×4096，4 列 8 行，每帧 512×512。
- 跳舞原图 2048×4096，4 列 8 行，每帧 512×512。

`home/actions.json` 记录与现有 `scripts/build_pet_atlas.py` 一致的原始帧号、时长和动作顺序。首页通过 CSS 裁切原图播放；维持原显示尺寸，进入角色区域才加载，跳舞图集在悬停、键盘聚焦或点击时加载。刷题页继续使用原先的轻量图集。许可继续适用本目录 LICENSE.txt 和 ASSET_LICENSE.md。
