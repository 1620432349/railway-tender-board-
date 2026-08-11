# 路局竞商管理看板（旅游专列）

国铁招商网 **旅游专列** 竞商文件全流程管理看板。部署于 GitHub Pages，数据云端共享、访客端每 60 秒自动轮询刷新，你更新后台数据后所有人无需手动刷新即可看到最新。

## 在线访问

部署后填写 GitHub Pages 链接（形如 `https://<用户名>.github.io/<仓库名>/`）。

## 数据说明

- `data.json` —— 看板唯一数据源，结构：`{ docs: 竞商文件库, applies: 报名项目, plans: 开行计划 }`。
  - 看板打开即从 `data.json` 加载，每 60 秒轮询一次；内容有变化自动刷新并提示。
  - 当前已抓取并内置 **旅游专列竞商文件**（北京局 / 上海局），报名项目与开行计划待本地导入。
- `index.html` —— 看板页面（GitHub Pages 入口）。
- `xlsx.full.min.js` —— 本地 Excel 导入/导出库（离线可用）。
- `crawler/` —— 国铁招商网旅游专列爬虫脚本。

## 本地更新后台数据（更新后全员实时可见）

1. 抓取最新旅游专列数据：
   ```bash
   python crawler/tender_crawler.py --tourism --cookie "你的浏览器Cookie"
   ```
2. 在看板内「导入抓取结果(含旅游专列)」入库，或本地编辑报名项目 / 开行计划。
3. 点看板顶栏 **「发布后台(data.json)」** 导出最新 `data.json`。
4. 将 `data.json` 提交并推送到本仓库：
   ```bash
   git add data.json
   git commit -m "更新竞商数据"
   git push
   ```
   GitHub Pages 自动重新发布，所有访客 60 秒内自动刷新。

## 本地预览

浏览器直接打开 `index.html` 即可（需同目录存在 `data.json`）。

## 竞商文件库清理

看板「竞商文件库」页提供 **「仅保留旅游专列」** 按钮，可一键清除非旅游专列记录。
