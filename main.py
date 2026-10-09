import asyncio
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from playwright.async_api import async_playwright

WAITING_EMAIL, WAITING_OTP = range(2)
user_sessions = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Vui lòng nhập Email để bắt đầu đăng ký:")
    return WAITING_EMAIL

async def process_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip()
    chat_id = update.message.chat.id
    
    await update.message.reply_text(f"Đang xử lý đăng ký cho: {email}...")

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True)
    page = await browser.new_page()

    try:
        # Thay link trang web cần đăng ký vào đây
        await page.goto("https://cloud.vmoscloud.com")

        # Điền email (thay đổi selector theo web của bạn)
        await page.fill('input[type="email"]', email)
        await page.click('button[type="submit"]')

        user_sessions[chat_id] = {
            "playwright": playwright,
            "browser": browser,
            "page": page
        }

        await update.message.reply_text("Mã xác minh đã được gửi về mail. Vui lòng nhập mã OTP tại đây:")
        return WAITING_OTP

    except Exception as e:
        await update.message.reply_text(f"Lỗi khi gửi request: {str(e)}")
        await browser.close()
        await playwright.stop()
        return ConversationHandler.END

async def process_otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    otp_code = update.message.text.strip()
    chat_id = update.message.chat.id
    session = user_sessions.get(chat_id)

    if not session:
        await update.message.reply_text("Phiên làm việc hết hạn. Vui lòng gõ /start để thử lại.")
        return ConversationHandler.END

    page = session["page"]

    try:
        # Điền mã OTP (thay đổi selector theo web của bạn)
        await page.fill('input[name="otp"]', otp_code)
        await page.click('button[id="verify-btn"]')

        await page.wait_for_load_state("networkidle")
        await update.message.reply_text("Đăng ký tài khoản thành công!")

    except Exception as e:
        await update.message.reply_text(f"Xảy ra lỗi khi xác minh: {str(e)}")

    finally:
        await session["browser"].close()
        await session["playwright"].stop()
        user_sessions.pop(chat_id, None)

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    session = user_sessions.pop(chat_id, None)
    if session:
        await session["browser"].close()
        await session["playwright"].stop()
    await update.message.reply_text("Đã hủy quá trình đăng ký.")
    return ConversationHandler.END

if __name__ == "__main__":
    # Thay '8351895750:AAGNsI1k9zuiCWopY3Bt3sajJfqiqzAs4sY' bằng Token lấy từ BotFather
    app = Application.builder().token("8351895750:AAGNsI1k9zuiCWopY3Bt3sajJfqiqzAs4sY").build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAITING_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_email)],
            WAITING_OTP: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_otp)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.run_polling()
