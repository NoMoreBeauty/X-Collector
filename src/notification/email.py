"""邮件通知器 - 发送报告邮件"""

import asyncio
from dataclasses import dataclass
from typing import Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
import aiosmtplib


@dataclass
class EmailConfig:
    """邮件配置"""
    smtp_host: str
    smtp_port: int = 587
    use_tls: bool = True
    username: str = ""
    password: str = ""
    from_address: str = ""
    to_addresses: list[str] = None
    
    def __post_init__(self):
        if self.to_addresses is None:
            self.to_addresses = []


class EmailNotifier:
    """邮件通知器"""
    
    def __init__(self, config: EmailConfig):
        self.config = config
    
    async def send_report(
        self,
        subject: str,
        body: str,
        attachment_path: Optional[str] = None
    ) -> bool:
        """
        发送报告邮件
        
        Args:
            subject: 邮件主题
            body: 邮件正文 (支持 HTML)
            attachment_path: 附件路径 (可选)
            
        Returns:
            bool: 是否发送成功
        """
        if not self.config.to_addresses:
            print("No recipients configured")
            return False
        
        try:
            # 创建邮件
            # 创建邮件
            msg = MIMEMultipart()
            
            # 使用 Header 编码非 ASCII字符
            from email.header import Header
            
            # 设置显示名称: "X-Daily-Report <email@address.com>"
            # 注意: Header 只编码显示名称部分，不编码邮箱地址
            display_name = "祝乙留环球时报"
            encoded_name = Header(display_name, 'utf-8').encode()
            sender = f"{encoded_name} <{self.config.from_address}>"
            
            msg["From"] = sender
            msg["To"] = ", ".join(self.config.to_addresses)
            msg["Subject"] = Header(subject, 'utf-8')
            
            # 添加正文
            msg.attach(MIMEText(body, "html", "utf-8"))
            
            # 添加附件
            if attachment_path and Path(attachment_path).exists():
                with open(attachment_path, "rb") as f:
                    attachment = MIMEBase("application", "octet-stream")
                    attachment.set_payload(f.read())
                    encoders.encode_base64(attachment)
                    attachment.add_header(
                        "Content-Disposition",
                        f"attachment; filename={Path(attachment_path).name}"
                    )
                    msg.attach(attachment)
            
            # 根据端口判断 TLS 模式
            use_tls = False
            start_tls = False
            
            if self.config.smtp_port in [465, 994]:
                use_tls = True  # 隐式 SSL
                start_tls = False
            elif self.config.use_tls:
                use_tls = False
                start_tls = True  # 显式 STARTTLS
            
            # 发送邮件
            await aiosmtplib.send(
                msg,
                hostname=self.config.smtp_host,
                port=self.config.smtp_port,
                use_tls=use_tls,
                start_tls=start_tls,
                username=self.config.username,
                password=self.config.password
            )
            
            return True
            
        except Exception as e:
            print(f"Failed to send email: {e}")
            return False
    
    async def send_daily_report(
        self,
        tweets_count: int,
        users_count: int,
        summary: str,
        report_path: str
    ) -> bool:
        """
        发送每日报告邮件
        
        Args:
            tweets_count: 推文数量
            users_count: 用户数量
            summary: AI 摘要
            report_path: 完整报告文件路径
        """
        import markdown
        from datetime import datetime
        
        # 将 Markdown 转换为 HTML (启用表格扩展)
        summary_html = markdown.markdown(summary, extensions=['tables'])
        
        date_str = datetime.now().strftime("%Y-%m-%d")
        subject = f"📱 X 动态日报 - {date_str}"
        
        body = f"""
        <html>
        <head>
            <style>
                table {{
                    border-collapse: collapse;
                    width: 100%;
                    margin: 10px 0;
                    font-size: 14px;
                }}
                th, td {{
                    border: 1px solid #e1e8ed;
                    padding: 8px;
                    text-align: left;
                }}
                th {{
                    background-color: #f5f8fa;
                    font-weight: bold;
                    color: #1da1f2;
                }}
                tr:nth-child(even) {{
                    background-color: #f9f9f9;
                }}
            </style>
        </head>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #1da1f2;">📱 X 动态日报</h2>
            <p style="color: #666;">日期: {date_str}</p>
            
            <div style="background: #f5f5f5; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <h3 style="margin-top: 0;">📊 采集统计</h3>
                <ul>
                    <li>监控用户: {users_count} 人</li>
                    <li>采集推文: {tweets_count} 条</li>
                </ul>
            </div>
            
            <div style="background: #ffffff; padding: 15px; border: 1px solid #e1e8ed; border-radius: 8px; margin: 20px 0;">
                <h3 style="margin-top: 0; color: #1da1f2;">🔥 热点摘要</h3>
                {summary_html}
            </div>
            
            <p style="color: #666; font-size: 12px;">
                完整报告请查看附件。
                <br><br>
                此邮件由 X Information Collector 自动发送。
            </p>
        </body>
        </html>
        """
        
        return await self.send_report(subject, body, report_path)
