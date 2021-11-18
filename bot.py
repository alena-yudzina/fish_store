import os
from functools import partial

import redis
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (CallbackQueryHandler, CommandHandler, Filters,
                          MessageHandler, Updater)

from store import (add_item_to_cart, create_customer, delete_item_from_cart,
                   download_file, get_cart_items, get_product, get_products,
                   get_token, make_cart_description)

_database = None

def start(update, context, access_token):
    products = get_products(access_token)

    keyboard = [
        [InlineKeyboardButton(product['name'], callback_data=product['id'])]
            for product in products
    ]
    keyboard.append([InlineKeyboardButton('Корзина', callback_data='cart')])

    context.user_data['keyboard'] = keyboard
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text('Please choose:', reply_markup=reply_markup)
    return 'HANDLE_MENU'


def handle_menu(update, context, access_token):
    keyboard = [
        [
            InlineKeyboardButton('1 кг', callback_data=1),
            InlineKeyboardButton('5 кг', callback_data=5),
            InlineKeyboardButton('10 кг', callback_data=10)
        ],
        [InlineKeyboardButton('Корзина', callback_data='cart')],
        [InlineKeyboardButton('Назад', callback_data='back')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    query = update.callback_query
    product_id = query.data
    context.user_data['product_id'] = product_id

    product = get_product(access_token, product_id)

    name = product['name']
    price = product['meta']['display_price']['with_tax']['formatted']
    description = product['description']
    img_id = product['relationships']['main_image']['data']['id']
    img_url = download_file(access_token, img_id)
    product_description = '{0}\n\n{1} per kg\n\n{2}'.format(
        name, price, description
    )

    context.bot.send_photo(
        chat_id=query.message.chat_id,
        photo=img_url,
        caption=product_description,
        reply_markup=reply_markup
    )
    context.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=update.callback_query.message.message_id
    )
    return 'HANDLE_DESCRIPTION'


def handle_description(update, context, access_token):
    keyboard = context.user_data['keyboard']
    reply_markup = InlineKeyboardMarkup(keyboard)

    query = update.callback_query
    user_choice = query.data
    cart_id = update.effective_chat.id
    product_id = context.user_data['product_id']

    if user_choice == 'back':
        query.message.reply_text(
            text='Please choose:',
            reply_markup=reply_markup
        )
        return 'HANDLE_MENU'
    elif user_choice == 'cart':
        cart = get_cart_items(access_token, cart_id)
        text = make_cart_description(cart)
        context.bot.send_message(query.message.chat_id, text)
        return 'HANDLE_DESCRIPTION'
    elif user_choice.isdigit():
        quantity = int(user_choice)
        add_item_to_cart(access_token, product_id, cart_id, quantity)
        return 'HANDLE_DESCRIPTION'


def show_cart(update, context, access_token):
    cart_id = update.effective_chat.id
    cart = get_cart_items(access_token, cart_id)
    text = make_cart_description(cart)
    products = cart['data']

    keyboard = [
        [InlineKeyboardButton('Убрать из корзины {}'.format(product['name']), callback_data=product['id'])]
            for product in products
    ]
    keyboard.append(
        [InlineKeyboardButton('В меню', callback_data='menu')]
    )
    keyboard.append(
        [InlineKeyboardButton('Оплатить', callback_data='pay')]
    )

    reply_markup = InlineKeyboardMarkup(keyboard)

    update.callback_query.message.reply_text(text=text, reply_markup=reply_markup)
    return 'HANDLE_CART'


def handle_cart(update, context, access_token):
    query = update.callback_query
    user_choice = query.data

    if user_choice == 'menu':
        keyboard = context.user_data['keyboard']
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.message.reply_text(
            text='Please choose:',
            reply_markup=reply_markup
        )
        return 'HANDLE_MENU'
    elif user_choice == 'pay':
        query.message.reply_text(
            text='Пожалуйста, пришлите ваш email.'
        )
        return 'WAITING_EMAIL'
    else:
        delete_item_from_cart(
            access_token,
            cart_id=update.effective_chat.id,
            product_id=user_choice
        )
        return 'HANDLE_CART'


def waiting_email(update, context, access_token):
    email = update.message.text
    create_customer(access_token, email)
    update.message.reply_text(
        text=f'Ваш email: {email}'
    )
    return 'SHOW_CART'


def handle_users_reply(update, context, store_token):

    db = get_database_connection()
    access_token = get_token(store_token)

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
    elif user_reply == 'cart':
        user_state = 'SHOW_CART'
    else:
        user_state = db.get(chat_id).decode('utf-8')
    states_functions = {
        'START': partial(start, access_token=access_token),
        'HANDLE_MENU': partial(handle_menu, access_token=access_token),
        'HANDLE_DESCRIPTION': partial(handle_description, access_token=access_token),
        'SHOW_CART': partial(show_cart, access_token=access_token),
        'HANDLE_CART': partial(handle_cart, access_token=access_token),
        'WAITING_EMAIL': partial(waiting_email, access_token=access_token),
    }
    state_handler = states_functions[user_state]
    try:
        next_state = state_handler(update, context)
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
    store_token = os.environ['CLIENT_ID']
    tg_token = os.environ['TELEGRAM_TOKEN']
    updater = Updater(tg_token)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CallbackQueryHandler(partial(handle_users_reply, store_token=store_token)))
    dispatcher.add_handler(MessageHandler(Filters.text, partial(handle_users_reply, store_token=store_token)))
    dispatcher.add_handler(CommandHandler('start', partial(handle_users_reply, store_token=store_token)))
    updater.start_polling()
