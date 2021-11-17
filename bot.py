import json
import logging
import os

import redis
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (CallbackQueryHandler, CommandHandler, Filters,
                          MessageHandler, Updater)

from store import (add_item_to_cart, download_file, get_cart_items,
                   get_product, get_products, make_cart_description)

_database = None

def start(bot, update):
    products = get_products(store_token)

    keyboard = [
        [InlineKeyboardButton(product['name'], callback_data=product['id'])]
            for product in products
    ]
    keyboard.append([InlineKeyboardButton('Корзина', callback_data='cart')])

    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text('Please choose:', reply_markup=reply_markup)
    return 'HANDLE_MENU'


def handle_menu(bot, update):
    query = update.callback_query
    cart_id = query.message.chat_id

    if query.data == 'cart':
        cart = get_cart_items(store_token, cart_id)
        text = make_cart_description(cart)
        bot.send_message(query.message.chat_id, text)
        return 'HANDLE_MENU'

    product_id = query.data
    product = get_product(store_token, product_id)

    name = product['name']
    price = product['meta']['display_price']['with_tax']['formatted']
    description = product['description']
    img_id = product['relationships']['main_image']['data']['id']
    img_url = download_file(store_token, img_id)
    product_description = '{0}\n\n{1} per kg\n\n{2}'.format(
        name, price, description
    )
    
    keyboard = [
        [
            InlineKeyboardButton('1 кг', callback_data=f'1_{product_id}'),
            InlineKeyboardButton('5 кг', callback_data=f'5_{product_id}'),
            InlineKeyboardButton('10 кг', callback_data=f'10_{product_id}')
        ],
        [InlineKeyboardButton('Корзина', callback_data='cart')],
        [InlineKeyboardButton('Назад', callback_data='back')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    bot.send_photo(
        chat_id=query.message.chat_id,
        photo=img_url,
        caption=product_description,
        reply_markup=reply_markup
    )
    return 'HANDLE_DESCRIPTION'


def handle_description(bot, update):
    query = update.callback_query
    answer = query.data
    cart_id = query.message.chat_id
    print(type(answer))

    if answer == 'back':
        return 'HANDLE_MENU'
    elif answer == 'cart':
        cart = get_cart_items(store_token, cart_id)
        #print(json.dumps(cart, indent=2))
        text = make_cart_description(cart)
        bot.send_message(query.message.chat_id, text)
        return 'HANDLE_DESCRIPTION'
    elif answer.split('_', 2)[0] in (1, 5, 10):
        print(answer)
        quantity, product_id = answer.split('_', 2)
        add_item_to_cart(store_token, product_id, cart_id, quantity)
        return 'HANDLE_DESCRIPTION'


def echo(bot, update):
    users_reply = update.message.text
    update.message.reply_text(users_reply)
    return "ECHO"


def handle_users_reply(bot, update):
    """
    Функция, которая запускается при любом сообщении от пользователя и решает как его обработать.

    Эта функция запускается в ответ на эти действия пользователя:
        * Нажатие на inline-кнопку в боте
        * Отправка сообщения боту
        * Отправка команды боту
    Она получает стейт пользователя из базы данных и запускает соответствующую функцию-обработчик (хэндлер).
    Функция-обработчик возвращает следующее состояние, которое записывается в базу данных.
    Если пользователь только начал пользоваться ботом, Telegram форсит его написать "/start",
    поэтому по этой фразе выставляется стартовое состояние.
    Если пользователь захочет начать общение с ботом заново, он также может воспользоваться этой командой.
    """
    db = get_database_connection()
    if update.message:
        user_reply = update.message.text
        chat_id = update.message.chat_id
    elif update.callback_query:
        user_reply = update.callback_query.data
        chat_id = update.callback_query.message.chat_id
    else:
        return
    if user_reply == '/start':
        user_state = 'START'
    else:
        user_state = db.get(chat_id).decode('utf-8')
    states_functions = {
        'START': start,
        'ECHO': echo,
        'HANDLE_MENU': handle_menu,
        'HANDLE_DESCRIPTION': handle_description
    }
    state_handler = states_functions[user_state]
    # Если вы вдруг не заметите, что python-telegram-bot перехватывает ошибки.
    # Оставляю этот try...except, чтобы код не падал молча.
    # Этот фрагмент можно переписать.
    try:
        next_state = state_handler(bot, update)
        db.set(chat_id, next_state)
    except Exception as err:
        print(err)


def get_database_connection():

    global _database
    if _database is None:
        database_password = os.environ['DATABASE_PASSWORD']
        database_host = os.environ['DATABASE_HOST']
        database_port = os.environ['DATABASE_PORT']
        _database = redis.Redis(host=database_host, port=database_port, password=database_password)
    return _database


if __name__ == '__main__':
    load_dotenv()
    global store_token
    store_token = os.environ['CLIENT_ID']
    tg_token = os.environ['TELEGRAM_TOKEN']
    updater = Updater(tg_token)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CallbackQueryHandler(handle_users_reply))
    dispatcher.add_handler(MessageHandler(Filters.text, handle_users_reply))
    dispatcher.add_handler(CommandHandler('start', handle_users_reply))
    updater.start_polling()
