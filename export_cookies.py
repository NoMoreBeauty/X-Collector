#!/usr/bin/env python3
"""
从系统 Chrome 浏览器导出 X (Twitter) 的 Cookie

用法:
    python export_cookies.py

输出:
    data/browser_state.json (Playwright 兼容格式)
"""

import os
import json
import sqlite3
import shutil
import tempfile
from pathlib import Path
from datetime import datetime

# macOS Chrome Cookie 数据库路径
CHROME_COOKIE_PATH = os.path.expanduser(
    "~/Library/Application Support/Google/Chrome/Default/Cookies"
)

# 输出路径
OUTPUT_PATH = "data/browser_state.json"


def get_chrome_cookies(domain: str = ".x.com") -> list[dict]:
    """
    从 Chrome Cookie 数据库读取指定域名的 Cookie
    
    注意：需要先关闭 Chrome 浏览器
    """
    if not os.path.exists(CHROME_COOKIE_PATH):
        raise FileNotFoundError(f"Chrome Cookie 数据库不存在: {CHROME_COOKIE_PATH}")
    
    # 复制数据库到临时文件（因为 Chrome 可能锁定原文件）
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
        tmp_path = tmp.name
    
    try:
        shutil.copy2(CHROME_COOKIE_PATH, tmp_path)
        
        conn = sqlite3.connect(tmp_path)
        cursor = conn.cursor()
        
        # 查询 X 相关的 Cookie
        # Chrome 的 Cookie 存储格式：host_key 包含域名
        cursor.execute("""
            SELECT 
                host_key,
                name,
                value,
                path,
                expires_utc,
                is_secure,
                is_httponly,
                samesite
            FROM cookies 
            WHERE host_key LIKE ? OR host_key LIKE ?
        """, (f"%{domain}%", "%.twitter.com%"))
        
        cookies = []
        for row in cursor.fetchall():
            host_key, name, value, path, expires_utc, is_secure, is_httponly, samesite = row
            
            # 转换为 Playwright 格式
            cookie = {
                "name": name,
                "value": value,
                "domain": host_key,
                "path": path or "/",
                "expires": expires_utc / 1000000 - 11644473600 if expires_utc else -1,  # Chrome 时间戳转换
                "httpOnly": bool(is_httponly),
                "secure": bool(is_secure),
                "sameSite": ["None", "Lax", "Strict"][samesite] if samesite in [0, 1, 2] else "None"
            }
            cookies.append(cookie)
        
        conn.close()
        return cookies
        
    finally:
        os.unlink(tmp_path)


def save_playwright_state(cookies: list[dict], output_path: str = OUTPUT_PATH):
    """保存为 Playwright storage state 格式"""
    state = {
        "cookies": cookies,
        "origins": []
    }
    
    # 确保目录存在
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(state, f, indent=2)
    
    return output_path


def main():
    print("🍪 Chrome Cookie 导出工具")
    print("=" * 40)
    print()
    print("⚠️  请确保已完全关闭 Chrome 浏览器！")
    print()
    
    try:
        # 读取 Cookie
        print("📖 读取 Chrome Cookie 数据库...")
        cookies = get_chrome_cookies()
        
        if not cookies:
            print("❌ 未找到 X/Twitter 相关的 Cookie")
            print("   请确保你已在 Chrome 中登录 X")
            return
        
        print(f"✅ 找到 {len(cookies)} 个 Cookie")
        
        # 保存
        output_path = save_playwright_state(cookies)
        print(f"✅ 已保存到: {output_path}")
        print()
        print("🎉 完成！现在可以运行采集命令了：")
        print("   python main.py collect -u sama --no-headless")
        
    except FileNotFoundError as e:
        print(f"❌ {e}")
    except sqlite3.OperationalError as e:
        print(f"❌ 数据库访问错误: {e}")
        print("   请确保已完全关闭 Chrome 浏览器")
    except Exception as e:
        print(f"❌ 错误: {e}")


if __name__ == "__main__":
    main()
