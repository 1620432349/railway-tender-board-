# -*- coding: utf-8 -*-
"""
国铁招商网 · 竞商文件抓取脚本（支持旅游专列模式）
================================================
数据源：国铁招商网 https://zs.95306.cn （Vue SPA）

两种模式：
  1) 公开竞商大厅模式（默认）
     接口：GET /api/quote/homeShow/page（无需登录）
     数据：各局正在招商的项目（房屋出租/广告/土地/站车商业）
     限制：不含旅游列车分类

  2) 旅游专列模式（--tourism + --cookie）
     接口：POST /gtzs-mhqd/api/notice/selectHomeNotice（需登录Cookie）
     数据：dealType=36 的旅游列车竞商公告全量列表
     认证：Cookie AlteonPgtzstjfx（从浏览器 DevTools 复制）

用法：
    python tender_crawler.py                          # 公开竞商大厅模式
    python tender_crawler.py --out out.json           # 指定输出文件
    python tender_crawler.py --demo                   # 离线样例（不联网）

    python tender_crawler.py --tourism --cookie "AlteonPgtzstjfx=xxx"   # 旅游专列模式
    python tender_crawler.py --tourism --cookie "AlteonPgtzstjfx=xxx" --all   # 全量(不限路局)

字段映射（与看板 importCrawl 对齐）：
    bureau / docTitle / docNo / docUrl / publishDate / applyDeadline /
    depositRequire / routeScope / sourceSite / crawlTime /
    projId / dealType / noticeType / notStatus         # 新增字段
"""

import argparse, json, ssl, sys, time, urllib.request, urllib.error
from datetime import datetime

SITE = "https://zs.95306.cn"

# ============================================================
# 两个接口
# ============================================================
PUBLIC_API    = SITE + "/api/quote/homeShow/page"          # 公开竞商大厅（GET）
TOURISM_API   = SITE + "/gtzs-mhqd/api/notice/selectHomeNotice"  # 旅游专列（POST，需Cookie）
DETAIL_URL    = SITE + "/#/ann-detail?id="                  # 公告详情页

# ============================================================
# 目标路局白名单（9 局）— 用于公开模式过滤 & 旅游模式统计
# ============================================================
TARGET_BUREAUS = ["上海局", "北京局", "广州局", "南宁局", "武汉局",
                  "郑州局", "南昌局", "乌鲁木齐局", "西安局"]

# marketName（旅游模式返回的全称）-> 短名 映射
MARKET_NAME_MAP = {
    "上海局集团公司":     "上海局",
    "北京局集团公司":     "北京局",
    "广州局集团公司":     "广州局",
    "南宁局集团公司":     "南宁局",
    "武汉局集团公司":     "武汉局",
    "郑州局集团公司":     "郑州局",
    "南昌局集团公司":     "南昌局",
    "乌鲁木齐局集团公司": "乌鲁木齐局",
    "西安局集团公司":     "西安局",
    "哈尔滨局集团公司":   "哈尔滨局",   # 非目标但保留
}

# 招商单位名 -> 路局 关键字识别（公开模式用）
BUREAU_KEYWORDS = {
    "上海局":     ["上海局", "上海铁路", "安徽铁道", "安徽铁路", "江苏", "浙江", "华铁", "欣逸", "徐州"],
    "北京局":     ["北京局", "京铁"],
    "广州局":     ["广铁", "广州局", "广东", "湖南", "海南"],
    "南宁局":     ["南宁局", "广西", "宁铁"],
    "武汉局":     ["武汉局"],
    "郑州局":     ["郑州局"],
    "南昌局":     ["南昌局", "江西", "南铁", "赣铁"],
    "乌鲁木齐局": ["乌鲁木齐局", "新疆"],
    "西安局":     ["西安局", "陕铁"],
}

def guess_bureau(name):
    """从招商单位名识别路局，命中白名单才返回，否则 None。"""
    if not name:
        return None
    for bureau, kws in BUREAU_KEYWORDS.items():
        for kw in kws:
            if kw in name:
                return bureau
    return None

def normalize_bureau(market_name):
    """将 marketName 全称映射为短名，命中白名单才返回。"""
    if not market_name:
        return None
    short = MARKET_NAME_MAP.get(market_name)
    if short and short in TARGET_BUREAUS:
        return short
    # 也尝试关键字匹配
    for bureau, kws in BUREAU_KEYWORDS.items():
        for kw in kws:
            if kw in market_name:
                return bureau
    return None


# ============================================================
# 模式1：公开竞商大厅（GET，无需登录）
# ============================================================
def fetch_public_page(current, size=100):
    url = f"{PUBLIC_API}?current={current}&size={size}"
    req = urllib.request.Request(url, method="GET")
    req.add_header("User-Agent", "Mozilla/5.0")
    req.add_header("Accept", "application/json, text/plain, */*")
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
            return json.loads(r.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"接口返回 {e.code}：{e.read().decode('utf-8','ignore')[:160]}")
    except Exception as e:
        raise RuntimeError(f"请求失败：{e}")

def to_doc_public(rec):
    """公开模式：homeShow 字段 → 标准格式"""
    name = rec.get("createUnitName", "") or ""
    bureau = guess_bureau(name)
    if not bureau:
        return None
    proj_id = rec.get("projId", "") or rec.get("id", "")
    return {
        "bureau": bureau,
        "docTitle": rec.get("proName", "") or rec.get("packName", ""),
        "docNo": rec.get("purId", "") or rec.get("packNoStr", ""),
        "docUrl": DETAIL_URL + proj_id if proj_id else "",
        "publishDate": "",
        "applyDeadline": rec.get("quoteEndtime", "") or rec.get("quoteStarttime", ""),
        "bidOpenDate": "",
        "depositRequire": 0,
        "routeScope": rec.get("packName", "") or rec.get("dealTypeName", ""),
        "sourceSite": "国铁招商网·竞商大厅",
        "crawlTime": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "projId": proj_id,
        "dealType": "",
        "dealTypeName": rec.get("dealTypeName", ""),
        "noticeType": "",
        "notStatus": "",
    }

def crawl_public():
    """公开竞商大厅模式：翻页抓取全部"""
    out, seen, page = [], set(), 1
    while True:
        obj = fetch_public_page(page)
        recs = (obj.get("data", {}) or {}).get("records") or []
        if not recs:
            break
        for r in recs:
            d = to_doc_public(r)
            if not d:
                continue
            key = (d["docNo"] or "") + "|" + d["docTitle"]
            if key in seen:
                continue
            seen.add(key)
            out.append(d)
        if len(recs) < 100:
            break
        page += 1
        if page > 50:
            break
        time.sleep(0.3)
    return out


# ============================================================
# 模式2：旅游专列（POST，需 Cookie）
# ============================================================
def fetch_tourism_page(cookie, page=1, size=100):
    """调用 selectHomeNotice 接口，dealType=36 筛选旅游列车"""
    url = TOURISM_API
    payload = json.dumps({
        "testRun": "3",
        "attractWay": "",
        "dealType": "36",          # ★ 旅游列车
        "isHome": "0",
        "marketId": "",
        "noticeCondition": "1",
        "noticeType": "",            # 不限公告类型（01公告+02变更都要）
        "page": page,
        "size": size,
        "str": "",
        "type": "1",
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json;charset=UTF-8")
    req.add_header("Accept", "application/json, text/plain, */*")
    req.add_header("Cookie", cookie)
    req.add_header("User-Agent", "Mozilla/5.0")
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
            return json.loads(r.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")[:200]
        raise RuntimeError(f"接口返回 {e.code}：{body}")
    except Exception as e:
        raise RuntimeError(f"请求失败：{e}")

def to_doc_tourism(rec):
    """旅游模式：selectHomeNotice 字段 → 标准格式"""
    market_name = rec.get("marketName", "") or ""
    bureau = normalize_bureau(market_name)
    proj_id = rec.get("projId", "") or ""
    # 从标题提取线路信息
    title = rec.get("notTitle", "") or ""
    return {
        "bureau": bureau or market_name,       # 未命中白名单也保留原名
        "docTitle": title,
        "docNo": rec.get("id", ""),            # 用公告ID作为编号
        "docUrl": DETAIL_URL + proj_id if proj_id else "",
        "publishDate": rec.get("createTime", ""),
        "applyDeadline": "",                    # 此接口不返回截止日期
        "bidOpenDate": "",
        "depositRequire": 0,
        "routeScope": title,                    # 标题本身含线路信息
        "sourceSite": "国铁招商网·旅游专列",
        "crawlTime": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "projId": proj_id,
        "dealType": rec.get("dealType", ""),      # "36"
        "dealTypeName": rec.get("dealTypeName", ""),  # "旅游列车"
        "noticeType": rec.get("noticeType", ""),    # "01"=公告 "02"=变更
        "noticeTypeName": rec.get("noticeTypeName", ""),
        "notStatus": rec.get("notStatus", ""),
        "marketName": market_name,
        "updateTime": rec.get("updateTime", ""),
    }

def crawl_tourism(cookie, allow_all=False):
    """
    旅游专列模式：一次性请求（size=500 足够，通常 totalPage=1）
    allow_all=True 时不过滤路局，返回全部
    """
    print(f"正在抓取旅游专列数据（Cookie 认证）…")
    obj = fetch_tourism_page(cookie, page=1, size=500)
    recs = obj.get("dataList", [])
    total = obj.get("totalCount", len(recs))

    out, seen = [], set()
    for r in recs:
        d = to_doc_tourism(r)
        # 路局过滤（除非 allow_all）
        if not allow_all:
            if d["bureau"] not in TARGET_BUREAUS:
                continue
        key = d["docNo"] + "|" + d["docTitle"]
        if key in seen:
            continue
        seen.add(key)
        out.append(d)

    print(f"接口返回 {total} 条，筛选后 {len(out)} 条")
    return out


# ============================================================
# 离线样例（--demo，不联网）
# ============================================================
def demo_data():
    today = datetime.now().strftime("%Y-%m-%d")
    ct = datetime.now().strftime("%Y-%m-%d %H:%M")
    return [
        {"bureau":"上海局","docTitle":"上海局2026年10月兰新客专线、额济纳线旅游列车第1次竞价项目公告",
         "docNo":"demo001","docUrl":DETAIL_URL+"demo1","publishDate":"2026-03-30 09:45:35",
         "applyDeadline":"","bidOpenDate":"","depositRequire":0,
         "routeScope":"兰新客专线、额济纳线","sourceSite":"国铁招商网·旅游专列","crawlTime":ct,
         "projId":"demo-p1","dealType":"36","dealTypeName":"旅游列车","noticeType":"01","notStatus":"10"},
        {"bureau":"北京局","docTitle":"北京局2026年9月兰新客专线、兰新格库线、漠河线、额济纳旅游列车三轮竞价项目",
         "docNo":"demo002","docUrl":DETAIL_URL+"demo2","publishDate":"2026-06-24 17:47:16",
         "applyDeadline":"","bidOpenDate":"","depositRequire":0,
         "routeScope":"兰新客专线、格库线、漠河线、额济纳","sourceSite":"国铁招商网·旅游专列","crawlTime":ct,
         "projId":"demo-p2","dealType":"36","dealTypeName":"旅游列车","noticeType":"01","notStatus":"10"},
        {"bureau":"哈尔滨局","docTitle":"哈尔滨局2026年10月兰新客专线、额济纳线旅游列车第1次竞价项目公告",
         "docNo":"demo003","docUrl":DETAIL_URL+"demo3","publishDate":"2026-03-27 10:01:39",
         "applyDeadline":"","bidOpenDate":"","depositRequire":0,
         "routeScope":"兰新客专线、额济纳线","sourceSite":"国铁招商网·旅游专列","crawlTime":ct,
         "projId":"demo-p3","dealType":"36","dealTypeName":"旅游列车","noticeType":"01","notStatus":"10"},
    ]


# ============================================================
# 主流程
# ============================================================
def main():
    ap = argparse.ArgumentParser(description="国铁招商网竞商文件抓取（支持旅游专列模式）",
                                formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog="""
示例：
  # 公开竞商大厅（无需登录）
  python tender_crawler.py

  # 旅游专列模式（需要浏览器 Cookie）
  python tender_crawler.py --tourism --cookie "AlteonPgtzstjxx=你的token值"

  # 旅游专列 + 输出指定文件
  python tender_crawler.py --tourism --cookie "xxx" --out tourism.json

  # 离线测试
  python tender_crawler.py --demo
                                """)
    ap.add_argument("--demo", action="store_true", help="离线样例模式（不联网）")
    ap.add_argument("--tourism", action="store_true", help="旅游专列模式（需配合 --cookie）")
    ap.add_argument("--cookie", default="", help="登录 Cookie（从浏览器 DevTools → Network → Request Headers → Cookie 复制）")
    ap.add_argument("--all", action="store_true", help="旅游模式下返回全部路局（不过滤白名单）")
    ap.add_argument("--out", default="国铁招商网_实时抓取.json", help="输出 JSON 路径")
    args = ap.parse_args()

    if args.demo:
        data = demo_data()
        print(f"[demo] 生成样例 {len(data)} 条（不联网）")

    elif args.tourism:
        if not args.cookie:
            print("❌ 旅游专列模式需要 --cookie 参数")
            print("   获取方式：浏览器登录 zs.95306.cn → F12 → Network → 刷新页面")
            print("   → 点击任意请求 → Headers → 找到 Cookie: AlteonPgtzstjfx=xxx")
            print("   → 复制完整 Cookie 值作为 --cookie 参数")
            sys.exit(1)
        try:
            data = crawl_tourism(args.cookie, allow_all=args.all)
        except RuntimeError as e:
            print(f"❌ 抓取失败：{e}")
            print("   可能原因：Cookie 过期 → 重新登录网站获取新 Cookie")
            sys.exit(1)

    else:
        print("正在抓取国铁招商网竞商大厅（公开接口，无需登录）…")
        try:
            data = crawl_public()
        except RuntimeError as e:
            print(f"❌ 抓取失败：{e}")
            sys.exit(1)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ 已写出 {len(data)} 条 → {args.out}")

    # 路局分布
    dist = {}
    for d in data:
        dist[d["bureau"]] = dist.get(d["bureau"], 0) + 1
    print(f"   路局分布：{dict(sorted(dist.items()))}")

    # 如果是旅游模式，额外显示来源标识
    if args.tourism:
        types = {}
        for d in data:
            t = d.get("dealTypeName", "未知")
            types[t] = types.get(t, 0) + 1
        print(f"   交易类型：{types}")

if __name__ == "__main__":
    main()
