import os
import re
import datetime, pytz
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, \
    ConversationHandler, Defaults
from db import Database
from functools import partial, wraps

db = Database()
db.create_tables()

GROUP_ID = -495335749
REMINDER_TIME = datetime.time(21, 00)
keyboard = [
    [InlineKeyboardButton("Track Exercise", callback_data='track_exercise')],
    [InlineKeyboardButton("Delete Exercise", callback_data='delete_exercise')],
    [InlineKeyboardButton("View History", callback_data='view_history')],
    [InlineKeyboardButton("Leaderboards", callback_data='leaderboard')],
    [InlineKeyboardButton("Add exam reminder", callback_data='exam')]
]
main_keyboard = InlineKeyboardMarkup(keyboard)

LIST_OF_ADMINS = [148721731]


def restricted(func):
    @wraps(func)
    def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in LIST_OF_ADMINS:
            print("Unauthorized access denied for {}.".format(user_id))
            return
        return func(update, context, *args, **kwargs)

    return wrapped


def remove_job_if_exists(name, context):
    """Remove job with given name. Returns whether job was removed."""
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True


def start(update: Update, context):
    if update.message.chat.type != 'group':
        update.message.reply_text('Please select one of the options:', reply_markup=main_keyboard)
        remove_job_if_exists("daily_exam", context)
        context.job_queue.run_daily(daily_exam_reminder, REMINDER_TIME, context=GROUP_ID, name="daily_exam")
    else:
        update.message.reply_text('Not available in groups. Please PM me.')


def show_back_home(update, context):
    query = update.callback_query
    query.answer()

    remove_job_if_exists("daily_exam", context)
    context.job_queue.run_daily(daily_exam_reminder, REMINDER_TIME, context=GROUP_ID, name="daily_exam")

    text = "Welcome back home! Please select one of the options:"
    query.edit_message_text(text, reply_markup=main_keyboard)
    return ConversationHandler.END


def log_exercise(update, context, exercise=""):
    name = update.message.from_user.first_name
    tele = update.message.from_user.username
    score = update.message.text

    keyboard = [
        [InlineKeyboardButton("Record another", callback_data='track_exercise')],
        [InlineKeyboardButton("Back", callback_data='return_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if exercise == "Run":
        try:
            score = float(score)
            if score < 0:
                raise ValueError
            db.insert_entry(name, tele, exercise, score)
            update.message.reply_text(f"Success! Recorded {score} km for {name}.", reply_markup=reply_markup)
        except ValueError:
            update.message.reply_text(f"Input is wrong, please try again or record 0 km to exit.")
            return "LOG_" + "R"

    else:
        try:
            score = int(score)
            if score < 0:
                raise ValueError
            db.insert_entry(name, tele, exercise, score)
            update.message.reply_text(f"Success! Recorded {score} reps for {name}.", reply_markup=reply_markup)
        except ValueError:
            update.message.reply_text(f"Input is wrong, please try again or record 0 reps to exit.")
            return "LOG_" + exercise[0]
    return ConversationHandler.END


def ask_exercise(update, context):
    query = update.callback_query
    query.answer()
    exercise = query.data[1:]

    if exercise == "P":
        query.edit_message_text("Pull ups selected. Please enter how many pull ups you have done:")
        return "LOG_P"

    elif exercise == "C":
        query.edit_message_text("Core selected. Please enter how many you have done:")
        return "LOG_C"
    elif exercise == "R":
        query.edit_message_text("Run selected. Please enter how far you have ran in km (e.g. 4.6):")
        return "LOG_R"


def choose_exercise(update, context):
    keyboard = [
        [InlineKeyboardButton("Pull ups", callback_data='EP'),
         InlineKeyboardButton("Core", callback_data='EC'),
         InlineKeyboardButton("Run", callback_data='ER')],
        [InlineKeyboardButton("Back", callback_data='return_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        text="Choose exercise: ", reply_markup=reply_markup
    )

    return "selected_exercise"


def choose_exercise_query(update, context):
    query = update.callback_query
    query.answer()
    keyboard = [
        [InlineKeyboardButton("Pull ups", callback_data='EP'),
         InlineKeyboardButton("Core", callback_data='EC'),
         InlineKeyboardButton("Run", callback_data='ER')],
        [InlineKeyboardButton("Back", callback_data='return_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(
        text="Choose exercise: ", reply_markup=reply_markup
    )

    return "selected_exercise"


def delete_exercise(update, context, offset=0, limit=5):
    history = db.get_user_history(update.message.from_user.username, offset)
    history = [list(map(lambda x: str(x), entry)) for entry in history]
    keyboard = [[InlineKeyboardButton(entry[3][5:10] + ": " + str(entry[2]) + " " + entry[1],
                                      callback_data=",".join(entry))] for entry in history]
    keyboard.append([InlineKeyboardButton("More entries", callback_data=f"next_page_{offset + limit}")])
    keyboard.append([InlineKeyboardButton("Back", callback_data="return_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        text=f"Showing entries {offset} to {offset + limit}: ", reply_markup=reply_markup
    )

    return "selected_delete"


def delete_exercise_query(update, context, offset=0, limit=5):
    query = update.callback_query
    query.answer()
    if "next_page" in query.data:
        offset = int(query.data[10:])

    history = db.get_user_history(query.from_user.username, offset)
    history = [list(map(lambda x: str(x), entry)) for entry in history]
    keyboard = [[InlineKeyboardButton(entry[3][5:10] + ": " + str(entry[2]) + " " + entry[1],
                                      callback_data=",".join(entry))] for entry in history]
    keyboard.append([InlineKeyboardButton("More entries", callback_data=f"next_page_{offset + limit}")])
    keyboard.append([InlineKeyboardButton("Back", callback_data="return_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(
        text=f"Showing entries {offset} to {offset + limit}: ", reply_markup=reply_markup
    )

    return "selected_delete"


def confirm_delete(update, context):
    query = update.callback_query
    entry = query.data
    entry = entry.split(",")

    keyboard = [
        [InlineKeyboardButton("Confirm", callback_data=str(entry[0]))],
        [InlineKeyboardButton("Back", callback_data="back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(
        text=f"Are you sure you want to delete {entry[3][5:10]}" + ': ' + str(entry[2]) + " " + entry[1] + '?'
        , reply_markup=reply_markup
    )

    return "confirm_delete"


def process_delete(update, context):
    query = update.callback_query
    query.answer()
    rowid = int(query.data)

    db.delete_entry(rowid)

    keyboard = [
        [InlineKeyboardButton("Delete another", callback_data='delete_exercise')],
        [InlineKeyboardButton("Back", callback_data='return_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    query.edit_message_text(f"Success! Deleted entry.", reply_markup=reply_markup)


def leaderboard(update, context):
    query = update.callback_query
    query.answer()

    w, all_time = db.get_leaderboards()

    all_time = "All time leaders \n" + all_time
    w = "This week's leaders \n" + w + "\n \n"

    keyboard = [
        [InlineKeyboardButton("Back", callback_data='return_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    query.edit_message_text(w + all_time, reply_markup=reply_markup)

    return ConversationHandler.END


def view_history(update, context):
    query = update.callback_query
    tele = query.from_user.username
    query.answer()

    s = db.get_history()

    keyboard = [
        [InlineKeyboardButton("Back", callback_data='return_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    query.edit_message_text(s, reply_markup=reply_markup)

    return ConversationHandler.END


def exam_entry(update, callback):
    query = update.callback_query
    query.answer()

    query.edit_message_text("Enter your exam details (date, start time, end time) in the format: DD/MM HHMM HHMM")
    return "submitted_exam"


def log_exam(update, context, exercise=""):
    name = update.message.from_user.first_name
    tele = update.message.from_user.username
    details = update.message.text

    def valid_input(s):
        shape = bool(re.match("\d{2}/\d{2}\s\d{2}\d{2}\s\d{2}\d{2}", s))
        remove_job_if_exists("daily_exam", context)
        context.job_queue.run_daily(daily_exam_reminder, REMINDER_TIME, context=GROUP_ID, name="daily_exam")
        if shape:
            try:
                a = datetime.datetime(2021, int(s[3:5]), int(s[:2]), int(s[6:8]), int(s[8:10]))
                b = datetime.datetime(2021, int(s[3:5]), int(s[:2]), int(s[11:13]), int(s[13:15]))
                return b > a
            except ValueError:
                return False
        return False

    keyboard = [
        [InlineKeyboardButton("Record another", callback_data='exam')],
        [InlineKeyboardButton("Back", callback_data='return_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if valid_input(details):
        date, startt, end = details[:5], details[6:10], details[11:]
        db.insert_exam(name, tele, date, startt, end)

        send_time = datetime.datetime(2021,
                                      int(date[3:]),
                                      int(date[:2]),
                                      int(startt[:2]),
                                      int(startt[2:])) - datetime.timedelta(minutes=15)
        context.job_queue.run_once(send_message_to_group,
                                   send_time,
                                   context=(GROUP_ID, name, startt, end),
                                   name=f"exam_alert_{str(startt)}_{str(end)}")

        update.message.reply_text(f"Success! Recorded exam on {date} from {startt} to {end} for {name}.",
                                  reply_markup=reply_markup)
    else:
        update.message.reply_text(f"Input is wrong, please try again.")
        return "submitted_exam"

    return ConversationHandler.END


def send_message_to_group(context):
    job = context.job
    chat_id, name, startt, end = job.context
    context.bot.send_message(chat_id, text=f'{name} will be having an exam in 15mins from {startt} to {end}!')


def daily_exam_reminder(context):
    job = context.job
    chat_id = job.context
    tomorrow = pytz.timezone('Asia/Singapore'). \
                   localize(datetime.datetime.now()) + datetime.timedelta(days=1)
    s = db.get_exam_string(tomorrow.day, tomorrow.month)
    if s:
        context.bot.send_message(chat_id, text=s)


def test_message(update, context):
    print(1)
    context.bot.send_message(GROUP_ID, text=f'{context.job_queue.jobs()[0].next_t}')


# Admin functions
@restricted
def get_one(update, context):
    update.message.reply_text(db.get_all())


@restricted
def drop(update, context):
    db.drop_table("")


@restricted
def execute(update, context):
    query = " ".join(context.args)
    r = db.execute_query(query)
    update.message.reply_text(r)


@restricted
def set_query(update, context):
    query = " ".join(context.args)
    db.set_query(query)


@restricted
def change_group_id(update, context):
    cid = context.args[0]
    global GROUP_ID
    GROUP_ID = int(cid)


@restricted
def change_reminder_time(update, context):
    t = context.args[0]
    global REMINDER_TIME
    REMINDER_TIME = datetime.time(int(t[:2]), int(t[2:]))


@restricted
def get_reminder_time(update, context):
    update.message.reply_text(str(REMINDER_TIME))


@restricted
def get_group_id(update, context):
    update.message.reply_text(GROUP_ID)


def main():
    """Run the bot."""
    defaults = Defaults(tzinfo=pytz.timezone('Asia/Singapore'))
    # Create the Updater and pass it your bot's token.
    updater = Updater(os.environ['TOKEN'], defaults=defaults)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CallbackQueryHandler(show_back_home, pattern="return_menu"))
    dispatcher.add_handler(CallbackQueryHandler(leaderboard, pattern="leaderboard"))
    dispatcher.add_handler(CallbackQueryHandler(view_history, pattern="view_history"))
    dispatcher.add_handler(CommandHandler("add_entry", log_exercise))

    # Add exam handler
    dispatcher.add_handler(
        ConversationHandler(
            entry_points=[CallbackQueryHandler(exam_entry, pattern="exam")],
            states={
                "submitted_exam": [MessageHandler(Filters.all, callback=log_exam)],
            },
            fallbacks=[CallbackQueryHandler(exam_entry, pattern="exam")],
            per_message=False
        )
    )
    # Add exercise entry
    dispatcher.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("track_exercise", choose_exercise),
                          CallbackQueryHandler(choose_exercise_query, pattern="track_exercise")],
            states={
                "selected_exercise": [
                    CallbackQueryHandler(ask_exercise, pattern="^E")
                ],
                "LOG_P": [MessageHandler(Filters.all, callback=partial(log_exercise, exercise="Pull Ups"))],
                "LOG_C": [MessageHandler(Filters.all, callback=partial(log_exercise, exercise="Core"))],
                "LOG_R": [MessageHandler(Filters.all, callback=partial(log_exercise, exercise="Run"))],
                "choose_exercise": [CallbackQueryHandler(choose_exercise_query, pattern="track_exercise")],
                # "TIMEOUT": [CallbackQueryHandler(choose_exercise_query, pattern="track_exercise")]
            },
            fallbacks=[CallbackQueryHandler(choose_exercise_query, pattern="track_exercise")],
            per_message=False
        )
    )

    # Delete entry
    dispatcher.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("delete_exercise", delete_exercise),
                          CallbackQueryHandler(delete_exercise_query, pattern="delete_exercise")],
            states={
                "selected_delete": [
                    CallbackQueryHandler(confirm_delete, pattern=("^\d")),
                    CallbackQueryHandler(delete_exercise_query, pattern="^next_page")

                ],
                "confirm_delete": [CallbackQueryHandler(process_delete, pattern="\d+"),
                                   CallbackQueryHandler(delete_exercise_query, pattern="back")],
            },
            fallbacks=[CallbackQueryHandler(delete_exercise_query, pattern="delete_exercise")],
            per_message=False
        )
    )

    # Admin commands
    dispatcher.add_handler(CommandHandler("get_reminder_time", get_reminder_time))
    dispatcher.add_handler(CommandHandler("get_group_id", get_group_id))
    dispatcher.add_handler(CommandHandler("change_reminder_time", change_reminder_time))
    dispatcher.add_handler(CommandHandler("change_group_id", change_group_id))
    dispatcher.add_handler(CommandHandler("get_one", get_one))
    dispatcher.add_handler(CommandHandler("drop", drop))
    dispatcher.add_handler(CommandHandler("execute", execute))
    dispatcher.add_handler(CommandHandler("set", set_query))

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
