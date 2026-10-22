# 本地前端依赖

页面从本项目加载图标和字体，不需要访问 CDN 或 Google Fonts。

| 资源 | 用途 | 来源与许可 |
| --- | --- | --- |
| Font Awesome Free 6.4.0 | 页面图标 | npm 官方包 `@fortawesome/fontawesome-free@6.4.0`；字体 SIL OFL 1.1，代码 MIT，图标 CC BY 4.0；完整许可见 [LICENSE.txt](fontawesome-6.4.0/LICENSE.txt) |
| Roboto | 页面西文字体 | Google Fonts 仓库；[SIL OFL 1.1](fonts/roboto/OFL.txt) |
| Source Code Pro | 代码编辑器等宽字体 | Google Fonts 仓库；[SIL OFL 1.1](fonts/sourcecodepro/OFL.txt) |

字体文件及 Font Awesome CSS/字体保持上游原样，仅调整页面加载地址；`fonts/fonts.css` 为本项目的本地字体声明。固定来源版本、下载地址和校验值见 [sources.json](sources.json)。
