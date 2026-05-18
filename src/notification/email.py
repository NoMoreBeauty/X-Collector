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
        发送每日报告邮件（Editorial Noir 风格，Outlook 全兼容）

        Args:
            tweets_count: 推文数量
            users_count: 用户数量
            summary: AI 摘要
            report_path: 完整报告文件路径
        """
        import markdown
        from datetime import datetime
        import re

        date_str = datetime.now().strftime("%Y-%m-%d")
        weekday_map = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
        weekday_str = weekday_map[datetime.now().weekday()]
        issue_num = datetime.now().strftime("%Y%m%d")

        # ── Markdown → HTML，再注入全内联样式（Outlook 不支持 <style> 标签）──
        raw_html = markdown.markdown(summary, extensions=['tables', 'nl2br'])

        # h3 区块标题：根据 emoji 标记区分三种优先级，使用纯色背景（Outlook 不支持渐变）
        def style_h3(m):
            text = m.group(1)
            if '🔴' in text:
                label = 'MAJOR EVENTS'
                accent = '#c9614a'
                bg     = '#1a1010'
                color  = '#d97060'
            elif '🟡' in text:
                label = 'WORTH WATCHING'
                accent = '#9a8ec8'
                bg     = '#13121c'
                color  = '#9a8ec8'
            elif '📊' in text:
                label = 'SIGNAL STRENGTH'
                accent = '#5bb89e'
                bg     = '#0f1916'
                color  = '#5bb89e'
            else:
                label = ''
                accent = '#3a3a50'
                bg     = '#13131a'
                color  = '#8c8fa8'

            # 用嵌套 <table> 模拟左侧彩色竖线（Outlook 兼容方式）
            return (
                f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
                f'style="margin:24px 0 12px;">'
                f'<tr>'
                f'<td width="3" style="width:3px;background-color:{accent};font-size:0;line-height:0;">&nbsp;</td>'
                f'<td style="padding:12px 16px;background-color:{bg};">'
                f'<div style="font-size:9px;letter-spacing:0.22em;color:{accent};'
                f'text-transform:uppercase;font-family:Arial,sans-serif;margin-bottom:3px;">{label}</div>'
                f'<div style="font-family:Georgia,\'Times New Roman\',serif;font-size:17px;'
                f'color:#e2ddd6;font-weight:400;">{text}</div>'
                f'</td>'
                f'</tr>'
                f'</table>'
            )

        raw_html = re.sub(r'<h3>(.*?)</h3>', style_h3, raw_html, flags=re.DOTALL)

        # p 标签正文
        raw_html = raw_html.replace(
            '<p>',
            '<p style="margin:0 0 10px;line-height:1.75;color:#8c8fa8;'
            'font-size:13px;font-family:Arial,sans-serif;">'
        )
        # ul 列表（Outlook 支持 padding-left，但不支持 list-style-type 很好，保留默认）
        raw_html = raw_html.replace('<ul>', '<ul style="margin:6px 0 14px;padding-left:18px;">')
        raw_html = raw_html.replace('<ol>', '<ol style="margin:6px 0 14px;padding-left:18px;">')
        raw_html = raw_html.replace(
            '<li>',
            '<li style="margin:5px 0;color:#8c8fa8;font-size:13px;'
            'line-height:1.7;font-family:Arial,sans-serif;">'
        )
        # strong 强调
        raw_html = raw_html.replace('<strong>', '<strong style="color:#c8c4bc;font-weight:600;">')
        # 表格（Outlook 兼容，避免 border-radius）
        raw_html = raw_html.replace(
            '<table>',
            '<table style="width:100%;border-collapse:collapse;margin:12px 0;font-size:13px;">'
        )
        raw_html = raw_html.replace(
            '<th>',
            '<th style="padding:8px 12px;text-align:left;background-color:#1c1c26;'
            'color:#6a6e88;font-size:10px;letter-spacing:0.1em;'
            'border-bottom:1px solid #252538;font-family:Arial,sans-serif;">'
        )
        raw_html = raw_html.replace(
            '<td>',
            '<td style="padding:8px 12px;border-bottom:1px solid #1c1c26;'
            'color:#8c8fa8;font-family:Arial,sans-serif;">'
        )

        subject = f"AI 情报日报 · {date_str} · {weekday_str}"

        body = f"""<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>AI 情报日报</title>
</head>
<body style="margin:0;padding:0;background-color:#08080b;font-family:Arial,'Helvetica Neue',sans-serif;">

<table width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background-color:#08080b;padding:28px 0;">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" border="0"
           style="max-width:600px;background-color:#0f0f13;border:1px solid #1c1c26;">

      <!-- ══ 顶部金线（纯色实线，Outlook 兼容） ══ -->
      <tr>
        <td height="2" style="height:2px;background-color:#c9a96e;font-size:0;line-height:0;">&nbsp;</td>
      </tr>

      <!-- ══ MASTHEAD ══ -->
      <tr>
        <td style="padding:32px 32px 24px;border-bottom:1px solid #1c1c26;
                   background-color:#0f0f13;">
          <!-- 刊号行 -->
          <table width="100%" cellpadding="0" cellspacing="0" border="0"
                 style="margin-bottom:18px;">
            <tr>
              <td style="font-size:9px;letter-spacing:0.22em;color:#3a3a52;
                         text-transform:uppercase;font-family:Arial,sans-serif;">
                AI Intelligence Review
              </td>
              <td align="right" style="font-size:9px;letter-spacing:0.18em;color:#3a3a52;
                                        text-transform:uppercase;font-family:Arial,sans-serif;">
                No.&nbsp;{issue_num}
              </td>
            </tr>
          </table>

          <!-- 大标题（Georgia 衬线斜体，Outlook 支持） -->
          <div style="font-family:Georgia,'Times New Roman',serif;font-size:40px;
                      font-style:italic;color:#e2ddd6;letter-spacing:-1px;
                      line-height:1;margin-bottom:8px;">
            今日要览
          </div>
          <!-- 日期副标题 -->
          <div style="font-size:11px;letter-spacing:0.18em;color:#c9a96e;
                      text-transform:uppercase;font-family:Arial,sans-serif;
                      margin-bottom:22px;">
            {weekday_str} · {date_str}
          </div>

          <!-- 徽章：用 table 单元格实现（Outlook 不支持 inline-block） -->
          <table cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td style="padding:4px 12px;border:1px solid #2a2a38;
                         font-size:10px;letter-spacing:0.12em;color:#4a4a62;
                         text-transform:uppercase;font-family:Arial,sans-serif;">
                {users_count} Sources
              </td>
              <td width="10" style="width:10px;">&nbsp;</td>
              <td style="padding:4px 12px;border:1px solid #2a2a38;
                         font-size:10px;letter-spacing:0.12em;color:#4a4a62;
                         text-transform:uppercase;font-family:Arial,sans-serif;">
                {tweets_count} Signals
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- ══ 分隔符（◆ 用 Unicode 字符，无需 CSS transform） ══ -->
      <tr>
        <td style="padding:0 32px;background-color:#0f0f13;">
          <table width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td style="border-top:1px solid #1c1c26;width:50%;height:1px;
                         font-size:0;line-height:0;">&nbsp;</td>
              <td align="center" width="20" style="width:20px;color:#c9a96e;
                                                    font-size:10px;line-height:1;">
                ◆
              </td>
              <td style="border-top:1px solid #1c1c26;width:50%;height:1px;
                         font-size:0;line-height:0;">&nbsp;</td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- ══ 正文内容（Markdown 转换后的 HTML） ══ -->
      <tr>
        <td style="padding:20px 32px 28px;background-color:#0f0f13;">
          {raw_html}
        </td>
      </tr>

      <!-- ══ 底部金线 ══ -->
      <tr>
        <td height="1" style="height:1px;background-color:#c9a96e;font-size:0;line-height:0;">&nbsp;</td>
      </tr>

      <!-- ══ FOOTER ══ -->
      <tr>
        <td style="padding:12px 32px;background-color:#0a0a0d;">
          <table width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td style="font-size:9px;letter-spacing:0.12em;color:#28283a;
                         text-transform:uppercase;font-family:Arial,sans-serif;">
                Full report attached &nbsp;&middot;&nbsp; x-info-collector
              </td>
              <td align="right" style="font-size:9px;letter-spacing:0.1em;color:#28283a;
                                        text-transform:uppercase;font-family:Arial,sans-serif;">
                {date_str}
              </td>
            </tr>
          </table>
        </td>
      </tr>

    </table>
  </td></tr>
</table>

</body>
</html>"""

        return await self.send_report(subject, body, report_path)

