#!/usr/bin/env python3
"""
从 cookies.txt 配置文件加载 Cookie 并生成 Playwright state 文件

用法:
    1. 编辑 config/cookies.txt 填写你的 Cookie
    2. 运行: python load_cookies.py
    3. 运行采集: python main.py collect
"""

import json
from pathlib import Path

COOKIES_FILE = "config/cookies.txt"
OUTPUT_FILE = "data/browser_state.json"


def parse_cookies_file(filepath: str) -> list[dict]:
    """解析 cookies.txt 文件"""
    cookies = []
    
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            # 跳过注释和空行
            if not line or line.startswith('#'):
                continue
            
            # 解析 name=value 格式
            if '=' in line:
                name, value = line.split('=', 1)
                name = name.strip()
                value = value.strip()
                
                if name and value and not value.startswith('你的'):
                    cookies.append({
                        "name": name,
                        "value": value,
                        "domain": ".x.com",
                        "path": "/",
                        "expires": -1,
                        "httpOnly": True,
                        "secure": True,
                        "sameSite": "None"
                    })
    
    return cookies


def save_state(cookies: list[dict], output_path: str):
    """保存为 Playwright state 格式"""
    state = {
        "cookies": cookies,
        "origins": []
    }
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(state, f, indent=2)


def main():
    print("🍪 Cookie 加载工具")
    print("=" * 40)
    
    if not Path(COOKIES_FILE).exists():
        print(f"❌ 找不到配置文件: {COOKIES_FILE}")
        print("   请先创建并填写 Cookie")
        return
    
    cookies = parse_cookies_file(COOKIES_FILE)
    
    if not cookies:
        print("❌ 没有找到有效的 Cookie")
        print("   请编辑 config/cookies.txt 填写你的 Cookie")
        return
    
    print(f"✅ 读取到 {len(cookies)} 个 Cookie:")
    for c in cookies:
        print(f"   - {c['name']}")
    
    save_state(cookies, OUTPUT_FILE)
    print(f"\n✅ 已保存到: {OUTPUT_FILE}")
    print("\n🎉 完成！现在可以运行采集命令：")
    print("   python main.py collect -u sama --no-headless")


if __name__ == "__main__":
    main()
