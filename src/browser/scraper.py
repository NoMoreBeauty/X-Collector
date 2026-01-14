"""X (Twitter) 页面爬取器 - 使用 Playwright 浏览器自动化"""

import asyncio
import os
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import Optional
from playwright.async_api import async_playwright, Browser, Page, BrowserContext


# 默认浏览器状态存储路径
DEFAULT_STATE_PATH = "data/browser_state.json"

# macOS 系统 Chrome 用户数据目录
MACOS_CHROME_USER_DATA = os.path.expanduser(
    "~/Library/Application Support/Google/Chrome"
)


@dataclass
class ScraperConfig:
    """爬取器配置"""
    headless: bool = True
    scroll_times: int = 3
    scroll_delay: float = 2.0
    max_tweets_per_user: int = 20
    screenshots_path: str = "data/screenshots"
    viewport_width: int = 1280
    viewport_height: int = 900
    # 浏览器状态文件路径（用于保持登录）
    state_path: str = DEFAULT_STATE_PATH
    # 是否使用系统 Chrome（复用已登录状态）
    use_system_chrome: bool = False
    # Chrome 用户数据目录（仅 use_system_chrome=True 时有效）
    chrome_user_data_dir: str = MACOS_CHROME_USER_DATA
    # Chrome Profile 名称 (默认 "Default")
    chrome_profile: str = "Default"


@dataclass
class ScrapedUser:
    """爬取结果"""
    handle: str
    name: str
    screenshot_path: str
    scraped_at: datetime
    success: bool
    error: Optional[str] = None


class XScraper:
    """X (Twitter) 页面爬取器"""
    
    def __init__(self, config: ScraperConfig = None):
        self.config = config or ScraperConfig()
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self._playwright = None
    
    async def start(self, use_saved_state: bool = True):
        """
        启动浏览器
        
        Args:
            use_saved_state: 是否加载保存的浏览器状态（Cookie等）
        """
        self._playwright = await async_playwright().start()
        
        # 如果使用系统 Chrome（复用已登录状态）
        if self.config.use_system_chrome:
            await self._start_with_system_chrome()
        else:
            await self._start_with_playwright_browser(use_saved_state)
    
    async def _start_with_system_chrome(self):
        """使用系统 Chrome 的用户数据目录启动（复用登录状态）"""
        # 使用 launch_persistent_context 复用 Chrome 用户数据
        # 注意：需要先关闭正在运行的 Chrome
        user_data_dir = Path(self.config.chrome_user_data_dir) / self.config.chrome_profile
        
        self.context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=self.config.headless,
            viewport={
                "width": self.config.viewport_width,
                "height": self.config.viewport_height
            },
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
            ]
        )
        # persistent context 没有独立的 browser 对象
        self.browser = None
    
    async def _start_with_playwright_browser(self, use_saved_state: bool):
        """使用独立的 Playwright 浏览器启动"""
        # 添加反检测参数
        self.browser = await self._playwright.chromium.launch(
            headless=self.config.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )
        
        # 检查是否有保存的状态
        state_path = Path(self.config.state_path)
        storage_state = None
        if use_saved_state and state_path.exists():
            storage_state = str(state_path)
        
        # 使用真实的 User-Agent
        user_agent = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        
        # 创建浏览器上下文
        self.context = await self.browser.new_context(
            viewport={
                "width": self.config.viewport_width,
                "height": self.config.viewport_height
            },
            locale="en-US",
            timezone_id="America/Los_Angeles",
            storage_state=storage_state,
            user_agent=user_agent,
        )
        
        # 注入反检测脚本
        await self.context.add_init_script("""
            // 隐藏 webdriver 属性
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // 修改 plugins 长度
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // 修改 languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
        """)
        
        # 设置额外的请求头
        await self.context.set_extra_http_headers({
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })
    
    async def save_state(self):
        """保存浏览器状态（Cookie 等）到文件"""
        if self.context:
            state_path = Path(self.config.state_path)
            state_path.parent.mkdir(parents=True, exist_ok=True)
            await self.context.storage_state(path=str(state_path))
            return str(state_path)
        return None
    
    async def stop(self):
        """关闭浏览器"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()
    
    async def scrape_user(self, handle: str, name: str = "") -> ScrapedUser:
        """
        爬取单个用户的推文页面
        
        Args:
            handle: X 用户名 (不含 @)
            name: 显示名 (可选)
            
        Returns:
            ScrapedUser: 爬取结果
        """
        if not self.context:
            raise RuntimeError("Browser not started. Call start() first.")
        
        page = await self.context.new_page()
        screenshot_path = ""
        
        try:
            # 访问用户主页
            url = f"https://x.com/{handle}"
            # 使用 domcontentloaded 而非 networkidle，更快
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # 等待页面渲染
            await asyncio.sleep(3)
            
            # 尝试等待推文加载
            await self._wait_for_tweets(page)
            
            # 检查是否遇到登录墙，尝试触发内容
            login_wall = await page.query_selector('[data-testid="loginButton"]')
            if login_wall:
                await page.evaluate("window.scrollBy(0, 300)")
                await asyncio.sleep(1)
                await page.evaluate("window.scrollTo(0, 0)")
                await asyncio.sleep(1)
            
            # 截图（内部会处理滚动和拼接）
            screenshot_path = await self._take_screenshot(page, handle)
            
            return ScrapedUser(
                handle=handle,
                name=name,
                screenshot_path=screenshot_path,
                scraped_at=datetime.now(),
                success=True
            )
            
        except Exception as e:
            # 即使出错也尝试截图保存当前状态
            try:
                if not screenshot_path:
                    screenshot_path = await self._take_screenshot(page, f"{handle}_error")
            except:
                pass
            
            return ScrapedUser(
                handle=handle,
                name=name,
                screenshot_path=screenshot_path,
                scraped_at=datetime.now(),
                success=False,
                error=str(e)
            )
        finally:
            await page.close()
    
    async def scrape_users(self, users: list[dict]) -> list[ScrapedUser]:
        """
        批量爬取多个用户
        
        Args:
            users: 用户列表 [{"handle": "...", "name": "..."}]
            
        Returns:
            list[ScrapedUser]: 爬取结果列表
        """
        results = []
        for user in users:
            result = await self.scrape_user(
                handle=user.get("handle", ""),
                name=user.get("name", "")
            )
            results.append(result)
            # 添加随机延迟，避免被检测
            await asyncio.sleep(2 + (hash(user.get("handle", "")) % 3))
        
        return results
    
    async def _wait_for_tweets(self, page: Page, timeout: int = 10000):
        """等待推文元素加载"""
        try:
            # 等待推文容器出现
            await page.wait_for_selector(
                'article[data-testid="tweet"]',
                timeout=timeout
            )
        except Exception:
            # 可能是私密账户或不存在
            pass
    
    async def _scroll_page(self, page: Page):
        """滚动页面加载更多内容（已弃用，使用分段截图）"""
        for _ in range(self.config.scroll_times):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await asyncio.sleep(self.config.scroll_delay)
    
    async def _take_screenshot(self, page: Page, handle: str) -> str:
        """
        分段截图并拼接
        
        策略：
        1. 先截取首屏
        2. 小幅滚动，截取下一段（有重叠区域）
        3. 重复直到达到滚动上限
        4. 使用 PIL 拼接所有截图
        """
        from PIL import Image
        import io
        
        # 确保截图目录存在
        screenshots_dir = Path(self.config.screenshots_path)
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{handle}_{timestamp}.png"
        filepath = screenshots_dir / filename
        
        # 获取视口尺寸
        viewport_height = self.config.viewport_height
        scroll_step = int(viewport_height * 0.7)  # 每次滚动 70%，保留 30% 重叠
        max_scroll_pixels = viewport_height * self.config.scroll_times  # 最大滚动距离
        
        screenshots = []
        current_scroll = 0
        
        # 回到页面顶部
        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(0.5)
        
        while current_scroll < max_scroll_pixels:
            # 等待当前视口内容渲染
            await asyncio.sleep(0.3)
            
            # 截取当前视口
            screenshot_bytes = await page.screenshot()
            img = Image.open(io.BytesIO(screenshot_bytes))
            screenshots.append((current_scroll, img))
            
            # 检查是否已到达页面底部
            is_at_bottom = await page.evaluate(
                "window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 10"
            )
            if is_at_bottom:
                break
            
            # 滚动到下一段
            current_scroll += scroll_step
            await page.evaluate(f"window.scrollTo(0, {current_scroll})")
            await asyncio.sleep(self.config.scroll_delay)
        
        # 拼接截图
        if len(screenshots) == 1:
            # 只有一张截图，直接保存
            screenshots[0][1].save(str(filepath))
        else:
            # 多张截图需要拼接
            final_image = self._stitch_screenshots(screenshots, viewport_height, scroll_step)
            final_image.save(str(filepath))
        
        return str(filepath)
    
    def _stitch_screenshots(
        self, 
        screenshots: list[tuple[int, 'Image.Image']], 
        viewport_height: int,
        scroll_step: int
    ) -> 'Image.Image':
        """
        拼接多张截图
        
        Args:
            screenshots: [(scroll_position, image), ...]
            viewport_height: 视口高度
            scroll_step: 滚动步长
        """
        from PIL import Image
        
        if not screenshots:
            raise ValueError("No screenshots to stitch")
        
        # 获取第一张图片的宽度
        width = screenshots[0][1].width
        
        # 计算最终图片的高度
        # 第一张完整 + 后续每张只取 scroll_step 高度的部分
        total_height = viewport_height + scroll_step * (len(screenshots) - 1)
        
        # 创建最终图片
        final_image = Image.new('RGB', (width, total_height))
        
        # 粘贴第一张（完整）
        final_image.paste(screenshots[0][1], (0, 0))
        
        # 粘贴后续截图（只取下半部分，去掉重叠区域）
        overlap = viewport_height - scroll_step
        for i, (scroll_pos, img) in enumerate(screenshots[1:], 1):
            # 从每张截图中裁剪掉顶部重叠区域
            cropped = img.crop((0, overlap, width, viewport_height))
            paste_y = viewport_height + scroll_step * (i - 1)
            final_image.paste(cropped, (0, paste_y))
        
        return final_image
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        await self.stop()


# 便捷函数
async def scrape_single_user(handle: str, headless: bool = True) -> ScrapedUser:
    """快速爬取单个用户"""
    config = ScraperConfig(headless=headless)
    async with XScraper(config) as scraper:
        return await scraper.scrape_user(handle)

