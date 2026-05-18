#!/usr/bin/env python3
"""
X Information Collector - CLI 入口

用法:
    python main.py collect           # 采集所有订阅用户
    python main.py collect -u elonmusk  # 采集指定用户
    python main.py report            # 生成今日报告
    python main.py daemon            # 启动守护进程（每日定时采集）
    python main.py list              # 查看订阅列表
"""

import asyncio
from typing import Optional, List
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="x-collector",
    help="X (Twitter) 信息收集智能体",
    add_completion=False
)
console = Console()


@app.command()
def collect(
    user: Optional[List[str]] = typer.Option(
        None, "-u", "--user",
        help="指定要采集的用户 (可多次使用)"
    ),
    headless: bool = typer.Option(
        True, "--headless/--no-headless",
        help="是否使用无头浏览器模式"
    ),
    system_chrome: bool = typer.Option(
        False, "--system-chrome",
        help="使用系统 Chrome 的登录状态 (需要先关闭 Chrome)"
    ),
    report: bool = typer.Option(
        True, "--report/--no-report",
        help="采集后是否自动生成报告"
    ),
    notify: bool = typer.Option(
        False, "--notify",
        help="采集后是否发送邮件通知"
    )
):
    """
    执行推文采集任务
    
    默认采集所有订阅用户，可通过 -u 参数指定特定用户
    使用 --system-chrome 可复用系统 Chrome 的登录状态
    """
    from src.collector import Collector
    from src.config import Config
    
    async def run():
        config = Config()
        # 覆盖配置
        config._config.setdefault("collector", {})["headless"] = headless
        config._config["collector"]["use_system_chrome"] = system_chrome
        
        # 如果指定了 --notify，强制开启邮件
        if notify:
            config._config.setdefault("email", {})["enabled"] = True
        
        if system_chrome:
            console.print("[cyan]📌 使用系统 Chrome 登录状态[/cyan]")
            console.print("[dim]注意：请确保已关闭系统 Chrome 浏览器[/dim]\n")
        
        collector = Collector(config)
        
        # 采集
        result = await collector.collect(user)
        
        if result.status == "no_users":
            return
        
        console.print(f"\n[bold]采集完成:[/bold]")
        console.print(f"  ✅ 成功: {result.success_count}")
        console.print(f"  ❌ 失败: {result.error_count}")
        console.print(f"  📝 新推文: {result.tweets_count}")
        
        # 生成报告（同时拿到 summary，避免后续重复调用 LLM）
        if report:
            report_path, summary = await collector.generate_report()
            
            # 发送通知
            if notify and report_path:
                await collector.send_notification(report_path, summary=summary)
    
    asyncio.run(run())


@app.command()
def report(
    summary: bool = typer.Option(
        True, "--summary/--no-summary",
        help="是否包含 AI 摘要"
    )
):
    """
    生成今日推文报告
    """
    from src.collector import Collector
    
    async def run():
        collector = Collector()
        report_path, _ = await collector.generate_report(with_summary=summary)
        if report_path:
            console.print(f"\n[green]📄 报告已生成: {report_path}[/green]")
    
    asyncio.run(run())


@app.command()
def daemon(
    time: str = typer.Option(
        None, "-t", "--time",
        help="每日采集时间 (格式: HH:MM，如 08:00)"
    )
):
    """
    启动守护进程，每日定时采集
    
    按 Ctrl+C 停止
    """
    from src.config import Config
    from src.scheduler import Scheduler
    from src.scheduler.jobs import parse_time
    from src.collector import run_full_pipeline
    
    config = Config()
    
    # 解析时间
    time_str = time or config.scheduler_time
    hour, minute = parse_time(time_str)
    
    # 创建调度器
    scheduler = Scheduler(timezone=config.scheduler_timezone)
    scheduler.schedule_daily_collection(run_full_pipeline, hour, minute)
    
    console.print(f"\n[bold cyan]🚀 守护进程已启动[/bold cyan]")
    console.print(f"   下次采集: {scheduler.get_next_run_time()}")
    console.print(f"   按 Ctrl+C 停止\n")
    
    try:
        scheduler.start()
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        scheduler.stop()
        console.print("\n[yellow]👋 已停止[/yellow]")


@app.command("list")
def list_users():
    """
    查看订阅用户列表
    """
    from src.config import load_subscriptions
    
    users = load_subscriptions()
    
    if not users:
        console.print("[yellow]⚠️ 未配置任何订阅用户[/yellow]")
        console.print("请编辑 config/subscriptions.yaml 添加用户")
        return
    
    table = Table(title="📋 订阅用户列表")
    table.add_column("用户名", style="cyan")
    table.add_column("显示名", style="green")
    table.add_column("分类")
    table.add_column("优先级")
    
    for user in users:
        table.add_row(
            f"@{user.get('handle', '')}",
            user.get("name", ""),
            user.get("category", "-"),
            user.get("priority", "medium")
        )
    
    console.print(table)
    console.print(f"\n共 {len(users)} 个用户")


@app.command()
def status():
    """
    查看最近一次采集状态
    """
    from src.storage import Database
    
    async def run():
        db = Database()
        await db.connect()
        
        try:
            run_info = await db.get_latest_run()
            
            if not run_info:
                console.print("[yellow]⚠️ 暂无采集记录[/yellow]")
                return
            
            console.print("\n[bold]📊 最近一次采集:[/bold]")
            console.print(f"  开始时间: {run_info.started_at}")
            console.print(f"  完成时间: {run_info.completed_at or '进行中'}")
            console.print(f"  状态: {run_info.status}")
            console.print(f"  用户数: {run_info.users_count}")
            console.print(f"  推文数: {run_info.tweets_count}")
            console.print(f"  成功: {run_info.success_count}")
            console.print(f"  失败: {run_info.error_count}")
            
        finally:
            await db.close()
    
    asyncio.run(run())


@app.command()
def init():
    """
    初始化项目配置
    """
    from pathlib import Path
    import shutil
    
    # 创建必要目录
    dirs = ["data", "data/screenshots", "reports", "logs", "config"]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
        console.print(f"  📁 创建目录: {d}")
    
    # 复制配置文件
    example_config = Path("config/config.example.yaml")
    config_file = Path("config/config.yaml")
    
    if example_config.exists() and not config_file.exists():
        shutil.copy(example_config, config_file)
        console.print("  📄 创建配置文件: config/config.yaml")
    
    # 复制环境变量文件
    example_env = Path(".env.example")
    env_file = Path(".env")
    
    if example_env.exists() and not env_file.exists():
        shutil.copy(example_env, env_file)
        console.print("  📄 创建环境变量文件: .env")
    
    console.print("\n[green]✅ 初始化完成！[/green]")
    console.print("\n下一步:")
    console.print("  1. 编辑 .env 填写 API Key")
    console.print("  2. 编辑 config/config.yaml 配置参数")
    console.print("  3. 编辑 config/subscriptions.yaml 添加订阅用户")
    console.print("  4. 运行 python main.py login 登录 X 账号")
    console.print("  5. 运行 python main.py collect 开始采集")


@app.command()
def login():
    """
    登录 X 账号并保存 Cookie
    
    打开浏览器窗口，手动完成登录后按回车保存状态。
    保存后，后续采集将自动使用登录状态。
    """
    from src.browser.scraper import XScraper, ScraperConfig
    
    async def run():
        console.print("\n[bold cyan]🔐 X 账号登录[/bold cyan]")
        console.print("即将打开浏览器，请手动完成以下操作:")
        console.print("  1. 登录你的 X 账号")
        console.print("  2. 登录成功后，回到终端按回车")
        console.print()
        
        config = ScraperConfig(headless=False)  # 必须非无头模式
        scraper = XScraper(config)
        
        try:
            # 启动浏览器（不加载已保存状态）
            await scraper.start(use_saved_state=False)
            
            # 打开 X 登录页面
            page = await scraper.context.new_page()
            await page.goto("https://x.com/login", wait_until="domcontentloaded")
            
            console.print("[yellow]⏳ 浏览器已打开，请登录你的 X 账号...[/yellow]")
            console.print("[dim]登录完成后，请回到终端按回车键[/dim]\n")
            
            # 等待用户按回车
            input("按回车键保存登录状态...")
            
            # 保存状态
            state_path = await scraper.save_state()
            
            if state_path:
                console.print(f"\n[green]✅ 登录状态已保存到: {state_path}[/green]")
                console.print("[green]之后的采集将自动使用此登录状态[/green]")
            else:
                console.print("\n[red]❌ 保存失败[/red]")
                
        finally:
            await scraper.stop()
    
    asyncio.run(run())


@app.command()
def logout():
    """
    清除保存的登录状态
    """
    from pathlib import Path
    from src.browser.scraper import DEFAULT_STATE_PATH
    
    state_path = Path(DEFAULT_STATE_PATH)
    
    if state_path.exists():
        state_path.unlink()
        console.print("[green]✅ 登录状态已清除[/green]")
    else:
        console.print("[yellow]⚠️ 没有保存的登录状态[/yellow]")


if __name__ == "__main__":
    app()
