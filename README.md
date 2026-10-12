# note-craft-skill

面向 Codex 的 Markdown 学习笔记整理 Skill。项目当前为 **v0.1.0 预发布版本**，作者为 **lizeping-hub**。

输入包含图片、表格、代码、链接或碎片化表达的学习笔记，输出两份独立 Markdown：

- **基础整理版**：保留原标题文字、层级和顺序，清洗内容，用于 Dify 等知识库入库。
- **专业研究报告版**：保留知识主干，补充原理、应用、对比和来源，用于深度学习和面试准备。

## 在 Codex 中安装

复制以下请求到 Codex 对话中发送。每次安装获取 `main` 分支最新内容，使用个人级安装位置。

```text
$skill-installer 请从 https://github.com/lizeping-hub/note-craft-skill/tree/main/note-craft-skill-v1 安装 main 分支最新的 note-craft-skill-v1，使用当前用户的个人级安装位置，并启用自动匹配。安装完成后，确认 Skill 可被发现，并告诉我调用方式。
```

安装完成后，下一轮对话中即可使用。提供 Markdown 文件或正文，并调用：

```text
用 $note-craft-skill-v1 处理这份 Markdown 学习笔记。
```

## 文件结构

```text
note-craft-skill-v1/   Skill 本体及 Python 标准库辅助脚本
docs/                GitHub Pages 单页落地页
```

Skill 目录包含 `SKILL.md`、`reference.md`、`agents/openai.yaml` 和 `scripts/note_ops.py`。详细处理规则与脚本调用方式见 `reference.md`。

脚本负责标题、格式和覆盖记录校验；不执行 OCR，也不验证研究结论。素材识别、数字、表格和来源仍需要内容复核。

## 页面开发与部署

落地页使用原生 HTML、CSS 和 JavaScript，无构建步骤和外部资源依赖。内容集中在 `docs/assets/content.js`，包含中文、完整英文、安装请求和课堂示例。

维护文案时，同时同步 `docs/index.html` 中的中文静态回退内容。已安装的 Skill 不会因页面更新自动升级；安装指令每次指向最新 `main`。

本地预览：

```text
python3 -m http.server 8765 --directory docs
```

页面默认中文，右上角切换语言。直接访问 `?lang=en` 可打开英文内容；语言选择保存在浏览器中。示例来自 10.12 课堂笔记，英文示例为对应译文。

发布 GitHub Pages：提交 Skill 和 `docs/` 后，在仓库 **Settings → Pages** 选择 **Deploy from a branch**，分支选 **main**，目录选 **/docs**，保存并等待发布。

已上线地址：[中文页面](https://lizeping-hub.github.io/note-craft-skill/) · [English](https://lizeping-hub.github.io/note-craft-skill/?lang=en)。页面路径使用相对地址，适配 GitHub Pages 项目子路径。

页面主要入口是“复制安装命令”，没有仓库跳转或 ZIP 下载按钮。

## 待定事项

许可证和反馈渠道尚未确定；此仓库目前不对这些事项作出声明。

---

## English

A Codex Skill that turns Markdown learning notes into two independent documents: a cleaned version for knowledge bases, and a professional research report for deeper study and interview preparation.

The project is a **v0.1.0 pre-release**, authored by **lizeping-hub**. Each installation retrieves the latest content on `main`.

Paste this request into Codex:

```text
Use $skill-installer to install the latest note-craft-skill-v1 from the main branch at https://github.com/lizeping-hub/note-craft-skill/tree/main/note-craft-skill-v1 as a user-level Skill, and enable automatic matching. After installation, verify that the Skill can be discovered and explain how to invoke it.
```

The Skill is available on your next turn. Provide a Markdown file or pasted source and ask:

```text
Use $note-craft-skill-v1 to process these Markdown learning notes.
```

The [live landing page](https://lizeping-hub.github.io/note-craft-skill/?lang=en) lives in `docs/`. GitHub Pages publishes from `main` and `/docs`. The page has a complete English mode through the language switch or `?lang=en`. License and feedback channels are still undecided.
