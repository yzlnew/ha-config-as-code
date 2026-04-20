---
name: sync-to-public
description: 将本内部仓库同步到公开 GitHub 仓库（yzlnew/ha-config-as-code）。用于发布配置更新、README、脚本等可公开内容，自动剔除本地配置和 secrets。触发场景：用户说"同步到公开仓库"、"发布到 public"、"推送 public 仓库"、"sync public"。
---

# sync-to-public

把本仓库（内部）同步到公开仓库 `yzlnew/ha-config-as-code`。公开仓库默认位于 `../ha-public`。

## 首次初始化（如果 `../ha-public` 不存在）

```bash
./sync-to-public.sh --init
```

## 日常同步

```bash
./sync-to-public.sh
```

脚本会：
1. 清空 `../ha-public`（保留 `.git`）
2. 复制所有 `git ls-files` 追踪的文件（自动尊重 `.gitignore`）
3. 额外剔除：`.DS_Store`、`__pycache__`、`*.pyc`、`.claude/settings.local.json`、`.agents/settings.local.json`
4. 扫描潜在 secrets（JWT 模式、YAML 硬编码密码），命中则中止
5. 展示 diff，提示用户确认
6. 使用内部最近一次 commit message 作为默认消息（可覆盖）
7. `git push -u origin main`

## 何时邀请用户运行

- 用户口头要求同步/发布到 public
- 内部仓库刚合并了一个面向公开展示的变更（如 README、脚本、文档），且用户表示希望公开

## 注意事项

- 脚本对 secrets 做了模式扫描但不是万能的。**重要变更前建议先用 `git diff` 看一眼 staged 文件。**
- `.codex` / `.gemini` 是指向 `.agents` 的 symlink；`.agents/` 内部是指向 `.claude/` 的 symlink。同步时这些 symlink 会被原样复制到公开仓库——内容通过 symlink 解引用，是可公开的。
- 若新增需要屏蔽的文件，应同时更新 `.gitignore` 和脚本 `sync()` 里的显式 rm 列表。
- `yzlnew/ha-config-as-code` 的推送需要 `git` 已配置好推送凭据（gh CLI auth 或 SSH key）。
