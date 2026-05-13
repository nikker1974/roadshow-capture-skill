---
name: roadshow-capture
description: "自动化捕获路演/在线演示页面并保存为 PDF。Playwright 驱动，支持 NetRoadShow 和 DealRoadShow。"
version: 1.2.0
metadata:
  hermes:
    tags: [roadshow, netroadshow, dealroadshow, capture, pdf, playwright]
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

---

## 首次使用（邮箱配置）

1. 用户告知你（agent）他的路演邮箱
2. 写入 `scripts/.env` 文件：
   ```
   NRS_EMAIL=your-email@your-company.com
   ```
3. 之后同一台机器不再需要询问

---

## NetRoadShow 工作流

脚本：`scripts/netroadshow-capture.py`

### 前置条件
- 路演 URL：`https://www.netroadshow.com/nrs/home/#!/?show=SHOW_ID`

### 已验证流程（KODIT Audio Roadshow Plus，32 slides，2026-05-12）

```
1. browser.goto(show_url)
   → 邮箱输入页（Angular 路由正常解析）

2. page.locator("#homeEmailInput").first.fill(email)
   → with page.expect_popup() as info: page.get_by_text("Launch Show").click()
   → pp = info.value  ← 必须用 expect_popup()，不能用 page.on("popup")

3. 弹窗 → /presentation/v2/{id}/disclaimer/
   → Agree 是 <div> 不是 <button>
   → pp.evaluate('document.querySelector(".btn-agree").click()')

4. "Start from beginning" 按钮
   → URL → /presentation/v2/{id}/MediaSlides

5. ArrowRight × N → 截图 → Pillow 合成 PDF
```

### NetRoadShow 专有陷阱

| 陷阱 | 方案 |
|------|------|
| 弹窗/新窗口 | `expect_popup()` 阻塞等待 |
| `div` 按钮（非 `button`） | `page.evaluate('.btn-agree').click()` |
| Hash 路由 `#!/?show=X` | Playwright 原生支持，无需处理 |
| Session Taint（失败后锁定） | 重建干净浏览器上下文 |
| 密码登录被拦截 | Email-Only 流程（已验证） |

---

## DealRoadShow 工作流

脚本：`scripts/dealroadshow-capture.py`

### 前置条件
- 路演 URL：`https://dealroadshow.com/e/XXXXXXX`

### 已验证流程（ArcelorMittal USD Bond，32 slides，2026-05-13）

```
1. browser.goto(deal_url)
   → 可能弹出 Cookie 横幅 → 点 "Ok"

2. page.locator("input").first.fill(email)
   → page.get_by_text("Launch Deal Roadshow").click()

3. URL → /e/XXXXXXX（Disclaimer 页面）
   → page.get_by_text("I Agree").click()  ← 标准 button，可直接点击

4. URL → /e/XXXXXXX/1（幻灯片页面）
   → 顶部显示 "1 of 32" + 翻页箭头

5. ArrowRight × N → 截图 → Pillow 合成 PDF
```

### 与 NetRoadShow 的关键区别

| 维度 | NetRoadShow | DealRoadShow |
|------|-------------|--------------|
| 弹窗 | `expect_popup()` 新窗口 | 同页面跳转，无需弹窗处理 |
| Disclaimer 按钮 | `<div>`，需 JS evaluate | 标准 `<button>`，直接 `.click()` |
| URL 格式 | SPA hash 路由 | RESTful: `/e/XXXX/{page}` |
| 翻页后 URL 变化 | 不变（SPA） | 变化（可检测翻页终点） |

---

## 通用陷阱

### Pillow PDF 合成需 format='PDF'
```python
# ✅ 必须显式指定 format='PDF'
imgs[0].save(path, save_all=True, append_images=imgs[1:], format='PDF', resolution=150)
```

### 总页数检测
- NetRoadShow：从 disclaimer 页 "All N Slides" 提取
- DealRoadShow：从 "X of Y" 文本提取；翻页后 URL 不变则判定为末页

---

## 交互式凭证引导

如果 `NRS_EMAIL` 未设置，agent 应按以下流程交互：

1. 检查 `NRS_EMAIL` 环境变量 → 有则直接使用
2. 检查 `scripts/.env` 是否有 `NRS_EMAIL=xxx` → 有则读取
3. 都没有 → 向用户提问："请提供你的路演邮箱地址"
4. 用户提供后 → 写入 `scripts/.env`
5. 提示用户记得把该邮箱加入路演授权列表

---

## 注意事项

- 邮箱统一使用 `NRS_EMAIL` 环境变量（两个平台共享）
- User-Agent 设置为 macOS Safari 以提高服务端信任度
- 翻页用 `page.keyboard.press("ArrowRight")`
- 截图尺寸 1920×1080，约 350KB~900KB 每张
- 参考：`references/netroadshow-practice.md`
