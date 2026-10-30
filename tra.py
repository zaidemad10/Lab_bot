import os
import json
import re
import math
import asyncio
import logging
import subprocess
import sys
import time
import textwrap
import urllib.request
import random
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

def install_missing_packages():
    import importlib.util
    required = {
        'arabic-reshaper': 'arabic_reshaper',
        'python-bidi': 'bidi',
        'pypdf': 'pypdf',
        'reportlab': 'reportlab',
        'requests': 'requests',
        'python-telegram-bot': 'telegram',
    }
    missing = [pkg for pkg, mod in required.items() if importlib.util.find_spec(mod) is None]
    if missing:
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)

try:
    install_missing_packages()
except Exception:
    pass

import requests
from pypdf import PdfReader
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import arabic_reshaper
from bidi.algorithm import get_display

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

TELEGRAM_TOKEN = "8858734598:AAHjxd4-VsPEbigKN-5Ud8pYJ6StNnpZD-o"
GROQ_API_KEY = "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"

BOT_HEADER_PHOTO = "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?w=800&auto=format&fit=crop&q=80"

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

MODEL_LADDER_STRONG = [
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-safeguard-20b",
    "allam-2-7b"
]

MODEL_LADDER_FAST = [
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-safeguard-20b",
    "allam-2-7b",
    "openai/gpt-oss-120b"
]

HEDGE_DELAY = 6.0
MAX_PARALLEL_MODELS = 3

DEFAULT_SYSTEM_PROMPT = (
    "أنت نظام مستشار تشخيصي وأكاديمي تخصصي في التحليلات المرضية لمرحلة رابعة. "
    "ممنوع نهائياً استخدام لغة الذكاء الاصطناعي أو العناوين التكرارية أو كتابة أي مقدمات أو سرديات أو عبارات توضيحية. "
    "ابدأ بالمحتوى مباشرة بأسلوب علمي رصين ومختصر دون إسهاب أو ذكر لأي أرقام أو عناوين ترحيبية."
)

groq_session = requests.Session()
groq_session.mount("https://", requests.adapters.HTTPAdapter(pool_connections=32, pool_maxsize=32))

THEMES = [
    {"name": "أكاديمي", "title": "#1E3A8A", "accent": "#2563EB", "card_bg": "#F8FAFC", "band": "#1E3A8A", "body_en": "#0F172A", "body_ar": "#1E40AF"},
    {"name": "رومانسي", "title": "#9D174D", "accent": "#DB2777", "card_bg": "#FFF1F7", "band": "#BE185D", "body_en": "#4C0519", "body_ar": "#9D174D"},
    {"name": "مُغرم", "title": "#9F1239", "accent": "#E11D48", "card_bg": "#FFF1F2", "band": "#BE123C", "body_en": "#4C0519", "body_ar": "#9F1239"},
    {"name": "كارتوني", "title": "#B45309", "accent": "#F59E0B", "card_bg": "#FFFBEB", "band": "#D97706", "body_en": "#7C2D12", "body_ar": "#B45309"},
    {"name": "طبيعة", "title": "#166534", "accent": "#16A34A", "card_bg": "#F0FDF4", "band": "#15803D", "body_en": "#14532D", "body_ar": "#166534"},
    {"name": "محيط", "title": "#0E7490", "accent": "#06B6D4", "card_bg": "#ECFEFF", "band": "#0891B2", "body_en": "#164E63", "body_ar": "#0E7490"},
    {"name": "ملكي", "title": "#5B21B6", "accent": "#7C3AED", "card_bg": "#F5F3FF", "band": "#6D28D9", "body_en": "#2E1065", "body_ar": "#5B21B6"},
    {"name": "غروب", "title": "#9A3412", "accent": "#EA580C", "card_bg": "#FFF7ED", "band": "#C2410C", "body_en": "#7C2D12", "body_ar": "#9A3412"},
    {"name": "زهري لطيف", "title": "#9D174D", "accent": "#EC4899", "card_bg": "#FFF7FB", "band": "#BE185D", "body_en": "#4C2438", "body_ar": "#9D174D", "sticker_family": "feminine"},
    {"name": "لافندر ناعم", "title": "#5B21B6", "accent": "#A78BFA", "card_bg": "#FAF7FF", "band": "#7C3AED", "body_en": "#352450", "body_ar": "#5B21B6", "sticker_family": "feminine"},
    {"name": "خوخي مرح", "title": "#9A3412", "accent": "#FB923C", "card_bg": "#FFFAF5", "band": "#EA580C", "body_en": "#542D1D", "body_ar": "#9A3412", "sticker_family": "feminine"},
    {"name": "سماوي مغامر", "title": "#1E40AF", "accent": "#38BDF8", "card_bg": "#F4FBFF", "band": "#0284C7", "body_en": "#19324D", "body_ar": "#1E40AF", "sticker_family": "playful"},
    {"name": "فضاء مرح", "title": "#3730A3", "accent": "#818CF8", "card_bg": "#F7F7FF", "band": "#4F46E5", "body_en": "#282747", "body_ar": "#3730A3", "sticker_family": "playful"},
    {"name": "نعناعي شبابي", "title": "#166534", "accent": "#34D399", "card_bg": "#F3FFF9", "band": "#059669", "body_en": "#1D4031", "body_ar": "#166534", "sticker_family": "playful"}
]

def pick_theme():
    return random.choice(THEMES)

def _accent_rule(theme, width):
    rule = Table([[""]], colWidths=[width], rowHeights=[3])
    rule.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(theme["accent"])),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return rule

user_sessions = {}
user_usage = {}
chat_locks = {}

def get_chat_lock(chat_id):
    if chat_id not in chat_locks:
        chat_locks[chat_id] = asyncio.Lock()
    return chat_locks[chat_id]

ARABIC_FONT_NAME = "Helvetica"
font_file = "Amiri-Regular.ttf"

if not os.path.exists(font_file):
    try:
        url = "https://github.com/google/fonts/raw/main/ofl/amiri/Amiri-Regular.ttf"
        urllib.request.urlretrieve(url, font_file)
    except Exception:
        pass

for f_path in [font_file, '/system/fonts/NotoSansArabic-Regular.ttf', '/system/fonts/DroidSans.ttf']:
    if os.path.exists(f_path):
        try:
            pdfmetrics.registerFont(TTFont('ArabicFont', f_path))
            ARABIC_FONT_NAME = 'ArabicFont'
            break
        except Exception:
            pass

async def get_user_photo_id(context, user_id):
    try:
        photos = await context.bot.get_user_profile_photos(user_id=user_id, limit=1)
        if photos and photos.total_count > 0:
            return photos.photos[0][-1].file_id
    except Exception as e:
        logging.error(f"Error fetching profile photo: {e}")
    return BOT_HEADER_PHOTO

def check_rate_limit(user):
    username = (user.username or "").lower().replace("@", "")
    if username == "zukuu":
        return True, ""
    
    user_id = user.id
    now = time.time()
    
    data = user_usage.get(user_id, {'count': 0, 'reset_time': 0})
    
    if now >= data['reset_time']:
        data['count'] = 0
        data['reset_time'] = now + 3600
        user_usage[user_id] = data
        
    if data['count'] >= 15:
        return False, "انتظر بعد ساعه ، فقد تم الوصول إلى الحد الأقصى من المحاولات لهذا الوقت."
        
    return True, ""

def increment_usage(user):
    username = (user.username or "").lower().replace("@", "")
    if username == "zukuu":
        return
    user_id = user.id
    now = time.time()
    if user_id not in user_usage or now >= user_usage[user_id]['reset_time']:
        user_usage[user_id] = {'count': 1, 'reset_time': now + 3600}
    else:
        user_usage[user_id]['count'] += 1

def is_arabic(text):
    return bool(re.search(r'[\u0600-\u06FF]', text))

def format_arabic_clean(text, max_width=60):
    if not text:
        return ""
    try:
        clean = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
        clean = re.sub(r'\*(.*?)\*', r'\1', clean)
        clean = re.sub(r'`(.*?)`', r'\1', clean)
        clean = clean.replace('\r', '')

        lines = clean.split('\n')
        result_lines = []
        for l in lines:
            l_str = l.strip()
            if not l_str:
                result_lines.append("")
                continue
            
            if is_arabic(l_str):
                wrapped = textwrap.wrap(l_str, width=max_width)
                if not wrapped:
                    wrapped = [l_str]
                for w_line in wrapped:
                    reshaped = arabic_reshaper.reshape(w_line)
                    bidi_l = get_display(reshaped)
                    result_lines.append(bidi_l)
            else:
                result_lines.append(l_str)
                
        return "<br/>".join(result_lines)
    except Exception:
        return text

def clean_text(text):
    if not text:
        return ""
    text = str(text)
    dash_variants = ['\u2010', '\u2011', '\u2012', '\u2013', '\u2014', '\u2015', '\u2212', '–', '—', '‐', '‑', '‒', '―']
    for d in dash_variants:
        text = text.replace(d, '-')
        
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    text = text.replace('\r', '')
    text = re.sub(r'[\u2500-\u257F\u2580-\u259F]', '', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'`(.*?)`', r'\1', text)
    return text

def _draw_sticker(canvas, x, y, kind, color):
    canvas.saveState()
    ink = colors.HexColor(color)
    canvas.setStrokeColor(ink)
    canvas.setFillColor(ink)
    canvas.setLineWidth(1.15)

    if kind == "star":
        path = canvas.beginPath()
        for index in range(10):
            angle = math.pi / 2 + index * math.pi / 5
            radius = 7 if index % 2 == 0 else 3.2
            px = x + math.cos(angle) * radius
            py = y + math.sin(angle) * radius
            (path.moveTo if index == 0 else path.lineTo)(px, py)
        path.close()
        canvas.drawPath(path, stroke=1, fill=0)
    elif kind == "heart":
        path = canvas.beginPath()
        path.moveTo(x, y - 7)
        path.curveTo(x - 12, y + 1, x - 6, y + 9, x, y + 3)
        path.curveTo(x + 6, y + 9, x + 12, y + 1, x, y - 7)
        canvas.drawPath(path, stroke=1, fill=0)
    elif kind == "flower":
        for dx, dy in ((0, 4), (4, 0), (0, -4), (-4, 0), (3, 3), (-3, 3)):
            canvas.circle(x + dx, y + dy, 2.4, stroke=1, fill=0)
        canvas.circle(x, y, 1.5, stroke=1, fill=1)
    elif kind == "smile":
        canvas.circle(x, y, 7, stroke=1, fill=0)
        canvas.circle(x - 2.5, y + 2, 0.65, stroke=0, fill=1)
        canvas.circle(x + 2.5, y + 2, 0.65, stroke=0, fill=1)
        canvas.arc(x - 3.5, y - 3, x + 3.5, y + 1.5, 205, 130)
    elif kind == "book":
        canvas.roundRect(x - 7, y - 5.5, 14, 11, 1.6, stroke=1, fill=0)
        canvas.line(x, y - 5, x, y + 5)
        canvas.line(x - 5, y + 2.5, x - 1.5, y + 2.5)
        canvas.line(x + 1.5, y + 2.5, x + 5, y + 2.5)
    elif kind == "bow":
        path = canvas.beginPath()
        path.moveTo(x - 1, y)
        path.lineTo(x - 8, y + 5)
        path.lineTo(x - 7, y - 5)
        path.close()
        canvas.drawPath(path, stroke=1, fill=0)
        path = canvas.beginPath()
        path.moveTo(x + 1, y)
        path.lineTo(x + 8, y + 5)
        path.lineTo(x + 7, y - 5)
        path.close()
        canvas.drawPath(path, stroke=1, fill=0)
        canvas.circle(x, y, 2, stroke=1, fill=0)
    elif kind == "planet":
        canvas.circle(x, y, 5, stroke=1, fill=0)
        canvas.ellipse(x - 9, y - 3, x + 9, y + 3, stroke=1, fill=0)
        canvas.circle(x + 2, y + 1.5, 0.7, stroke=0, fill=1)
    elif kind == "rocket":
        path = canvas.beginPath()
        path.moveTo(x, y + 8)
        path.curveTo(x + 7, y + 3, x + 5, y - 3, x + 3, y - 5)
        path.lineTo(x - 3, y - 5)
        path.curveTo(x - 5, y - 3, x - 7, y + 3, x, y + 8)
        path.close()
        canvas.drawPath(path, stroke=1, fill=0)
        canvas.circle(x, y + 1, 1.5, stroke=1, fill=0)
        canvas.line(x - 3, y - 4, x - 6, y - 8)
        canvas.line(x + 3, y - 4, x + 6, y - 8)
    elif kind == "bolt":
        path = canvas.beginPath()
        path.moveTo(x + 2, y + 8)
        path.lineTo(x - 5, y - 1)
        path.lineTo(x - 1, y - 1)
        path.lineTo(x - 3, y - 8)
        path.lineTo(x + 5, y + 1)
        path.lineTo(x + 1, y + 1)
        path.close()
        canvas.drawPath(path, stroke=1, fill=0)
    elif kind == "paw":
        canvas.ellipse(x - 5, y - 5, x + 5, y + 2, stroke=1, fill=0)
        for dx, dy in ((-5, 4), (-1.8, 6), (1.8, 6), (5, 4)):
            canvas.circle(x + dx, y + dy, 1.7, stroke=1, fill=0)
    else:  # sparkle
        canvas.line(x, y - 8, x, y + 8)
        canvas.line(x - 8, y, x + 8, y)
        canvas.line(x - 5, y - 5, x + 5, y + 5)
        canvas.line(x - 5, y + 5, x + 5, y - 5)
        canvas.circle(x, y, 2.2, stroke=1, fill=0)

    canvas.restoreState()


def draw_background(canvas, doc, theme=None):
    if theme is None:
        theme = THEMES[0]
    canvas.saveState()
    w, h = doc.pagesize
    canvas.setFillColor(colors.HexColor('#FFFFFF'))
    canvas.rect(0, 0, w, h, fill=1, stroke=0)
    canvas.setStrokeColor(colors.HexColor(theme["accent"]))
    canvas.setLineWidth(2.2)
    canvas.rect(14, 14, w - 28, h - 28, fill=0, stroke=1)
    canvas.setStrokeColor(colors.HexColor(theme["band"]))
    canvas.setLineWidth(0.7)
    canvas.rect(19.5, 19.5, w - 39, h - 39, fill=0, stroke=1)

    page_number = max(1, int(getattr(doc, "page", 1)))
    page_rng = random.Random(random.getrandbits(64) ^ (page_number * 0x9E3779B97F4A7C15))
    family = theme.get("sticker_family", "mixed")
    if family == "feminine":
        sticker_kinds = ("heart", "flower", "bow", "star", "smile", "sparkle")
    elif family == "playful":
        sticker_kinds = ("star", "planet", "rocket", "bolt", "book", "paw", "smile", "sparkle")
    else:
        sticker_kinds = ("star", "heart", "flower", "smile", "book", "bow", "planet", "rocket", "bolt", "paw", "sparkle")

    sticker_x = page_rng.choice((29, w - 29))
    sticker_y = page_rng.uniform(48, h - 48)
    _draw_sticker(canvas, sticker_x, sticker_y, page_rng.choice(sticker_kinds), theme["accent"])
    if page_rng.random() < 0.28:
        other_x = w - sticker_x
        other_y = page_rng.uniform(48, h - 48)
        _draw_sticker(canvas, other_x, other_y, page_rng.choice(sticker_kinds), theme["band"])

    footer_size = 7.5
    footer_y = 23
    footer_handle = "@zukuu"
    footer_arabic = get_display(arabic_reshaper.reshape("تم الاعداد بواسطه :"))
    handle_width = pdfmetrics.stringWidth(footer_handle, ARABIC_FONT_NAME, footer_size)
    arabic_width = pdfmetrics.stringWidth(footer_arabic, ARABIC_FONT_NAME, footer_size)
    label_padding = 7
    label_gap = 4
    label_width = handle_width + label_gap + arabic_width + 2 * label_padding
    label_x = (w - label_width) / 2
    canvas.setFillColor(colors.HexColor(theme["card_bg"]))
    canvas.setStrokeColor(colors.HexColor(theme["accent"]))
    canvas.setLineWidth(0.65)
    canvas.roundRect(label_x, 20.5, label_width, 13, 6, stroke=1, fill=1)
    canvas.setFillColor(colors.HexColor(theme["title"]))
    canvas.setFont(ARABIC_FONT_NAME, footer_size)
    canvas.drawString(label_x + label_padding, footer_y, footer_handle)
    canvas.drawString(label_x + label_padding + handle_width + label_gap, footer_y, footer_arabic)
    canvas.restoreState()

def _groq_request(model_name, sys_content, prompt_text, json_mode, max_tokens, reasoning):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": sys_content},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.3,
        "max_tokens": max_tokens
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    if reasoning and model_name.startswith("openai/gpt-oss"):
        payload["reasoning_effort"] = reasoning

    resp = groq_session.post(GROQ_URL, headers=headers, json=payload, timeout=120)
    if resp.status_code == 200:
        content = resp.json()["choices"][0]["message"].get("content", "")
        if content and content.strip():
            return True, content, ""
        return False, "", "empty completion"
    if resp.status_code == 429:
        return False, "", "429 rate limit"
    return False, "", f"{resp.status_code}: {resp.text[:300]}"

def _groq_attempt_safe(model_name, sys_content, prompt_text, json_mode, max_tokens, reasoning):
    try:
        return _groq_request(model_name, sys_content, prompt_text, json_mode, max_tokens, reasoning)
    except Exception as e:
        return False, "", str(e)

def call_groq(prompt_text, json_mode=False, system_prompt=None, max_tokens=8192, fast=False, reasoning=None, hedge_delay=None):
    if not GROQ_API_KEY:
        raise Exception("مفتاح Groq API غير موجود!")

    sys_content = system_prompt if system_prompt else DEFAULT_SYSTEM_PROMPT
    ladder = MODEL_LADDER_FAST if fast else MODEL_LADDER_STRONG
    if reasoning is None:
        reasoning = "low" if fast else "medium"
    delay = HEDGE_DELAY if hedge_delay is None else hedge_delay

    last_error = ""
    workers = min(MAX_PARALLEL_MODELS, len(ladder))
    executor = ThreadPoolExecutor(max_workers=workers)
    try:
        pending = set()
        index = 0
        pending.add(executor.submit(_groq_attempt_safe, ladder[index], sys_content, prompt_text, json_mode, max_tokens, reasoning))
        index += 1
        while pending:
            done, pending = wait(pending, timeout=delay, return_when=FIRST_COMPLETED)
            for future in done:
                ok, content, err = future.result()
                if ok:
                    return content
                last_error = err
                logging.warning(f"Model attempt failed: {err}")
            if index < len(ladder):
                pending.add(executor.submit(_groq_attempt_safe, ladder[index], sys_content, prompt_text, json_mode, max_tokens, reasoning))
                index += 1
    finally:
        try:
            executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            executor.shutdown(wait=False)

    _exc = Exception(f"فشل الاتصال بجميع النماذج المتاحة:\n{last_error}")
    logging.error(str(_exc))
    raise _exc

def create_unified_pdf(title, text_content, filename, is_landscape=False, theme=None):
    if theme is None:
        theme = pick_theme()
    file_path = f"{filename}_{os.urandom(4).hex()}.pdf"
    p_size = landscape(letter) if is_landscape else letter
    doc = SimpleDocTemplate(file_path, pagesize=p_size, leftMargin=34, rightMargin=34, topMargin=34, bottomMargin=34)
    styles = getSampleStyleSheet()
    col_w = p_size[0] - 68
    
    title_style = ParagraphStyle('PdfTitle', parent=styles['Heading1'], fontName=ARABIC_FONT_NAME, fontSize=17, leading=23, textColor=colors.HexColor(theme["title"]), alignment=1)
    card_head_style = ParagraphStyle('CardHead', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=14, textColor=colors.HexColor(theme["title"]), alignment=0)
    card_ar_style = ParagraphStyle('CardArabic', parent=styles['Normal'], fontName=ARABIC_FONT_NAME, fontSize=10, leading=14.5, textColor=colors.HexColor(theme["body_ar"]), alignment=2)
    card_en_style = ParagraphStyle('CardEn', parent=styles['Normal'], fontName='Helvetica', fontSize=9.5, leading=13.5, textColor=colors.HexColor(theme["body_en"]), alignment=0)
    
    story = []
    cleaned_title = clean_text(title)
    story.append(Paragraph(format_arabic_clean(cleaned_title, max_width=60) if is_arabic(cleaned_title) else cleaned_title, title_style))
    story.append(Spacer(1, 5))
    story.append(_accent_rule(theme, col_w))
    story.append(Spacer(1, 12))
    
    cleaned = clean_text(text_content)
    cleaned = re.sub(r'^\s*[-–—]+\s*$', '', cleaned, flags=re.MULTILINE)
    
    cases = cleaned.split("###CASE###")
    case_no = 0
    
    for case in cases:
        case_str = case.strip()
        if not case_str:
            continue
            
        lines = [l.strip() for l in case_str.split('\n') if l.strip() and l.strip() not in ['-', '–', '—', '---']]
        if not lines:
            continue
        case_no += 1

        badge = Table([[Paragraph(f"{case_no}", ParagraphStyle('Badge', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor('#FFFFFF'), alignment=1))]], colWidths=[20], rowHeights=[20])
        badge.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor(theme["accent"])),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ]))
        card_elements = [badge, Spacer(1, 6)]
        for line in lines:
            if is_arabic(line):
                card_elements.append(Paragraph(format_arabic_clean(line, max_width=60), card_ar_style))
            else:
                card_elements.append(Paragraph(line, card_en_style))
            card_elements.append(Spacer(1, 2))
                
        card_table = Table([[card_elements]], colWidths=[col_w])
        card_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor(theme["card_bg"])),
            ('BOX', (0,0), (-1,-1), 1.1, colors.HexColor(theme["accent"])),
            ('LINEBEFORE', (0,0), (0,-1), 3.5, colors.HexColor(theme["band"])),
            ('TOPPADDING', (0,0), (-1,-1), 7),
            ('BOTTOMPADDING', (0,0), (-1,-1), 7),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('RIGHTPADDING', (0,0), (-1,-1), 10),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        story.append(KeepTogether(card_table))
        story.append(Spacer(1, 8))
            
    doc.build(story, onFirstPage=lambda c, d: draw_background(c, d, theme), onLaterPages=lambda c, d: draw_background(c, d, theme))
    return file_path

def create_pdf(title, text_content, filename, is_landscape=False, theme=None):
    if theme is None:
        theme = pick_theme()
    file_path = f"{filename}_{os.urandom(4).hex()}.pdf"
    p_size = landscape(letter) if is_landscape else letter
    doc = SimpleDocTemplate(file_path, pagesize=p_size, leftMargin=34, rightMargin=34, topMargin=34, bottomMargin=34)
    styles = getSampleStyleSheet()
    col_w = p_size[0] - 68
    
    title_style = ParagraphStyle('PdfTitle', parent=styles['Heading1'], fontName=ARABIC_FONT_NAME, fontSize=17, leading=23, textColor=colors.HexColor(theme["title"]), alignment=1)
    card_subhead_style = ParagraphStyle('CardSubHead', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=14, textColor=colors.HexColor(theme["title"]), alignment=0)
    card_ar_style = ParagraphStyle('CardArabic', parent=styles['Normal'], fontName=ARABIC_FONT_NAME, fontSize=10, leading=14.5, textColor=colors.HexColor(theme["body_ar"]), alignment=2)
    card_en_style = ParagraphStyle('CardEn', parent=styles['Normal'], fontName='Helvetica', fontSize=9.5, leading=13.5, textColor=colors.HexColor(theme["body_en"]), alignment=0)
    
    body_style_en = ParagraphStyle('PdfBodyEN', parent=styles['Normal'], fontName='Helvetica', fontSize=9.5, leading=13.5, textColor=colors.HexColor(theme["body_en"]), alignment=0)
    body_style_ar = ParagraphStyle('PdfBodyAR', parent=styles['Normal'], fontName=ARABIC_FONT_NAME, fontSize=9.5, leading=14, textColor=colors.HexColor(theme["body_ar"]), alignment=2)
    
    story = []
    cleaned_title = clean_text(title)
    story.append(Paragraph(format_arabic_clean(cleaned_title, max_width=60) if is_arabic(cleaned_title) else cleaned_title, title_style))
    story.append(Spacer(1, 5))
    story.append(_accent_rule(theme, col_w))
    story.append(Spacer(1, 12))
    
    cleaned = clean_text(text_content)
    cleaned = re.sub(r'^\s*[-–—]+\s*$', '', cleaned, flags=re.MULTILINE)
    blocks = re.split(r'\n\s*\n', cleaned)
    
    framed_files = ["cases", "tf_reasoning", "summary", "terms", "flashcards", "bank"]
    
    for block in blocks:
        block_str = block.strip()
        if not block_str:
            continue
            
        lines = [l.strip() for l in block_str.split('\n') if l.strip() and l.strip() not in ['-', '–', '—', '---']]
        if not lines:
            continue
            
        has_english = any(not is_arabic(l) for l in lines)
        has_arabic = any(is_arabic(l) for l in lines)
        
        if (has_english and has_arabic and len(lines) >= 2) or filename in framed_files:
            card_elements = []
            first_en_done = False
            for line in lines:
                if is_arabic(line):
                    card_elements.append(Paragraph(format_arabic_clean(line, max_width=60), card_ar_style))
                elif not first_en_done:
                    card_elements.append(Paragraph(line, card_subhead_style))
                    first_en_done = True
                else:
                    card_elements.append(Paragraph(line, card_en_style))
                card_elements.append(Spacer(1, 2))
                    
            card_table = Table([[card_elements]], colWidths=[col_w])
            card_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor(theme["card_bg"])),
                ('BOX', (0,0), (-1,-1), 1.1, colors.HexColor(theme["accent"])),
                ('LINEBEFORE', (0,0), (0,-1), 3.5, colors.HexColor(theme["band"])),
                ('TOPPADDING', (0,0), (-1,-1), 7),
                ('BOTTOMPADDING', (0,0), (-1,-1), 7),
                ('LEFTPADDING', (0,0), (-1,-1), 10),
                ('RIGHTPADDING', (0,0), (-1,-1), 10),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ]))
            story.append(KeepTogether(card_table))
            story.append(Spacer(1, 6))
        else:
            for line in lines:
                if is_arabic(line):
                    story.append(Paragraph(format_arabic_clean(line, max_width=70), body_style_ar))
                else:
                    story.append(Paragraph(line, body_style_en))
                story.append(Spacer(1, 2))
            story.append(Spacer(1, 3))
            
    doc.build(story, onFirstPage=lambda c, d: draw_background(c, d, theme), onLaterPages=lambda c, d: draw_background(c, d, theme))
    return file_path

def create_mindmap_pdf(title, text_content, filename, theme=None):
    if theme is None:
        theme = pick_theme()
    file_path = f"{filename}_{os.urandom(4).hex()}.pdf"
    doc = SimpleDocTemplate(file_path, pagesize=landscape(letter), leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('MMTitle', parent=styles['Heading1'], fontName=ARABIC_FONT_NAME, fontSize=16, leading=21, textColor=colors.HexColor(theme["title"]), alignment=1)
    cat_title_style = ParagraphStyle('MMCatTitle', parent=styles['Heading3'], fontName='Helvetica-Bold', fontSize=10.5, leading=13, textColor=colors.HexColor('#FFFFFF'), alignment=0)
    point_style = ParagraphStyle('MMPoint', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, leading=12, textColor=colors.HexColor(theme["body_en"]))
    
    categories = []
    try:
        clean_t = text_content.replace("```json", "").replace("```", "").strip()
        match = re.search(r'\[.*\]', clean_t, re.DOTALL)
        if match:
            categories = json.loads(match.group(0))
        else:
            categories = json.loads(clean_t)
    except Exception:
        pass
        
    if not isinstance(categories, list) or len(categories) == 0:
        lines = [l.strip() for l in text_content.split('\n') if l.strip()]
        cat1 = {"title": "ETIOLOGY & PATHOGENESIS", "points": []}
        cat2 = {"title": "CLINICAL MANIFESTATIONS", "points": []}
        cat3 = {"title": "DIAGNOSTIC PROTOCOL", "points": []}
        cat4 = {"title": "LAB FINDINGS & BIOMARKERS", "points": []}
        all_cats = [cat1, cat2, cat3, cat4]
        idx = 0
        for l in lines:
            clean_l = re.sub(r'^[#=📌\-\*\d\.\)]+\s*', '', l)
            if clean_l:
                all_cats[idx % 4]["points"].append(clean_l[:60])
                idx += 1
        categories = all_cats

    cleaned_title = clean_text(title)
    story = [Paragraph(format_arabic_clean(cleaned_title, max_width=60) if is_arabic(cleaned_title) else cleaned_title, title_style), Spacer(1, 10)]
    
    while len(categories) < 4:
        categories.append({"title": "KEY DIAGNOSTIC NOTES", "points": ["Core Concept -> Exam Highlights"]})

    grid_cells = []
    for cat in categories[:4]:
        cat_title = str(cat.get("title", "SECTION")).upper()
        points = cat.get("points", [])
        
        hdr = Table([[Paragraph(cat_title, cat_title_style)]], colWidths=['100%'])
        hdr.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor(theme["band"])),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ]))
        
        content_elements = [hdr, Spacer(1, 5)]
        for pt in points[:6]:
            clean_pt = clean_text(str(pt))
            content_elements.append(Paragraph(f"• {clean_pt}", point_style))
            content_elements.append(Spacer(1, 3))
            
        box_table = Table([[content_elements]], colWidths=['100%'])
        box_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor(theme["card_bg"])),
            ('BOX', (0,0), (-1,-1), 1.1, colors.HexColor(theme["accent"])),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        grid_cells.append(box_table)

    row1 = [grid_cells[0], grid_cells[1]]
    row2 = [grid_cells[2], grid_cells[3]]
    
    col_w = (landscape(letter)[0] - 72) / 2.0
    grid_table = Table([row1, row2], colWidths=[col_w, col_w])
    grid_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    
    story.append(grid_table)
    doc.build(story, onFirstPage=lambda c, d: draw_background(c, d, theme), onLaterPages=lambda c, d: draw_background(c, d, theme))
    return file_path

async def send_long_message(message_obj, text):
    max_length = 4000
    if len(text) <= max_length:
        await message_obj.reply_text(text)
        return
    for i in range(0, len(text), max_length):
        await message_obj.reply_text(text[i:i + max_length])
        await asyncio.sleep(0.05)

def read_pdf_sync(file_path):
    extracted_text = ""
    reader = PdfReader(file_path)
    for page in reader.pages:
        t = page.extract_text()
        if t:
            extracted_text += t + "\n"
    return extracted_text

async def generate_mcq_batch(text, count, mode):
    chunk_size = 10 if count >= 20 else count
    chunks, remaining = [], count
    while remaining > 0:
        c = min(chunk_size, remaining)
        chunks.append(c)
        remaining -= c

    all_questions = []
    for c in chunks:
        q_sub = await asyncio.to_thread(fetch_mcqs_from_groq, text, c, mode)
        if isinstance(q_sub, list):
            all_questions.extend(q_sub)
        await asyncio.sleep(0.1)
    return all_questions

def fetch_mcqs_from_groq(text, count, mode):
    sys_p = (
        "أنت أستاذ جامعي ومصمم أسئلة امتحانات دقيقة لمرحلة رابعة تحليلات مرضية. "
        "مهمتك صياغة أسئلة متنوعة ومتجددة بالكامل بدون أي تكرار أو سرديات."
    )
    
    if mode == "ar":
        prompt = f"""أنشئ بالضبط {count} أسئلة MCQ متنوعة وغير مكررة نهائياً باللغة العربية حصراً من النص أدناه بدون أي مقدمات أو سرديات ويجب أن يحتوي الطلب على كلمة json:
[
  {{
    "question": "السؤال",
    "options": ["خيار 1", "خيار 2", "خيار 3", "خيار 4"],
    "correct_option_id": 0,
    "explanation": "التعليل"
  }}
]
النص: {text}"""
    elif mode == "en":
        prompt = f"""Generate exactly {count} diverse, non-repeating MCQs in English strictly based on the text without any introductory text or narratives. Return valid json format:
[
  {{
    "question": "Question statement",
    "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
    "correct_option_id": 0,
    "explanation": "Explanation"
  }}
]
Text: {text}"""
    else:
        prompt = f"""Generate exactly {count} diverse, unique, non-repeating MCQs based on the text without narratives. Return valid json format.
Format: Short English text with short Arabic translation in parentheses.
[
  {{
    "question": "Question (السؤال)",
    "options": ["Opt 1 (خيار 1)", "Opt 2 (خيار 2)", "Opt 3 (خيار 3)", "Opt 4 (خيار 4)"],
    "correct_option_id": 0,
    "explanation": "Explanation (التعليل)"
  }}
]
Text: {text}"""
    
    res_raw = call_groq(prompt, json_mode=True, system_prompt=sys_p, max_tokens=8192, fast=True, hedge_delay=4.0)
    try:
        clean_t = res_raw.replace("```json", "").replace("```", "").strip()
        match = re.search(r'\[.*\]', clean_t, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(clean_t)
    except:
        parsed = json.loads(res_raw.replace("```json", "").replace("```", "").strip())
        if isinstance(parsed, dict):
            for v in parsed.values():
                if isinstance(v, list):
                    return v
        return parsed

def get_main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📝 MCQ عربي", callback_data="menu_mcq_ar"),
            InlineKeyboardButton("🌐 MCQ مترجم", callback_data="menu_mcq_tr"),
            InlineKeyboardButton("🇬🇧 MCQ English", callback_data="menu_mcq_en")
        ],
        [
            InlineKeyboardButton("📚 بنك الأسئلة الشامل (PDF)", callback_data="gen_bank"),
            InlineKeyboardButton("🎯 الصح والخطأ والتعليل (PDF)", callback_data="gen_tf_reasoning")
        ],
        [
            InlineKeyboardButton("🧪 الحالات السريرية والمقالي (PDF)", callback_data="gen_cases"),
            InlineKeyboardButton("🩺 كيسات - Essay (PDF)", callback_data="gen_essay"),
            InlineKeyboardButton("🌐 كيسات Essay مترجم (PDF)", callback_data="gen_essay_tr")
        ],
        [
            InlineKeyboardButton("🗂 Flashcards (PDF)", callback_data="gen_flashcards"),
            InlineKeyboardButton("🧠 Mind Map (PDF)", callback_data="gen_mindmap")
        ],
        [
            InlineKeyboardButton("📖 الملخص الشامل (PDF)", callback_data="gen_summary"),
            InlineKeyboardButton("📌 المصطلحات التخصصية (PDF)", callback_data="gen_terms")
        ],
        [
            InlineKeyboardButton("📢 اشترك في القناة", url="https://t.me/Lab3z")
        ]
    ])

def get_mcq_count_keyboard(mode):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("5", callback_data=f"gen_{mode}_5"),
            InlineKeyboardButton("10", callback_data=f"gen_{mode}_10"),
            InlineKeyboardButton("15", callback_data=f"gen_{mode}_15")
        ],
        [
            InlineKeyboardButton("20", callback_data=f"gen_{mode}_20"),
            InlineKeyboardButton("25", callback_data=f"gen_{mode}_25"),
            InlineKeyboardButton("30", callback_data=f"gen_{mode}_30")
        ],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_main")]
    ])

async def edit_menu(query, text, reply_markup=None):
    try:
        if query.message.photo:
            await query.edit_message_caption(caption=text, reply_markup=reply_markup)
        else:
            await query.edit_message_text(text=text, reply_markup=reply_markup)
    except Exception as e:
        logging.error(f"Termux UI Edit Error: {e}")
        try:
            await query.message.reply_text(text, reply_markup=reply_markup)
        except:
            pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً بك. يرجى إرسال ملف المحاضرة (PDF).")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc.file_name.lower().endswith('.pdf'):
        await update.message.reply_text("يرجى إرسال ملف بصيغة PDF فقط.")
        return

    chat_id = update.effective_chat.id
    async with get_chat_lock(chat_id):
        status_msg = await update.message.reply_text("جارٍ معالجة الملف...")
        file = await context.bot.get_file(doc.file_id)
        file_path = f"temp_{doc.file_id}.pdf"
        await file.download_to_drive(file_path)

        try:
            extracted_text = await asyncio.to_thread(read_pdf_sync, file_path)
        except Exception as e:
            logging.error(f"PDF Read Error: {e}", exc_info=True)
            extracted_text = ""
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

        if not extracted_text or len(extracted_text.strip()) < 20:
            await status_msg.delete()
            await update.message.reply_text("يرجى إرسال المحاضرة الأصلية غير المترجمة والمعدلة لكي يتمكن البوت من معالجتها بالشكل الصحيح.")
            return

        user_sessions[chat_id] = {
            "text": extracted_text[:32000],
            "filename": doc.file_name
        }
        
        await status_msg.delete()
        
        user_photo = await get_user_photo_id(context, update.effective_user.id)
        user_name = update.effective_user.first_name or "طالبنا العزيز"

        menu_caption = (
            f"أهلاً {user_name} 👋\n"
            "تمت معالجة المحاضرة. اختر المحتوى المطلوب:"
        )

        try:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=user_photo,
                caption=menu_caption,
                reply_markup=get_main_keyboard()
            )
        except Exception as e:
            logging.error(f"Send Photo Error: {e}")
            await update.message.reply_text(
                menu_caption,
                reply_markup=get_main_keyboard()
            )

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in user_sessions:
        await update.message.reply_text("يرجى إرسال ملف PDF أولاً.")
        return

    async with get_chat_lock(chat_id):
        user_query = update.message.text
        file_text = user_sessions[chat_id]["text"]
        
        wait_msg = await update.message.reply_text("جارٍ تحليل الإجابة...")
        
        sys_p = "أنت أستاذ جامعي ومستشار تشخيصي في التحليلات المرضية. أجب مباشرة وبدقة متناهية بناءً على المحاضرة دون أي مقدمات."
        prompt = f"""أجب عن سؤال الطالب بناءً على المحاضرة مباشرة:
نص المحاضرة:
{file_text}
سؤال الطالب: {user_query}"""

        try:
            answer = await asyncio.to_thread(call_groq, prompt, False, sys_p, 8192, True, None, 3.0)
            await wait_msg.delete()
            await send_long_message(update.message, answer)
        except Exception as e:
            logging.error(f"Text Processing Error: {e}", exc_info=True)
            await wait_msg.edit_text("حدث خطأ غير متوقع، يرجى المحاولة لاحقاً.")

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat_id
    data = query.data
    
    if data == "back_main":
        if chat_id in user_sessions:
            await edit_menu(query, "اختر المحتوى المطلوب:", reply_markup=get_main_keyboard())
        else:
            await edit_menu(query, "انتهت الجلسة. يرجى إعادة إرسال الملف.")
        return

    if chat_id not in user_sessions:
        await edit_menu(query, "انتهت الجلسة. يرجى إعادة إرسال الملف.")
        return

    # تأمين العمليات لتتم بالتوالي منعاً للضغط على السيرفر
    async with get_chat_lock(chat_id):
        allowed, limit_msg = check_rate_limit(query.from_user)
        if not allowed:
            await query.answer(limit_msg, show_alert=True)
            await query.message.reply_text(limit_msg)
            return

        text = user_sessions[chat_id]["text"]

        if data in ["menu_mcq_ar", "menu_mcq_tr", "menu_mcq_en"]:
            mode = data.split("_")[-1]
            await edit_menu(query, "حدد العدد:", reply_markup=get_mcq_count_keyboard(mode))
            return

        if data.startswith("gen_") and not data.startswith("gen_mindmap") and not data.startswith("gen_flashcards") and not data.startswith("gen_summary") and not data.startswith("gen_terms") and not data.startswith("gen_cases") and not data.startswith("gen_essay") and not data.startswith("gen_essay_tr") and not data.startswith("gen_tf_reasoning") and not data.startswith("gen_bank"):
            parts = data.split("_")
            mode, count = parts[1], int(parts[2])
            await edit_menu(query, f"جارٍ الإعداد...")
            try:
                questions = await generate_mcq_batch(text, count, mode)
                increment_usage(query.from_user)
                for idx, q in enumerate(questions):
                    opts = [o[:100] for o in q["options"]]
                    await context.bot.send_poll(
                        chat_id=chat_id,
                        question=q["question"][:300],
                        options=opts,
                        type="quiz",
                        correct_option_id=q["correct_option_id"],
                        explanation=q.get("explanation", "")[:200]
                    )
                    await asyncio.sleep(0.3)
                await query.message.delete()
            except Exception as e:
                logging.error(f"MCQ Generation Error: {e}", exc_info=True)
                await query.message.reply_text("حدث خطأ أثناء إعداد الأسئلة، يرجى المحاولة لاحقاً.")
            return

        if data == "gen_bank":
            await edit_menu(query, "جارٍ الإعداد...")
            sys_p = "أنت أستاذ جامعي ومحاضر تخصصي في التحليلات المرضية. صغ بنك أسئلة امتحان شامل وموسع ومباشر بالإنجليزية مع تنظيم الخيارات عمودياً وتحتها الترجمة العربية مباشرة بدون أي سرديات أو مقدمات."
            prompt = f"""أنشئ بنك أسئلة امتحان شامل ودقيق (أكثر من 20 سؤالاً) من النص أدناه بدون أي مقدمات أو سرديات:
القواعد:
1. السؤال بالإنجليزية ثم تحته الترجمة العربية مباشرة بدون فواصل.
2. الخيارات مرتبة عمودياً (A, B, C, D) وتحتها ترجمتها العربية.
3. التنسيق:
Question: [English question]
([الترجمة العربية])
A) [Option 1]
B) [Option 2]
C) [Option 3]
D) [Option 4]
([ترجمة الخيارات])
Answer: [Correct Letter]
Explanation: [Explanation]
([التعليل])

نص المحاضرة:
{text}"""
            try:
                res_text = await asyncio.to_thread(call_groq, prompt, False, sys_p, 24576, False, "low", 8.0)
                if not res_text or len(res_text.strip()) < 10:
                    raise Exception("فشل التوليد.")
                pdf_path = await asyncio.to_thread(create_pdf, "بنك الأسئلة الشامل", res_text, "bank", False)
                increment_usage(query.from_user)
                with open(pdf_path, 'rb') as pdf_file:
                    await context.bot.send_document(chat_id=chat_id, document=pdf_file, filename="بنك_الاسئلة.pdf")
                await query.message.delete()
                if os.path.exists(pdf_path):
                    os.remove(pdf_path)
            except Exception as e:
                logging.error(f"Bank Generation Error: {e}", exc_info=True)
                await query.message.reply_text("حدث خطأ، يرجى المحاولة لاحقاً.")
            return

        if data == "gen_cases":
            await edit_menu(query, "جارٍ الإعداد...")
            sys_p = "أنت طبيب استشاري ومختص أكاديمي دقيق في التحليلات المرضية. بدون أي مقدمات أو سرديات."
            prompt = f"""أنشئ بنكاً موسعاً ومضاعفاً من الحالات السريرية الطبية الاحترافية (أكثر من 20 حالة) مستخرجة من النص بالشروط التالية وبدون أي مقدمات:
1. كل حالة في مربع واحد متكامل دون أرقام أو عناوين مثل Case.
2. الكيس السريري بالإنجليزية بإيجاز شديد وتحته الترجمة العربية.
3. الخيارات مرتبة عمودياً (A, B, C, D) وتحتها ترجمتها.
4. التنسيق:
[Concise English clinical case]
([الترجمة العربية])
A) ...
B) ...
C) ...
D) ...
([ترجمة الخيارات])
Answer: [...]
Explanation: [...]

نص المحاضرة:
{text}"""
            try:
                res_text = await asyncio.to_thread(call_groq, prompt, False, sys_p, 24576, False, "low", 8.0)
                if not res_text or len(res_text.strip()) < 10:
                    raise Exception("فشل التوليد.")
                pdf_path = await asyncio.to_thread(create_pdf, "الحالات السريرية", res_text, "cases", False)
                increment_usage(query.from_user)
                with open(pdf_path, 'rb') as pdf_file:
                    await context.bot.send_document(chat_id=chat_id, document=pdf_file, filename="الحالات_السريرية.pdf")
                await query.message.delete()
                if os.path.exists(pdf_path):
                    os.remove(pdf_path)
            except Exception as e:
                logging.error(f"Cases Generation Error: {e}", exc_info=True)
                await query.message.reply_text("حدث خطأ، يرجى المحاولة لاحقاً.")
            return

        if data == "gen_essay":
            await edit_menu(query, "جارٍ الإعداد...")
            sys_p = "اكتب حالة واحدة لكل مرض في المحاضرة وبترتيبها. وصف الحالة نحو 35–40 كلمة. أضف أربعة أسئلة سهلة فقط: ثلاثة قصيرة وواحد صح/خطأ. اعتمد على المحاضرة دون حذف مرض أو اختلاق معلومة، ولا تكتب الإجابات."
            prompt = f"""اكتب بالإنجليزية فقط، ومن معلومات المحاضرة وحدها.
احصر الأمراض المسماة في متن المحاضرة وعناوينها وجداولها وقوائمها، وتجاهل المراجع. أنشئ حالة واحدة مستقلة لكل مرض، بترتيب ظهوره؛ لا تحذف أو تدمج أو تكرر أي مرض.
لكل حالة: اكتب وصفاً واضحاً من نحو 35–40 كلمة في فقرة واحدة، مناسباً لسطرين إلى سطرين ونصف في PDF، ولا تذكر اسم المرض ولا تخترع تفاصيل. إذا شحت المعلومات فاستعمل المتاح ولا تحذف الحالة.
ثم اكتب أربعة أسئلة فقط: ثلاثة أسئلة صفية شائعة ومباشرة، لكل منها جواب من كلمة أو كلمتين، وسؤال واحد بسيط غير ملتبس بصيغة True/False. اجعلها سهلة ومن الحقائق الأساسية المذكورة (التشخيص عند وضوح القرائن، العامل المسبب، العلامة، الفحص، الانتقال أو المضاعفة). لا تطلب شرحاً أو تعليلاً أو مقارنة ولا تكتب الإجابات.
افصل الحالات بـ `###CASE###` في سطر مستقل، وضع كل سؤال في سطر. تحقق قبل الإخراج من وجود حالة لكل مرض وأربعة أسئلة فقط لكل حالة؛ لا تطبع قائمة الأمراض.

نص المحاضرة:
{text}"""
            try:
                res_text = await asyncio.to_thread(call_groq, prompt, False, sys_p, 8192, False, "low", 8.0)
                if not res_text or len(res_text.strip()) < 10:
                    raise Exception("فشل التوليد.")
                pdf_path = await asyncio.to_thread(create_unified_pdf, "كيسات المقالي الأكاديمية", res_text, "essay", False)
                increment_usage(query.from_user)
                with open(pdf_path, 'rb') as pdf_file:
                    await context.bot.send_document(chat_id=chat_id, document=pdf_file, filename="كيسات_Essay.pdf")
                await query.message.delete()
                if os.path.exists(pdf_path):
                    os.remove(pdf_path)
            except Exception as e:
                logging.error(f"Essay Cases Generation Error: {e}", exc_info=True)
                await query.message.reply_text("حدث خطأ، يرجى المحاولة لاحقاً.")
            return

        if data == "gen_essay_tr":
            await edit_menu(query, "جارٍ الإعداد...")
            sys_p = "اكتب حالة واحدة لكل مرض في المحاضرة وبترتيبها. وصف إنجليزي نحو 35–40 كلمة وترجمته العربية فقرتان موجزتان. أضف أربعة أسئلة سهلة فقط، ثلاثة قصيرة وواحد صح/خطأ، وترجم كل سؤال تحته. لا تحذف مرضاً ولا تخترع معلومة ولا تكتب الإجابات."
            prompt = f"""اكتب بالإنجليزية والعربية اعتماداً على المحاضرة وحدها.
احصر الأمراض المسماة في متن المحاضرة وعناوينها وجداولها وقوائمها، وتجاهل المراجع. أنشئ حالة واحدة مستقلة لكل مرض بترتيب ظهوره؛ لا تحذف أو تدمج أو تكرر أي مرض.
لكل حالة: اكتب وصفاً إنجليزياً واضحاً من نحو 35–40 كلمة في فقرة واحدة، ثم ترجمته العربية كاملة وموجزة في فقرة واحدة تحته. اجعل الوصفين مناسبين لنحو سطرين إلى سطرين ونصف لكل منهما في PDF، ولا تذكر اسم المرض ولا تخترع تفاصيل. إذا شحت المعلومات فاستعمل المتاح ولا تحذف الحالة.
ثم اكتب أربعة أسئلة فقط: ثلاثة أسئلة صفية شائعة ومباشرة، لكل منها جواب من كلمة أو كلمتين، وسؤال واحد بسيط غير ملتبس بصيغة True/False. اجعلها سهلة ومن الحقائق الأساسية المذكورة؛ لا تطلب شرحاً أو تعليلاً أو مقارنة ولا تكتب الإجابات. اكتب كل سؤال بالإنجليزية وتحته ترجمته العربية مباشرة.
افصل الحالات بـ `###CASE###` في سطر مستقل. تحقق من وجود حالة لكل مرض وأربعة أسئلة فقط لكل حالة؛ لا تطبع قائمة الأمراض أو مفتاح الإجابات.

نص المحاضرة:
{text}"""
            try:
                res_text = await asyncio.to_thread(call_groq, prompt, False, sys_p, 8192, False, "low", 8.0)
                if not res_text or len(res_text.strip()) < 10:
                    raise Exception("فشل التوليد.")
                pdf_path = await asyncio.to_thread(create_unified_pdf, "كيسات المقالي المترجمة", res_text, "essay_tr", False)
                increment_usage(query.from_user)
                with open(pdf_path, 'rb') as pdf_file:
                    await context.bot.send_document(chat_id=chat_id, document=pdf_file, filename="كيسات_Essay_مترجم.pdf")
                await query.message.delete()
                if os.path.exists(pdf_path):
                    os.remove(pdf_path)
            except Exception as e:
                logging.error(f"Essay Translated Cases Generation Error: {e}", exc_info=True)
                await query.message.reply_text("حدث خطأ، يرجى المحاولة لاحقاً.")
            return

        if data == "gen_tf_reasoning":
            await edit_menu(query, "جارٍ الإعداد...")
            sys_p = "أنت أستاذ جامعي وخبير امتحانات تخصصي لمرحلة رابعة تحليلات مرضية بدون أي سرديات."
            prompt = f"""أنشئ أسئلة صح وخطأ وتعليلات من المحاضرة بدون أي مقدمات:
Statement: [English]
([الترجمة العربية])
Answer: [TRUE/FALSE]
([التعليل])

نص المحاضرة:
{text}"""
            try:
                res_text = await asyncio.to_thread(call_groq, prompt, False, sys_p, 16384, False, "low", 8.0)
                if not res_text or len(res_text.strip()) < 10:
                    raise Exception("فشل التوليد.")
                pdf_path = await asyncio.to_thread(create_pdf, "الصح والخطأ والتعليل", res_text, "tf_reasoning", False)
                increment_usage(query.from_user)
                with open(pdf_path, 'rb') as pdf_file:
                    await context.bot.send_document(chat_id=chat_id, document=pdf_file, filename="الصح_والخطا.pdf")
                await query.message.delete()
                if os.path.exists(pdf_path):
                    os.remove(pdf_path)
            except Exception as e:
                logging.error(f"TF Reasoning Generation Error: {e}", exc_info=True)
                await query.message.reply_text("حدث خطأ، يرجى المحاولة لاحقاً.")
            return

        if data == "gen_mindmap":
            await edit_menu(query, "جارٍ الإعداد...")
            sys_p = "أنت خبير في بناء الخرائط الذهنية الطبية الشاملة لمرحلة رابعة تحليلات مرضية. أرجع JSON مصفوفة حصراً بدون مقدمات."
            prompt = f"""أنشئ خريطة ذهنية تشخيصية ومكثفة للمحاضرة بصيغة valid json بدون أي سرديات:
[
  {{
    "title": "ETIOLOGY & PATHOGENESIS",
    "points": ["Genetic Risk -> HLA", "Immune Trigger -> Autoantibody"]
  }},
  {{
    "title": "CLINICAL MANIFESTATIONS",
    "points": ["Systemic Effects -> Fever", "Renal Findings -> Proteinuria"]
  }},
  {{
    "title": "DIAGNOSTIC PROTOCOL",
    "points": ["Screening -> ANA", "Confirmatory -> Anti-dsDNA"]
  }},
  {{
    "title": "LAB FINDINGS",
    "points": ["Serology -> Panel", "Hematology -> Anemia"]
  }}
]

نص المحاضرة:
{text}"""
            try:
                res_text = await asyncio.to_thread(call_groq, prompt, True, sys_p, 8192, False, "low", 8.0)
                if not res_text or len(res_text.strip()) < 10:
                    raise Exception("فشل التوليد.")
                pdf_path = await asyncio.to_thread(create_mindmap_pdf, "الخريطة الذهنية", res_text, "mindmap")
                increment_usage(query.from_user)
                with open(pdf_path, 'rb') as pdf_file:
                    await context.bot.send_document(chat_id=chat_id, document=pdf_file, filename="الخريطة_الذهنية.pdf")
                await query.message.delete()
                if os.path.exists(pdf_path):
                    os.remove(pdf_path)
            except Exception as e:
                logging.error(f"Mindmap Generation Error: {e}", exc_info=True)
                await query.message.reply_text("حدث خطأ، يرجى المحاولة لاحقاً.")
            return

        if data == "gen_flashcards":
            await edit_menu(query, "جارٍ الإعداد...")
            sys_p = "أنت أستاذ متخصص في إعداد بطاقات الاستذكار بالإنجليزية وتحتها الترجمة العربية بدون أي سرديات أو خطوط فاصلة."
            prompt = f"""أنشئ بطاقات استذكار تخصصية تغطي المحاضرة بدون أي مقدمات أو فواصل:
Q: [English Question]
A: [English Answer]
([الترجمة العربية])

نص المحاضرة:
{text}"""
            try:
                res_text = await asyncio.to_thread(call_groq, prompt, False, sys_p, 16384, False, "low", 8.0)
                if not res_text or len(res_text.strip()) < 10:
                    raise Exception("فشل التوليد.")
                pdf_path = await asyncio.to_thread(create_pdf, "بطاقات الاستذكار", res_text, "flashcards", False)
                increment_usage(query.from_user)
                with open(pdf_path, 'rb') as pdf_file:
                    await context.bot.send_document(chat_id=chat_id, document=pdf_file, filename="البطاقات.pdf")
                await query.message.delete()
                if os.path.exists(pdf_path):
                    os.remove(pdf_path)
            except Exception as e:
                logging.error(f"Flashcards Generation Error: {e}", exc_info=True)
                await query.message.reply_text("حدث خطأ، يرجى المحاولة لاحقاً.")
            return

        if data == "gen_summary":
            await edit_menu(query, "جارٍ الإعداد...")
            sys_p = "أنت خبير ومحاضر تخصصي في التحليلات المرضية. أعد ملخصاً أكاديمياً بالإنجليزية وتحته الترجمة العربية مباشرة بدون أي سرديات."
            prompt = f"""أعد ملخصاً شاملاً للمحاضرة بدون أي مقدمات:
Concept X: [Name]
- [English Sentence]
([الترجمة العربية])

نص المحاضرة:
{text}"""
            try:
                res_text = await asyncio.to_thread(call_groq, prompt, False, sys_p, 16384, False, "low", 8.0)
                if not res_text or len(res_text.strip()) < 10:
                    raise Exception("فشل التوليد.")
                
                processed_lines = []
                prev_line = ""
                for line in res_text.split('\n'):
                    line_str = line.strip()
                    if line_str and line_str == prev_line and not is_arabic(line_str) and not line_str.lower().startswith('concept'):
                        continue
                    processed_lines.append(line)
                    prev_line = line_str
                    
                final_text = "\n".join(processed_lines)

                pdf_path = await asyncio.to_thread(create_pdf, "الملخص الشامل", final_text, "summary", False)
                increment_usage(query.from_user)
                with open(pdf_path, 'rb') as pdf_file:
                    await context.bot.send_document(chat_id=chat_id, document=pdf_file, filename="الملخص.pdf")
                await query.message.delete()
                if os.path.exists(pdf_path):
                    os.remove(pdf_path)
            except Exception as e:
                logging.error(f"Summary Generation Error: {e}", exc_info=True)
                await query.message.reply_text("حدث خطأ، يرجى المحاولة لاحقاً.")
            return

        if data == "gen_terms":
            await edit_menu(query, "جارٍ الإعداد...")
            sys_p = "أنت أستاذ جامعي متخصص في التحليلات المرضية. استخرج المصطلحات العلمية الواردة في المحاضرة بدقة وبأسلوب أكاديمي رصين، دون أي مقدمات أو عبارات إنشائية ودون أي تسميات أو كلمات مفتاحية."
            prompt = f"""استخرج جميع المصطلحات العلمية المهمة الواردة في المحاضرة. اعرض كل مصطلح في مقطع مستقل بالترتيب التالي، وافصل بين كل مصطلح والذي يليه بسطر فارغ واحد:

[المصطلح بالإنجليزية]
[مقابله العربي المباشر]
[تعريف علمي دقيق ومختصر بالإنجليزية]
[ترجمة التعريف بالعربية]

تعليمات صارمة:
1. ابدأ بالمصطلح مباشرة دون أي كلمات مثل Term أو Definition أو Title أو Explain ودون ترقيم أو عناوين أو عبارات تمهيدية.
2. التزم حرفياً بمحتوى المحاضرة ولا تضف معلومات من خارجها.
3. غطِّ كل المصطلحات الجوهرية في المحاضرة دون تكرار.

نص المحاضرة:
{text}"""
            try:
                res_text = await asyncio.to_thread(call_groq, prompt, False, sys_p, 16384, False, "low", 8.0)
                if not res_text or len(res_text.strip()) < 10:
                    raise Exception("فشل التوليد.")
                pdf_path = await asyncio.to_thread(create_pdf, "المصطلحات التخصصية", res_text, "terms", False)
                increment_usage(query.from_user)
                with open(pdf_path, 'rb') as pdf_file:
                    await context.bot.send_document(chat_id=chat_id, document=pdf_file, filename="المصطلحات.pdf")
                await query.message.delete()
                if os.path.exists(pdf_path):
                    os.remove(pdf_path)
            except Exception as e:
                logging.error(f"Terms Generation Error: {e}", exc_info=True)
                await query.message.reply_text("حدث خطأ، يرجى المحاولة لاحقاً.")
            return

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(CallbackQueryHandler(handle_button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    print("تم تشغيل البوت بنجاح...")
    application.run_polling()

if __name__ == '__main__':
    main()




