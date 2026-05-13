# RoadShow Capture Skill

> 自动化捕获 NetRoadShow 路演/在线演示的所有页面并保存为 PDF。
>
> 由 Playwright 驱动，支持 **Hermes Agent** 和 **OpenClaw** 两大 AI Agent 平台。

---

## 安装

### 方式一：Hermes Agent

```bash
# 克隆仓库
git clone https://github.com/nikker1974/roadshow-capture-skill.git

# 复制到 Hermes skills 目录
cp -r roadshow-capture-skill ~/.hermes/skills/roadshow-capture
```

### 方式二：OpenClaw

```bash
# 直接从 ClawHub 安装（推荐）
openclaw skills install roadshow-capture-skill

# 或手动安装
git clone https://github.com/nikker1974/roadshow-capture-skill.git
cp -r roadshow-capture-skill ~/.config/openclaw/skills/roadshow-capture
openclaw skills check
```

### 前置依赖

所有平台都需要：

```bash
pip install playwright pillow
playwright install chromium
```

---

## 配置

设置你的 NetRoadShow 邮箱（**必填**）：

```bash
export NRS_EMAIL=your-email@company.com
```

或者首次使用 agent 时，它也会主动问你邮箱，写入 `.env` 文件。

---

## 使用方法

告诉你的 agent：

> 帮我抓这个路演：https://www.netroadshow.com/nrs/home/#!/?show=SHOW_ID

或手动运行脚本：

```bash
python3 scripts/netroadshow-capture.py \
  --url "https://www.netroadshow.com/nrs/home/#!/?show=SHOW_ID" \
  --email your@email.com \
  -o /tmp/roadshow_output
```

输出为 `/tmp/roadshow_output/roadshow.pdf`。

---

## SKILL.md 结构说明

`SKILL.md` 的 frontmatter 同时包含两类 metadata：

```yaml
metadata:
  hermes:    # ← Hermes Agent 加载此段
  openclaw:  # ← OpenClaw 加载此段
```

两个平台各取所需，互不干扰。

---

## 技术要点

| 要点 | 说明 |
|------|------|
| 弹窗捕获 | 必须用 `expect_popup()` 阻塞等待，不能用 `page.on("popup")` |
| Disclaimer 按钮 | `<div>` 非 `<button>`，需 `page.evaluate('.btn-agree').click()` |
| 翻页 | `page.keyboard.press("ArrowRight")` 逐页前进 |
| PDF 合成 | Pillow 需显式指定 `format='PDF'` |
| Email 配置 | 环境变量 `NRS_EMAIL` → `--email` 参数 → agent 提问 |

详见 [`references/netroadshow-practice.md`](references/netroadshow-practice.md)。

---

## License

[MIT-0](https://opensource.org/licenses/MIT-0) — 免费使用、修改、再分发，无需署名。
