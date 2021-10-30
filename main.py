import os
# Import necessary libraries:
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler, \
    ConversationHandler
from db import Database
from functools import partial
db = Database()
db.create_tables()


def start(update: Update, context):
    """Sends a message with three inline buttons attached."""
    keyboard = [
        [InlineKeyboardButton("Track Exercise", callback_data='track_exercise')],
        [InlineKeyboardButton("Retrieve", callback_data='retrieve')],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text('Please choose:', reply_markup=reply_markup)



def help_command(update: Update, context):
    update.message.reply_text("shape is: ")


'''
def button(update: Update, context: CallbackContext) -> None:
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    query.answer()
    if query.data == "2":
      a = db.get_all()

    query.edit_message_text(text=a)
'''
def log_exercise(update, context, exercise=""):
    user = update.message.from_user.first_name
    tele_id = update.message.from_user.username
    score = update.message.text


    db.insert_entry(user, exercise, 3, 2)
    update.message.reply_text(f"Success! Recorded {score} reps for {user}.")
    return ConversationHandler.END

def ask_exercise(update, context, exercise=""):
    query = update.callback_query
    query.answer()

    if exercise == "PU":
        query.edit_message_text("Pull ups selected. Please enter how many pull ups you have done:")
        return "LOG_PU"
        # db.insert_entry(user, exercise, 3, 2)
        # print(user)
    elif exercise == "C":
        query.edit_message_text("Core selected. Please enter how many you have done:")
        return "LOG_C"
    elif exercise == "R":
        query.edit_message_text("Run selected. Please enter how far you have ran in km (e.g. 4.6):")
        return "LOG_R"




def get_one(update, context):
    query = update.callback_query
    query.answer()
    query.edit_message_text(db.get_all())


def choose_exercise(update, context):
    query = update.callback_query
    query.answer()

    keyboard = [
        [InlineKeyboardButton("Pull ups", callback_data='PU'),
         InlineKeyboardButton("Core", callback_data='C'),
         InlineKeyboardButton("Run", callback_data='R')],
        [InlineKeyboardButton("Back", callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(
        text="Choose exercise: ", reply_markup=reply_markup
    )

    return "selected_exercise"


def main() -> None:
    """Run the bot."""
    # Create the Updater and pass it your bot's token.
    updater = Updater(os.environ['TOKEN'])

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(
        ConversationHandler(
            entry_points=[CallbackQueryHandler(choose_exercise, pattern="track_exercise")],
            states={
                "selected_exercise": [
                    CallbackQueryHandler(partial(ask_exercise, exercise="PU"), pattern='PU'),
                    CallbackQueryHandler(partial(ask_exercise, exercise="C"), pattern='C'),
                    CallbackQueryHandler(partial(ask_exercise, exercise="R"), pattern='R'),
                ],
                "LOG_PU": [MessageHandler(Filters.text, partial(log_exercise, exercise="PU"))],
                "LOG_C": [MessageHandler(Filters.text, partial(log_exercise, exercise="C"))],
                "LOG_R": [MessageHandler(Filters.text, partial(log_exercise, exercise="R"))]
            },
            fallbacks=[CommandHandler('start', start)],
            per_message=False
        )
    )

    # Add ConversationHandler to dispatcher that will be used for handling updates
    dispatcher.add_handler(CommandHandler("add_entry", log_exercise))
    # updater.dispatcher.add_handler(CallbackQueryHandler(button))
    dispatcher.add_handler(CommandHandler("get_one", get_one))
    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()