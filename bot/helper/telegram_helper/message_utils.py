from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext, CallbackQueryHandler
from telegram.message import Message
from telegram.update import Update
import psutil, shutil
from datetime import datetime
import time
import pytz
from bot import *
from bot.helper.ext_utils.bot_utils import get_readable_message, get_readable_file_size, get_readable_time, MirrorStatus, setInterval
from telegram.error import TimedOut, BadRequest
from bot import AUTO_DELETE_MESSAGE_DURATION, LOGGER, status_reply_dict, status_reply_dict_lock, \
                Interval, DOWNLOAD_STATUS_UPDATE_INTERVAL, RSS_CHAT_ID, bot, rss_session
from bot.helper.ext_utils.bot_utils import get_readable_message, setInterval


def sendMessage(text: str, bot, message: Message):
    try:
        return bot.sendMessage(message.chat_id,
                            reply_to_message_id=message.message_id,
                            text=text, allow_sending_without_reply=True, parse_mode='HTMl', disable_web_page_preview=True)
    except RetryAfter as r:
        LOGGER.warning(str(r))
        sleep(r.retry_after * 1.5)
        return sendMessage(text, bot, message)
    except Exception as e:
        LOGGER.error(str(e))
        return

def sendMarkup(text: str, bot, message: Message, reply_markup: InlineKeyboardMarkup):
    try:
        return bot.sendMessage(message.chat_id,
                            reply_to_message_id=message.message_id,
                            text=text, reply_markup=reply_markup, allow_sending_without_reply=True,
                            parse_mode='HTMl', disable_web_page_preview=True)
    except RetryAfter as r:
        LOGGER.warning(str(r))
        sleep(r.retry_after * 1.5)
        return sendMarkup(text, bot, message, reply_markup)
    except Exception as e:
        LOGGER.error(str(e))
        return


def sendLog(text: str, bot, update: Update, reply_markup: InlineKeyboardMarkup):
    try:
        return bot.send_message(f"{LOG_CHANNEL_ID}",
                             reply_to_message_id=update.message.message_id,
                             text=text, disable_web_page_preview=True, reply_markup=reply_markup, allow_sending_without_reply=True, parse_mode='HTMl')
    except Exception as e:
        LOGGER.error(str(e))

def sendtextlog(text: str, bot, update: Update):
    try:
        return bot.send_message(f"{LOG_SEND_TEXT}",
                             reply_to_message_id=update.message.message_id,
                             text=text, disable_web_page_preview=True, allow_sending_without_reply=True, parse_mode='HTMl')
    except Exception as e:
        LOGGER.error(str(e))


def sendPrivate(text: str, bot, update: Update, reply_markup: InlineKeyboardMarkup):
    bot_d = bot.get_me()
    b_uname = bot_d.username
    
    try:
        return bot.send_message(update.message.from_user.id,
                             reply_to_message_id=update.message.message_id,
                             text=text, disable_web_page_preview=True, reply_markup=reply_markup, allow_sending_without_reply=True, parse_mode='HTMl')
    except Exception as e:
        LOGGER.error(str(e))
        if "Forbidden" in str(e):
            uname = f'<a href="tg://user?id={update.message.from_user.id}">{update.message.from_user.first_name}</a>'
            botstart = f"http://t.me/{b_uname}?start=start"
            keyboard = [
            [InlineKeyboardButton("Start Me", url = f"{botstart}")],
            [InlineKeyboardButton("Join Here", url = f"{LOG_CHANNEL_LINK}")]]
            sendMarkup(f"Hello {uname},\n\n<b>Looks like you havent started me in PM (Private Message) Yet.</b>\n\n I will send you link in PM and log channel", bot, update, reply_markup=InlineKeyboardMarkup(keyboard))
            return


def editMessage(text: str, message: Message, reply_markup=None):
    try:
        bot.edit_message_text(text=text, message_id=message.message_id,
                              chat_id=message.chat.id,reply_markup=reply_markup,
                              parse_mode='HTMl')
    except Exception as e:
        LOGGER.error(str(e))


def deleteMessage(bot, message: Message):
    try:
        bot.delete_message(chat_id=message.chat.id,
                           message_id=message.message_id)
    except Exception as e:
        LOGGER.error(str(e))


def sendLogFile(bot, update: Update):
    with open('log.txt', 'rb') as f:
        bot.send_document(document=f, filename=f.name,
                          reply_to_message_id=update.message.message_id,
                          chat_id=update.message.chat_id)


def auto_delete_message(bot, cmd_message: Message, bot_message: Message):
    if AUTO_DELETE_MESSAGE_DURATION != -1:
        time.sleep(AUTO_DELETE_MESSAGE_DURATION)
        try:
            # Skip if None is passed meaning we don't want to delete bot xor cmd message
            deleteMessage(bot, cmd_message)
            deleteMessage(bot, bot_message)
        except AttributeError:
            pass


def delete_all_messages():
    with status_reply_dict_lock:
        for message in list(status_reply_dict.values()):
            try:
                deleteMessage(bot, message)
                del status_reply_dict[message.chat.id]
            except Exception as e:
                LOGGER.error(str(e))


def update_all_messages():
    total, used, free = shutil.disk_usage('.')
    free = get_readable_file_size(free)
    currentTime = get_readable_time(time.time() - botStartTime)
    msg, buttons = get_readable_message()
    if msg is None:
        return
    msg += f"\n<b>🕊️ Free:</b> {free}"
    with download_dict_lock:
        dlspeed_bytes = 0
        uldl_bytes = 0
        for download in list(download_dict.values()):
            speedy = download.speed()
            if download.status() == MirrorStatus.STATUS_DOWNLOADING:
                if 'K' in speedy:
                    dlspeed_bytes += float(speedy.split('K')[0]) * 1024
                elif 'M' in speedy:
                    dlspeed_bytes += float(speedy.split('M')[0]) * 1048576 
            if download.status() == MirrorStatus.STATUS_UPLOADING:
                if 'KB/s' in speedy:
            	    uldl_bytes += float(speedy.split('K')[0]) * 1024
                elif 'MB/s' in speedy:
                    uldl_bytes += float(speedy.split('M')[0]) * 1048576
        dlspeed = get_readable_file_size(dlspeed_bytes)
        ulspeed = get_readable_file_size(uldl_bytes)
        msg += f"\n\n<b>🔺 UL:</b> {ulspeed}ps\n<b>🔻 DL:</b> {dlspeed}ps\n"
    with status_reply_dict_lock:
        for chat_id in list(status_reply_dict.keys()):
            if status_reply_dict[chat_id] and msg != status_reply_dict[chat_id].text:
                try:
                    if buttons == "":
                        editMessage(msg, status_reply_dict[chat_id])
                    else:
                        editMessage(msg, status_reply_dict[chat_id], buttons)
                except Exception as e:
                    LOGGER.error(str(e))
                status_reply_dict[chat_id].text = msg


def sendStatusMessage(msg, bot):
    if len(Interval) == 0:
        Interval.append(setInterval(DOWNLOAD_STATUS_UPDATE_INTERVAL, update_all_messages))
    total, used, free = shutil.disk_usage('.')
    free = get_readable_file_size(free)
    currentTime = get_readable_time(time.time() - botStartTime)
    progress, buttons = get_readable_message()
    if progress is None:
        progress, buttons = get_readable_message()
    progress += f"\n<b>🕊️ Free:</b> {free}"
    with download_dict_lock:
        dlspeed_bytes = 0
        uldl_bytes = 0
        for download in list(download_dict.values()):
            speedy = download.speed()
            if download.status() == MirrorStatus.STATUS_DOWNLOADING:
                if 'K' in speedy:
                    dlspeed_bytes += float(speedy.split('K')[0]) * 1024
                elif 'M' in speedy:
                    dlspeed_bytes += float(speedy.split('M')[0]) * 1048576 
            if download.status() == MirrorStatus.STATUS_UPLOADING:
                if 'KB/s' in speedy:
            	    uldl_bytes += float(speedy.split('K')[0]) * 1024
                elif 'MB/s' in speedy:
                    uldl_bytes += float(speedy.split('M')[0]) * 1048576
        dlspeed = get_readable_file_size(dlspeed_bytes)
        ulspeed = get_readable_file_size(uldl_bytes)
        progress += f"\n\n<b>🔺 UL:</b> {ulspeed}ps\n<b>🔻 DL:</b> {dlspeed}ps\n"
    with status_reply_dict_lock:
        if msg.message.chat.id in list(status_reply_dict.keys()):
            try:
                message = status_reply_dict[msg.message.chat.id]
                deleteMessage(bot, message)
                del status_reply_dict[msg.message.chat.id]
            except Exception as e:
                LOGGER.error(str(e))
                del status_reply_dict[msg.message.chat.id]
        if buttons == "":
            message = sendMessage(progress, bot, msg)
        else:
            message = sendMarkup(progress, bot, msg, buttons)
        status_reply_dict[msg.message.chat.id] = message
        
        
def sendRss(text: str, bot):
    if rss_session is None:
        try:
            return bot.sendMessage(RSS_CHAT_ID, text, parse_mode='HTMl', disable_web_page_preview=True)
        except RetryAfter as r:
            LOGGER.warning(str(r))
            sleep(r.retry_after * 1.5)
            return sendRss(text, bot)
        except Exception as e:
            LOGGER.error(str(e))
            return
    else:
        try:
            with rss_session:
                return rss_session.send_message(RSS_CHAT_ID, text, disable_web_page_preview=True)
        except FloodWait as e:
            LOGGER.warning(str(e))
            sleep(e.value * 1.5)
            return sendRss(text, bot)
        except Exception as e:
            LOGGER.error(str(e))
            return


async def sendRss_pyro(text: str):
    rss_session = Client(name='rss_session', api_id=int(TELEGRAM_API), api_hash=TELEGRAM_HASH, session_string=USER_STRING_SESSION, parse_mode=enums.ParseMode.HTML)
    await rss_session.start()
    try:
        return await rss_session.send_message(RSS_CHAT_ID, text, disable_web_page_preview=True)
    except FloodWait as e:
        LOGGER.warning(str(e))
        await asleep(e.value * 1.5)
        return await sendRss(text)
    except Exception as e:
        LOGGER.error(str(e))
        return
