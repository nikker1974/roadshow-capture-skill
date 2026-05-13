---
name: roadshow-capture
description: "自动化捕获路演/在线演示页面并保存为 PDF。Playwright 驱动，支持 NetRoadShow 和 DealRoadShow。"
version: 1.2.0
metadata:
  hermes:
    tags: [roadshow, netroadshow, dealroadshow, capture, pdf, playwright, finsight]
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

自动打开路演链接，处理认证流程，逐页截屏保存为 PDF。支持 **NetRoadShow** 和 **DealRoadShow** 两大平台。

**原则：直接使用 Playwright，不要用 Camofox。** Camofox 对路演平台有严重局限（hash 路由编码、弹窗拦截、reCAPTCHA、Angular 沙箱），Playwright 能处理所有 Camofox 做不到的事。

---

## 首次使用（邮箱配置）

1. 用户告知 agent 他的路演邮箱
2. 写入 `scripts/.env` 文件：
   ```
   NRS_EMAIL=your-email@your-company.com
   ```
3. 之后不再需要询问

如果 `NRS_EMAIL` 未设置，agent 主动提问并写入 `.env`，不要求用户提前配环境变量。

---

## NetRoadShow 工作流

脚本：`scripts/netroadshow-capture.py`
URL 格式：`https://www.netroadshow.com/nrs/home/#!/?show=SHOW_ID`

### 已验证流程（KODIT Audio Roadshow Plus，32 slides，2026-05-12）

```
1. browser.goto(show_url)
   → Angular SPA 路由正常解析，无需 hash 修正
   → URL 自动变为 /nrs/home/?show=SHOW_ID

2. page.locator("#homeEmailInput").first.fill(email)
   with page.expect_popup() as info:
       page.get_by_text("Launch Show").click()
   pp = info.value  ← 必须 expect_popup()，不能用 page.on("popup")

3. 弹窗 → /presentation/v2/{id}/disclaimer/
   Agree 是 <div class="disclaimer-btn btn-agree">，非 <button>
   ✅ pp.evaluate('document.querySelector(".btn-agree").click()')
   ❌ page.get_by_text("Agree").click() — 不触发

4. 出现 "Resume previous session" / "Start from beginning"
   永远选 Start from beginning（硬性约束，不用问用户）

5. URL → /presentation/v2/{id}/MediaSlides

6. ArrowRight × (N-1) → 截图 → Pillow 合成 PDF（必须 format='PDF'）
```

### URL 状态机

```
/home/#!/?show=SHOW_ID  →  邮箱输入页
   ↓ Fill email → Launch Show（expect_popup）
/home/?show=SHOW_ID      →  弹窗打开
   ↓ Popup
/presentation/v2/{id}/disclaimer/  →  法律条款（div 按钮）
   ↓ Agree（JS evaluate）
/presentation/v2/{id}/disclaimer/  →  Resume / Start from beginning
   ↓ Start from beginning（固定选）
/presentation/v2/{id}/MediaSlides  →  路演播放器
   ↓ ArrowRight × 截图
   PDF 合成
```

### NetRoadShow 专有陷阱

| 陷阱 | 方案 |
|------|------|
| 弹窗/新窗口 | `expect_popup()` 阻塞等待 |
| `div` 按钮（非 `button`） | `page.evaluate('.btn-agree').click()` |
| Hash 路由 `#!/?show=X` | Playwright 原生支持，无需处理 |
| Session Taint（失败后锁定） | 重建干净浏览器上下文：首页 → 乱填 Entry Code → Continue → 恢复 |
| 密码登录被拦截 | Email-Only 流程（zofundintl.com 域已验证） |

---

## DealRoadShow 工作流

脚本：`scripts/dealroadshow-capture.py`
URL 格式：`https://dealroadshow.com/e/XXXXXXXX`

### 已验证流程（ArcelorMittal USD Bond，32 slides，2026-05-13）

```
1. browser.goto(deal_url)
   可能弹出 Cookie 横幅 → page.get_by_role("button", name="Ok").click()

2. 填邮箱 → page.get_by_text("Launch Deal Roadshow").click()
   （同一个页面，无需弹窗处理）

3. URL → /e/XXXXXXX（Disclaimer 页）
   page.get_by_text("I Agree").click()  ← 标准 <button>，可直接点击

4. URL → /e/XXXXXXX/1（幻灯片页，基于页码的 RESTful URL）
   顶部显示 "1 of 32" 翻页控件

5. ArrowRight × 截图 → 翻页后 URL 变 → URL 不变则检测到末页
   Pillow 合成 PDF（必须 format='PDF'）
```

### DealRoadShow 流程要点

- **无弹窗**：认证后同页面跳转，不需要 `expect_popup()`
- **I Agree 按钮**：必须用 Playwright locator `.click()`，不要用 `page.evaluate()`（JS 点击不触发导航）
- **翻页检测**：通过 `input[data-test="currentSlideInput"]` 的 `value` 属性读取当前页码；"of 32" 文本提取总数
- **URL 格式不确定**：有时 `/e/XXXX/1`（带页码），有时 `/e/XXXX`（不带），因此翻页终点不能依赖 URL 变化
- **总页数检测**：从页面 "of 32" 文本提取总数，翻页后用 input value 是否增加判定终点

---

## 双平台对比

| 维度 | NetRoadShow | DealRoadShow |
|------|-------------|--------------|
| 弹窗 | `expect_popup()` 新窗口 | 同页面跳转，无需弹窗处理 |
| Disclaimer 按钮 | `<div>`，需 JS evaluate | 标准 `<button>`，直接 `.click()` |
| URL 格式 | SPA hash 路由 | RESTful: `/e/XXXX/{page}` |
| 翻页后 URL | 不变（SPA） | 变化（可检测末页） |
| 总页数检测 | "All N Slides" 文本 | "X of Y" 文本 + URL 变化 |
| Cookie 横幅 | 无 | 可能有，"Ok" 按钮 |

---

## 通用陷阱

### Pillow PDF 合成需 format='PDF'
```python
# ✅ 必须显式指定 format='PDF'
imgs[0].save(path, save_all=True, append_images=imgs[1:], format='PDF', resolution=150)
```

### headless 模式下信任度
Mac Safari UA 字符串 + Playwright headless Chromium 对两个平台都可用。

### 邮箱配置统一
两个平台共享 `NRS_EMAIL` 环境变量，无需分别配置。

---

## 注意事项

- User-Agent 设置为 macOS Safari 以提高服务端信任度
- 翻页统一用 `page.keyboard.press("ArrowRight")`
- 截图尺寸 1920×1080，约 350KB~900KB 每张
- 总输出 PDF 约 4-5 MB（32 slides）
- 参考：`references/netroadshow-practice.md`（实操记录含 Mermaid 流程图）
- GitHub 仓库：https://github.com/nikker1974/roadshow-capture-skill（Hermes + OpenClaw 双平台兼容）
