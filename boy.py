import os
import io
import json
import logging
import asyncio
from aiohttp import web
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegraph import Telegraph

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

telegraph = Telegraph()
telegraph.create_account(short_name='MiniApp_Exec')

# Leitura de Variáveis de Ambiente
TOKEN = os.environ.get("TELEGRAM_TOKEN")
WEB_APP_URL = os.environ.get("WEB_APP_URL")
PORT = int(os.environ.get("PORT", 8080)) # A Railway atribui a porta dinamicamente

if not TOKEN:
    raise ValueError("A variável TELEGRAM_TOKEN não foi encontrada no ambiente.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Bot de Tarefas Executivas: Conversão de Markdown/Rich Text e publicação no Telegraph.\n"
        "Envie /help para comandos operacionais."
    )
    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("Abrir App Executivo", web_app=WebAppInfo(url=WEB_APP_URL))
    ]]) if WEB_APP_URL else None
    
    await update.message.reply_text(text, reply_markup=markup)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "/start - Inicializa a interface principal e o botão da Mini App\n"
        "/help - Exibe esta lista de comandos\n"
        "/tgrich <texto> - Converte sintaxe Markdown para Rich Text nativo do Telegram\n"
        "/mdrich - Responda a uma mensagem para extrair a formatação nativa e receber ficheiro .md"
    )
    await update.message.reply_text(text)

async def tgrich(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Forneça o texto em markdown. Ex: /tgrich *texto*")
        return
    
    text = update.message.text.split(None, 1)[1]
    try:
        await update.message.reply_text(text, parse_mode='MarkdownV2')
    except Exception as e:
        await update.message.reply_text(f"Falha de sintaxe: {e}")

async def mdrich(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Execute este comando respondendo a uma mensagem.")
        return
    
    md_text = update.message.reply_to_message.text_markdown_v2
    
    if not md_text:
        await update.message.reply_text("Sem texto válido na mensagem alvo.")
        return
    
    file_buffer = io.BytesIO(md_text.encode('utf-8'))
    file_buffer.name = "exported_rich_text.md"
    
    await update.message.reply_document(document=file_buffer)

async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data = json.loads(update.message.web_app_data.data)
        
        if data.get('action') == 'publish_telegraph':
            content = data.get('content', '')
            real_title = data.get('title', 'Sem Título')
            custom_path = data.get('path', '').strip()
            
            html_content = content.replace('\n', '<br>')
            
            api_title = custom_path if custom_path else real_title
            if custom_path:
                html_content = f"<h1>{real_title}</h1><br>{html_content}"

            response = telegraph.create_page(
                title=api_title,
                html_content=html_content,
                author_name='App Executivo'
            )
            
            url = response['url']
            await update.message.reply_text(f"Publicado: {url}")
            
    except Exception as e:
        await update.message.reply_text(f"Erro no processamento: {e}")

# --- SERVIDOR WEB ---
async def serve_index(request):
    """Lê e serve o ficheiro index.html na raiz do servidor."""
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            content = f.read()
        return web.Response(text=content, content_type="text/html")
    except FileNotFoundError:
        return web.Response(text="Erro: ficheiro index.html não encontrado no servidor.", status=404)

async def main():
    # 1. Configurar e iniciar a aplicação Telegram
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("tgrich", tgrich))
    application.add_handler(CommandHandler("mdrich", mdrich))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))

    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    # 2. Configurar e iniciar o Servidor Web aiohttp
    web_app = web.Application()
    web_app.router.add_get('/', serve_index)
    
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    logging.info(f"Servidor Web iniciado na porta {PORT}. Bot em execução.")

    # 3. Manter o evento em loop para que os serviços corram continuamente
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())