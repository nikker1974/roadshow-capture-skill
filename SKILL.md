---
name: roadshow-capture
description: "自动化捕获路演/在线演示的所有页面并保存为 PDF。直接使用 Playwright 绕过 Camofox 局限。支持 NetRoadShow 等平台。"
version: 1.0.0
metadata:
  hermes:
    tags: [roadshow, netroadshow, capture, pdf, screenshot, playwright]
    related_skills: [browser-tools]
  openclaw:
    requires:
      bins: [python3]
      env:
        - NRS_EMAIL
    install:
      - kind: pip
        packages: [playwright, pillow]
---

# RoadShow Capture — 路演页面自动截屏/PDF 保存

自动打开路演链接，处理认证流程，逐页截屏保存为 PDF。

## 原则

**直接使用 Playwright，不要用 Camofox。** Camofox 对 NetRoadShow 有严重局限（hash 路由编码、弹窗拦截、reCAPTCHA、Angular 沙箱），Playwright 能处理所有 Camofox 做不到的事。

## NetRoadShow 完整工作流（已验证可靠）

### 用户偏好（硬性约束）
- **永远从 "Start from beginning"（从头开始），永不 Resume 上次进度。** 即使用户之前看过一半关掉，下次捕获也重新开始。如果页面询问 "Resume previous session" / "Start from beginning"，一律选后者。不加 --resume 参数，也不用问用户。

### 前置条件
- 需要的文件：`scripts/netroadshow-capture.py`
- 用户邮箱（见下方「首次使用」说明）
- 路演 URL（格式 `https://www.netroadshow.com/nrs/home/#!/?show=SHOW_ID`）
- 依赖：`playwright` + `Pillow` + `playwright install chromium`

## 首次使用（邮箱配置）

1. 用户需要告知你（agent）他的 NetRoadShow 邮箱
2. 写入 `skills/roadshow-capture/.env` 文件：
   ```
   NRS_EMAIL=your-email@your-company.com
   ```
3. 之后同一台机器不再需要询问

## 运行工作流

### 已验证流程（KODIT Audio Roadshow Plus，32 slides，2026-05-12）

```
1. browser.goto("https://www.netroadshow.com/nrs/home/#!/?show=SHOW_ID")
   → 直接显示邮箱输入框（Angular 路由正常解析，无需 hash 修正）
   → 注意：URL 会变为 /nrs/home/?show=SHOW_ID（base href 去 hash，正常）

2. Fill email → Launch Show → 用 expect_popup() 阻塞等待弹窗
   → page.locator("#homeEmailInput").first.fill(email)
   → with page.expect_popup() as info: page.get_by_text("Launch Show").click()
   → pp = info.value  ← 必须用 expect_popup()，不能用 page.on("popup")

3. 弹窗进入 disclaimer 页
   URL: /presentation/v2/{pres_id}/disclaimer/
   内容：法律条款文本
   Agree/Disagree 按钮是 <div class="disclaimer-btn btn-agree"> 和 btn-disagree
   ⚠️ 不是 <button> 元素！不能用 page.get_by_text("Agree").click()
   ✅ 正确方式：pp.evaluate('document.querySelector(".btn-agree").click()')

4. Agree 后仍停留在 /disclaimer/ URL，但内容变为：
   "Welcome back, Meng!" + "Resume previous session" / "Start from beginning"
   底部显示总页数如 "All 32 Slides"

5. 点击 "Start from beginning"（或用 page.get_by_text 定位）
   → URL 跳转至 /presentation/v2/{pres_id}/MediaSlides
   → 进入音频路演播放器视图

6. 翻页：page.keyboard.press("ArrowRight") 逐张前进
   每页截图前等待 1.5s 让渲染完成

7. 合成 PDF：
   ✅ Image.open(f).convert("RGB") → .save(path, save_all=True, append_images=..., format='PDF', resolution=150)
   ⚠️ 必须加 format='PDF' 参数，否则 Pillow 缺失 JPEG 支持时会报 KeyError: 'JPEG'
```

### URL 状态机

```
/home/#!/?show=SHOW_ID  →  邮箱输入页（Email + Launch Show）
   ↓ Fill email → Launch Show
/home/?show=SHOW_ID      →  "Thank you for viewing" 页面 + 弹窗打开
   ↓ Popup（新窗口）
/presentation/v2/{id}/disclaimer/  →  法律条款
   ↓ Agree (JS click .btn-agree)
/presentation/v2/{id}/disclaimer/  →  Resume / Start from beginning
   ↓ Start from beginning
/presentation/v2/{id}/MediaSlides  →  路演播放器（音频同步 + 翻页）
   ↓ ArrowRight (×N)
   逐张截图
```

## 已知陷阱与解决方案

### 陷阱 1：Camofox 不可用于 NetRoadShow 正式路演

| 问题 | Camofox | Playwright |
|------|---------|------------|
| Hash 路由 `#!/?show=X` | 编码为 `%2F%3F`，SPA 不解析 | 直接导航，正常解析 |
| 弹窗/新窗口 | `page.on("popup")` 事件延迟，捕获不到 | `expect_popup()` 阻塞等待，精准 |
| reCAPTCHA | headless 模式下失败 | Mac UA + headless 下成功 |
| Angular `$http` | `browser_console` 500 错误 | `page.evaluate()` 正常 |
| div 按钮点击 | 定位不到 | `page.evaluate('...click()')` 绕过 |
| 服务端信任 | 低（可能被拒绝） | Mac Safari UA 通过 |

### 陷阱 2：div 按钮无法用 standard locator 点击

Disclaimer 页的 Agree/Disagree 按钮是 `<div class="disclaimer-btn btn-agree">Agree</div>`，不是 `<button>` 元素。

❌ 无效方法：
- `page.get_by_text("Agree").click()` — 不触发
- `page.locator("button:has-text('Agree')")` — 找不到
- `page.locator(".btn-agree").click()` — Playwright 的 .click() 在 div 元素上可能不触发事件

✅ 正确方法：
```python
pp.evaluate('document.querySelector(".btn-agree").click()')
```

### 陷阱 3：Session Taint

失败一次（如 Entry Code 无效）后同一 Session 持续失败。需重建干净会话：首页 → Entry Code 输入任意内容 → Continue → 自动跳转到无报错的邮箱页。

### 陷阱 4：Pillow PDF 合成需 format='PDF'

```python
# ❌ 缺 format 参数可能报 KeyError: 'JPEG'
imgs[0].save(path, save_all=True, append_images=imgs[1:])

# ✅ 正确
imgs[0].save(path, save_all=True, append_images=imgs[1:], format='PDF', resolution=150)
```

### 陷阱 5：登录密码被安全组拦截

zofundintl.com 域邮箱的密码登录会被安全组拒绝（"please use your internal portal"）。只能用 Email-Only 流程。

## 脚本说明

`scripts/netroadshow-capture.py` — 完整自动化脚本：
- Playwright Chromium headless
- Email-Only 流程：导航 → 填邮箱 → Launch Show → expect_popup
- div 按钮 Agree（JS evaluate）
- 选择 Start from beginning
- ArrowRight 逐页前进 + 截图
- Pillow 合成 PDF

## 交互式凭证引导

如果 `NRS_EMAIL` 环境变量未设置，agent 应按以下流程交互：

1. 检查 `NRS_EMAIL` 是否已设 → 有则直接使用
2. 检查 `scripts/.env` 是否有 `NRS_EMAIL=xxx` → 有则读取
3. 都没有 → 向用户提问："请提供你的 NetRoadShow 邮箱地址，我会保存以后就不用再问了"
4. 用户提供后 → 写入 `scripts/.env`（格式 `NRS_EMAIL=xxx`），代码中自动读取
5. 提示用户记得把该邮箱加入公司的路演授权列表

**不要求用户提前配环境变量**，靠对话把设置门槛降到零。

## 注意事项

- 用户邮箱：agent 首次运行时询问并写入 `.env`（`NRS_EMAIL` 环境变量）
- User-Agent 设置为 macOS Safari 以提高服务端信任度
- 翻页用 `page.keyboard.press("ArrowRight")` 而非点击导航按钮
- 截图尺寸 1920×1080，约 350KB~900KB 每张
- 总输出 PDF 约 4-5 MB（32 slides）
- 不要把页面截完的 middle state 搞混——第 1 张是初始页截图，随后每按一次 ArrowRight 截一张。32 slides = 32 张截图
- 参考：`references/netroadshow-practice.md`
- ClawHub 发布参考：`references/clawhub-publishing.md`
