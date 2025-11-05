import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, timezone
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import matplotlib
import os

# === 配置 ===
symbol = "ETHUSDT"
interval = "15m"
tz = timezone(timedelta(hours=8))
matplotlib.use('Agg')
matplotlib.rcParams['font.sans-serif'] = ['SimHei']
matplotlib.rcParams['axes.unicode_minus'] = False

print("=== 自动生成 ETH/USDT K线图并发送邮件 ===")

# === Step 1: 自动计算目标日期（昨天） ===
target_date = (datetime.now(tz) - timedelta(days=1)).date()
print(f"正在生成 {target_date} 的K线图...")

# === Step 2: 时间范围 ===
start_of_day = datetime.combine(target_date, datetime.min.time(), tzinfo=tz)
end_of_day = start_of_day + timedelta(days=1)

# === Step 3: 获取K线数据 ===
url = "https://api.binance.com/api/v3/klines"
params = {
    "symbol": symbol,
    "interval": interval,
    "startTime": int(start_of_day.timestamp() * 1000),
    "endTime": int(end_of_day.timestamp() * 1000),
    "limit": 1000
}
res = requests.get(url, params=params)
data = res.json()

if not data:
    print(f"未找到 {target_date} 的K线数据。")
    exit()

# === Step 4: 处理数据 ===
columns = ["open_time", "open", "high", "low", "close", "volume", "close_time",
           "quote_asset_volume", "num_trades", "taker_buy_base", "taker_buy_quote", "ignore"]
df = pd.DataFrame(data, columns=columns)
df["open_time"] = (pd.to_datetime(df["open_time"], unit="ms")
                   .dt.tz_localize("UTC")
                   .dt.tz_convert("Asia/Shanghai")
                   .dt.tz_localize(None))
df.set_index("open_time", inplace=True)
df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)

# === Step 5: 计算指标 ===
df["IBS"] = (df["close"] - df["low"]) / (df["high"] - df["low"]) * 100
df["EMA20"] = df["close"].ewm(span=20, adjust=False).mean()

# === Step 6: 绘制K线图 ===
fig, ax = plt.subplots(figsize=(14, 8))
candle_width = 0.4

for i, (time, row) in enumerate(df.iterrows()):
    color = "#26a69a" if row["close"] >= row["open"] else "#ef5350"
    if row["close"] > row["open"] and row["IBS"] >= 69:
        color = "blue"
    elif row["close"] < row["open"] and row["IBS"] <= 31:
        color = "red"
    ax.plot([i, i], [row["low"], row["high"]], color=color, linewidth=1)
    ax.add_patch(plt.Rectangle((i - candle_width / 2, min(row["open"], row["close"])),
                               candle_width, abs(row["close"] - row["open"]), color=color))
ax.plot(range(len(df)), df["EMA20"], color="orange", linewidth=2, label="EMA20")
ax.set_xticks(range(0, len(df), max(1, len(df) // 10)))
ax.set_xticklabels(df.index.strftime("%H:%M")[::max(1, len(df) // 10)], rotation=45)
ax.set_title(f"{symbol} {interval} K线（IBS着色 + EMA20）", fontsize=14)
ax.set_ylabel("Price (USDT)")
ax.legend()
plt.tight_layout()

# === Step 7: 保存图片 ===
image_filename = f"{symbol}_{interval}_{target_date}.png"
plt.savefig(image_filename, dpi=150, bbox_inches='tight')
plt.close()
print(f"K线图已生成并保存为: {image_filename}")

# === Step 8: 读取邮箱环境变量 ===
sender_email = os.getenv("EMAIL")
sender_auth_code = os.getenv("AUTH_CODE")
receiver_email = os.getenv("EMAIL")

# === Step 9: 创建邮件 ===
msg = MIMEMultipart()
msg['Subject'] = f'{target_date} {symbol} K线图报告'
msg['From'] = sender_email
msg['To'] = receiver_email
body_text = f"""
您好！

附件为 {symbol} 在 {target_date} 08:00 至 {target_date + timedelta(days=1)} 08:00 （UTC+8） 的{interval} K线图。

图表说明：
- 蓝色：阳线且IBS≥69；
- 红色：阴线且IBS≤31；
- 橙色线：EMA20均线。
"""
msg.attach(MIMEText(body_text, 'plain', 'utf-8'))

# === Step 10: 添加图片附件 ===
with open(image_filename, 'rb') as img_file:
    img_data = img_file.read()
image_attachment = MIMEImage(img_data, name=image_filename)
image_attachment.add_header('Content-Disposition', 'attachment', filename=image_filename)
msg.attach(image_attachment)

# === Step 11: 发送邮件 ===
print("正在发送邮件...")
try:
    smtp_host = "smtp.qq.com"
    smtp_port = 465
    server = smtplib.SMTP_SSL(smtp_host, smtp_port)
    server.login(sender_email, sender_auth_code)
    server.sendmail(sender_email, [receiver_email], msg.as_string())
    server.quit()
    print("✅ 邮件发送成功！")
except Exception as e:
    print(f"❌ 邮件发送失败: {e}")
