import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import sqlite3

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

ADMIN_ID = 7872701674

class Database:
    def __init__(self):
        self.conn = sqlite3.connect('applications.db', check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                name TEXT,
                age INTEGER,
                skills TEXT,
                experience_years TEXT,
                previous_experience TEXT,
                status TEXT DEFAULT 'pending',
                admin_reply TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

    def add_application(self, user_id: int, username: str, name: str, age: int, 
                       skills: str, experience_years: str, previous_experience: str):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO applications 
            (user_id, username, name, age, skills, experience_years, previous_experience)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, username, name, age, skills, experience_years, previous_experience))
        self.conn.commit()
        return cursor.lastrowid

    def get_application(self, application_id: int):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM applications WHERE id = ?', (application_id,))
        return cursor.fetchone()

    def get_pending_applications(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM applications WHERE status = "pending" ORDER BY created_at DESC')
        return cursor.fetchall()

    def get_all_applications(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM applications ORDER BY created_at DESC')
        return cursor.fetchall()

    def update_application_status(self, application_id: int, status: str, admin_reply: str = None):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE applications 
            SET status = ?, admin_reply = ?
            WHERE id = ?
        ''', (status, admin_reply, application_id))
        self.conn.commit()

    def delete_application(self, application_id: int):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM applications WHERE id = ?', (application_id,))
        self.conn.commit()

db = Database()
user_states = {}

def get_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("Подать заявку", callback_data="start_application")],
        [InlineKeyboardButton("Мои заявки", callback_data="my_applications")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("Все заявки", callback_data="admin_all_applications")],
        [InlineKeyboardButton("Ожидающие", callback_data="admin_pending_applications")],
        [InlineKeyboardButton("Статистика", callback_data="admin_stats")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_application_action_keyboard(application_id: int):
    keyboard = [
        [
            InlineKeyboardButton("Принять", callback_data=f"accept_{application_id}"),
            InlineKeyboardButton("Отклонить", callback_data=f"reject_{application_id}")
        ],
        [InlineKeyboardButton("Ответить", callback_data=f"reply_{application_id}")],
        [InlineKeyboardButton("Назад", callback_data="admin_all_applications")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_cancel_keyboard():
    keyboard = [
        [InlineKeyboardButton("Отмена", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id == ADMIN_ID:
        await update.message.reply_text("Панель администратора", reply_markup=get_admin_keyboard())
    else:
        await update.message.reply_text("Главное меню:", reply_markup=get_main_menu_keyboard())

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return
    
    await update.message.reply_text("Панель администратора", reply_markup=get_admin_keyboard())

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "start_application":
        if user_id == ADMIN_ID:
            await query.edit_message_text("Администратор не может подавать заявки.")
            return
            
        user_states[user_id] = "waiting_name"
        await query.edit_message_text(
            "1. Как вас зовут?",
            reply_markup=get_cancel_keyboard()
        )
    
    elif data == "my_applications":
        await show_user_applications(update, context)
    
    elif data == "main_menu":
        if user_id == ADMIN_ID:
            await query.edit_message_text("Панель администратора", reply_markup=get_admin_keyboard())
        else:
            await query.edit_message_text("Главное меню:", reply_markup=get_main_menu_keyboard())
    
    elif data == "cancel":
        if user_id in user_states:
            del user_states[user_id]
        await query.edit_message_text("Заполнение анкеты отменено.", reply_markup=get_main_menu_keyboard())
    
    elif data == "admin_all_applications":
        if user_id != ADMIN_ID:
            await query.edit_message_text("У вас нет доступа.")
            return
        await show_all_applications(update, context)
    
    elif data == "admin_pending_applications":
        if user_id != ADMIN_ID:
            await query.edit_message_text("У вас нет доступа.")
            return
        await show_pending_applications(update, context)
    
    elif data == "admin_stats":
        if user_id != ADMIN_ID:
            await query.edit_message_text("У вас нет доступа.")
            return
        await show_stats(update, context)
    
    elif data.startswith("view_application_"):
        if user_id != ADMIN_ID:
            await query.edit_message_text("У вас нет доступа.")
            return
        application_id = int(data.split("_")[2])
        await show_application_details(update, context, application_id)
    
    elif data.startswith("accept_"):
        if user_id != ADMIN_ID:
            await query.edit_message_text("У вас нет доступа.")
            return
        application_id = int(data.split("_")[1])
        await accept_application(update, context, application_id)
    
    elif data.startswith("reject_"):
        if user_id != ADMIN_ID:
            await query.edit_message_text("У вас нет доступа.")
            return
        application_id = int(data.split("_")[1])
        user_states[f"reject_{user_id}"] = application_id
        await query.edit_message_text(
            "Напишите причину отказа:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Отмена", callback_data=f"view_application_{application_id}")]])
        )
    
    elif data.startswith("reply_"):
        if user_id != ADMIN_ID:
            await query.edit_message_text("У вас нет доступа.")
            return
        application_id = int(data.split("_")[1])
        user_states[f"reply_{user_id}"] = application_id
        await query.edit_message_text(
            "Напишите ответ пользователю:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Отмена", callback_data=f"view_application_{application_id}")]])
        )

async def show_user_applications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    applications = db.get_all_applications()
    user_applications = [app for app in applications if app[1] == user_id]
    
    if not user_applications:
        await query.edit_message_text(
            "У вас нет поданых заявок.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Подать заявку", callback_data="start_application")]])
        )
        return
    
    text = "Ваши заявки:\n\n"
    for app in user_applications[:10]:
        status_emoji = "⏳" if app[8] == "pending" else "✅" if app[8] == "accepted" else "❌"
        text += f"{status_emoji} Заявка #{app[0]} - {app[8]}\n"
        text += f"📅 {app[10]}\n\n"
    
    await query.edit_message_text(text, reply_markup=get_main_menu_keyboard())

async def show_all_applications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    applications = db.get_all_applications()
    
    if not applications:
        await query.edit_message_text("Нет заявок.", reply_markup=get_admin_keyboard())
        return
    
    text = "Все заявки:\n\n"
    keyboard = []
    
    for app in applications[:15]:
        status_emoji = "⏳" if app[8] == "pending" else "✅" if app[8] == "accepted" else "❌"
        text += f"{status_emoji} #{app[0]} - {app[3]} ({app[4]} лет) - {app[8]}\n"
        keyboard.append([InlineKeyboardButton(
            f"{status_emoji} #{app[0]} - {app[3]}", 
            callback_data=f"view_application_{app[0]}"
        )])
    
    keyboard.append([InlineKeyboardButton("Назад", callback_data="main_menu")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_pending_applications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    applications = db.get_pending_applications()
    
    if not applications:
        await query.edit_message_text("Нет ожидающих заявок.", reply_markup=get_admin_keyboard())
        return
    
    text = "Ожидающие заявки:\n\n"
    keyboard = []
    
    for app in applications[:15]:
        text += f"#{app[0]} - {app[3]} ({app[4]} лет)\n"
        keyboard.append([InlineKeyboardButton(
            f"#{app[0]} - {app[3]}", 
            callback_data=f"view_application_{app[0]}"
        )])
    
    keyboard.append([InlineKeyboardButton("Назад", callback_data="main_menu")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_application_details(update: Update, context: ContextTypes.DEFAULT_TYPE, application_id: int):
    query = update.callback_query
    application = db.get_application(application_id)
    
    if not application:
        await query.edit_message_text("Заявка не найдена.", reply_markup=get_admin_keyboard())
        return
    
    status_emoji = "⏳" if application[8] == "pending" else "✅" if application[8] == "accepted" else "❌"
    status_text = "Ожидает" if application[8] == "pending" else "Принята" if application[8] == "accepted" else "Отклонена"
    
    text = f"""
{status_emoji} Заявка #{application[0]}

Имя: {application[3]}
Возраст: {application[4]}
Навыки: {application[5]}
Опыт в студии: {application[6]}
Предыдущий опыт: {application[7]}
Username: @{application[2]}
User ID: {application[1]}
Статус: {status_text}
Подана: {application[10]}
"""
    
    if application[9]:
        text += f"\nОтвет админа: {application[9]}"
    
    await query.edit_message_text(text, reply_markup=get_application_action_keyboard(application_id))

async def accept_application(update: Update, context: ContextTypes.DEFAULT_TYPE, application_id: int):
    query = update.callback_query
    application = db.get_application(application_id)
    
    db.update_application_status(application_id, "accepted", "Заявка принята!")
    
    try:
        await context.bot.send_message(
            application[1],
            f"Ваша заявка #{application_id} принята!\n\n"
            "Администратор рассмотрел вашу заявку и принял ее.\n"
            "С вами свяжутся в ближайшее время!"
        )
    except Exception as e:
        logger.error(f"Не удалось уведомить пользователя: {e}")
    
    await context.bot.send_message(
        ADMIN_ID,
        f"Вы приняли заявку #{application_id} от @{application[2]}"
    )
    
    await query.edit_message_text(f"Заявка #{application_id} принята!", reply_markup=get_admin_keyboard())

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    applications = db.get_all_applications()
    
    total = len(applications)
    pending = len([app for app in applications if app[8] == "pending"])
    accepted = len([app for app in applications if app[8] == "accepted"])
    rejected = len([app for app in applications if app[8] == "rejected"])
    
    text = f"""
Статистика заявок:

Всего заявок: {total}
Ожидают: {pending}
Принято: {accepted}
Отклонено: {rejected}
"""
    
    await query.edit_message_text(text, reply_markup=get_admin_keyboard())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if user_id in user_states:
        state = user_states[user_id]
        username = update.effective_user.username or "Без username"
        
        if state == "waiting_name":
            context.user_data['name'] = text
            user_states[user_id] = "waiting_age"
            await update.message.reply_text("2. Сколько вам лет?", reply_markup=get_cancel_keyboard())
        
        elif state == "waiting_age":
            try:
                age = int(text)
                if age < 14 or age > 100:
                    await update.message.reply_text("Возраст должен быть от 14 до 100 лет.")
                    return
                context.user_data['age'] = age
                user_states[user_id] = "waiting_skills"
                await update.message.reply_text(
                    "3. Что вы умеете? (скриптинг, билдинг и т.д.)",
                    reply_markup=get_cancel_keyboard()
                )
            except ValueError:
                await update.message.reply_text("Пожалуйста, введите корректный возраст.")
        
        elif state == "waiting_skills":
            context.user_data['skills'] = text
            user_states[user_id] = "waiting_experience"
            await update.message.reply_text(
                "4. Сколько вы уже занимаетесь студией?",
                reply_markup=get_cancel_keyboard()
            )
        
        elif state == "waiting_experience":
            context.user_data['experience_years'] = text
            user_states[user_id] = "waiting_previous_experience"
            await update.message.reply_text(
                "5. Был ли у вас опыт работы? Опишите подробнее.",
                reply_markup=get_cancel_keyboard()
            )
        
        elif state == "waiting_previous_experience":
            context.user_data['previous_experience'] = text
            
            application_id = db.add_application(
                user_id=user_id,
                username=username,
                name=context.user_data['name'],
                age=context.user_data['age'],
                skills=context.user_data['skills'],
                experience_years=context.user_data['experience_years'],
                previous_experience=context.user_data['previous_experience']
            )
            
            application_text = f"""
Новая заявка #{application_id}

Имя: {context.user_data['name']}
Возраст: {context.user_data['age']}
Навыки: {context.user_data['skills']}
Опыт в студии: {context.user_data['experience_years']}
Предыдущий опыт: {context.user_data['previous_experience']}
Username: @{username}
User ID: {user_id}
"""
            
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("Посмотреть заявку", callback_data=f"view_application_{application_id}")
            ]])
            
            await context.bot.send_message(ADMIN_ID, application_text, reply_markup=keyboard)
            
            del user_states[user_id]
            context.user_data.clear()
            
            await update.message.reply_text(
                "Ваша заявка отправлена на рассмотрение!",
                reply_markup=get_main_menu_keyboard()
            )
    
    elif user_id == ADMIN_ID:
        for key in list(user_states.keys()):
            if key.startswith(f"reject_{user_id}"):
                application_id = user_states[key]
                application = db.get_application(application_id)
                
                db.update_application_status(application_id, "rejected", text)
                
                try:
                    await context.bot.send_message(
                        application[1],
                        f"Ваша заявка #{application_id} отклонена.\n\n"
                        f"Причина: {text}"
                    )
                except Exception as e:
                    logger.error(f"Не удалось уведомить пользователя: {e}")
                
                await context.bot.send_message(ADMIN_ID, f"Вы отклонили заявку #{application_id}")
                
                del user_states[key]
                await update.message.reply_text(f"Заявка #{application_id} отклонена.", reply_markup=get_admin_keyboard())
                return
            
            elif key.startswith(f"reply_{user_id}"):
                application_id = user_states[key]
                application = db.get_application(application_id)
                
                try:
                    await context.bot.send_message(
                        application[1],
                        f"Ответ на вашу заявку #{application_id}:\n\n{text}"
                    )
                    await update.message.reply_text(f"Ответ отправлен пользователю @{application[2]}")
                except Exception as e:
                    await update.message.reply_text(f"Не удалось отправить ответ: {e}")
                
                del user_states[key]
                return
    
    else:
        await update.message.reply_text("Используйте кнопки меню для навигации.", reply_markup=get_main_menu_keyboard())

def main():
    TOKEN = "8490741720:AAGD6tYEzUtruUAOX4Mp2iOm0VwQHgtNiFc"
    
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin))
    
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Бот запущен...")
    application.run_polling()

if __name__ == '__main__':
    main()
