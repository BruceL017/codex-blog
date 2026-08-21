# Codex Blog 中文说明

Codex Blog 是面向 OpenAI Codex 的完整 SEO 内容流水线，包含 33 个 Skill、
6 个 TOML Agent、确定性 Python CLI、可选 SEO 素材适配器，以及带安装所有权
保护的跨平台安装器。

它的最高优先级不是“所有产物都成功”，而是：**先完成并保存完整的 SEO 文章
Markdown 正文**。Schema、HTML、PDF、SEO/GEO 检查、事实和链接检查、平台格式
都属于下游增强。每个下游阶段失败后只重试一次；第二次仍失败就跳过，并在最终
报告里说明，不扣住正文。

图片默认关闭。文章和非图片流程全部完成后，Codex 只询问一次是否生成图片。
用户未明确回答需要时，不探测 Provider、不调用 API/MCP、不创建图片占位符，
也不会因为没有图片降低文章评分。

本项目是独立社区项目，与 OpenAI、AgriciDaniel、Codex SEO 以及文档提到的
任何服务商均不存在官方隶属或背书关系。

## 安装

只安装 Marketplace 和 33 个 Skill：

```bash
codex plugin marketplace add BruceL017/codex-blog --ref v2.1.2
codex plugin add codex-blog@brucel017-codex-blog
```

推荐完整安装（额外安装 6 个全局 Agent 和 `codex-blog` 启动器）：

```bash
git clone --branch v2.1.2 https://github.com/BruceL017/codex-blog.git
cd codex-blog
./install.sh
```

Windows PowerShell：

```powershell
git clone --branch v2.1.2 https://github.com/BruceL017/codex-blog.git
Set-Location codex-blog
.\install.ps1
```

安装器不会自动安装或配置图片 API、MCP、Codex SEO、
`extract-seo-materials`，也不会写入任何密钥。详情见
[安装说明](INSTALLATION.md)。

## 直接创作完整文章

```text
$blog write
核心关键词：AI 内容流水线
目标读者：内容团队
语言：中文
请完成一篇完整 SEO 文章；最后再询问我是否需要图片。
```

兼容 Codex SEO 的直接写作入口：

```text
$blog-write
读取 ./seo-brief.json 和
./_content_materials/sessions/project-seo-materials.md，围绕“AI 内容流水线”
写成完整中文 SEO 文章，并保留事实状态与来源边界。
```

如果没有 SEO Brief 或外部 Skill，Codex Blog 会用自己的研究、Brief、Outline、
写作、编辑和打包流程继续完成文章。

## SEO 与素材适配

Codex Blog 可以消费：

- Codex SEO 生成的 Content Brief；
- `cluster-plan.json` 和单篇 `cluster_context`；
- `extract-seo-materials` v1/v2 会话、项目或主题素材；
- 普通 Markdown、JSON、网页研究结果和用户直接输入。

固定优先级为：当前用户指令 → 显式 Brief/集群计划 → 素材包 → 项目品牌与
Persona → Blog 自身研究。适配器只转换数据，不导入外部 Skill 源码，也不把
外部 Skill 变成运行依赖。

`extract-seo-materials` 输出的是素材而不是文章。其 `hypothesis`、`failed`、
`unknown` 等状态不会在转换后自动变成已验证事实；公开边界和来源引用会一直
保留到审稿阶段。

## 图片规则

默认 `image_mode` 为 `deferred`。结尾可选：

- 不生成；
- 只生成一张封面；
- 生成封面和最多三张必要的正文图。

Provider 顺序为 Codex 原生能力 → 已配置 API → MCP。API 支持
OpenAI-compatible 与 Gemini-compatible，并允许自定义 `base_url`。密钥只从
用户私有的 `${CODEX_HOME}/codex-blog/config.json`（或 `image generate
--config` 显式指定的可信文件）所声明的环境变量名读取；项目内的
`.codex-blog/config.json` 会被忽略。自定义端点必须使用
`CODEX_BLOG_IMAGE_*` 专用环境变量；官方默认密钥名只允许发送到官方 API
主机。见 [Provider 说明](PROVIDERS.md)。

## 输出

默认目录：`.codex-blog/output/<slug>/`。其中 `<slug>.md` 是唯一硬交付，
`request.json` 和 `run-manifest.json` 记录输入、阶段、尝试次数、警告与恢复状态。
Schema、HTML、PDF、当前检测目标的平台 handoff 和图片是可选增强。

最终状态为 `complete` 或 `complete_with_warnings`。只有三次恢复后仍无法形成
结构完整的正文才会 `blocked`。

## 验证与卸载

```bash
codex-blog doctor
python3 scripts/validate_repo.py
python3 -m pytest -q tests plugins/codex-blog/tests
./uninstall.sh
```

卸载器只删除安装状态中由本项目拥有且哈希未变化的文件；用户修改的 Agent、
项目输出、Provider 配置和 Brain 数据都会保留。

## 来源与许可

公开功能基于 MIT 许可的
[claude-blog 2.1.1](https://github.com/AgriciDaniel/claude-blog/tree/v2.1.1)
移植。上游单独限制许可的 `brain/` 目录没有被复制，本项目的 Brain 是 clean-room
实现。FLOW 提示内容继续按 CC BY 4.0 归属。详情见
[NOTICE](../NOTICE)、[THIRD_PARTY.md](../THIRD_PARTY.md) 和
[UPSTREAM.md](../UPSTREAM.md)。
