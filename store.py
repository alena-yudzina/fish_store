import requests


def get_token(client_id):
    data = {
        'client_id': client_id,
        'grant_type': 'implicit'
    }

    response = requests.post('https://api.moltin.com/oauth/access_token', data=data)
    response.raise_for_status()
    return response.json()['access_token']


def get_products(client_id):
    
    access_token = get_token(client_id)
    
    headers = {
        'Authorization': access_token,
    }

    response = requests.get('https://api.moltin.com/v2/products', headers=headers)
    response.raise_for_status()
    catalog = response.json()
    products = catalog['data']
    return products


def get_product(client_id, product_id):
    access_token = get_token(client_id)

    headers = {
        'Authorization': access_token,
    }

    response = requests.get(
        'https://api.moltin.com/v2/products/{}'.format(product_id),
        headers=headers
    )
    response.raise_for_status()
    return response.json()['data']


def download_file(client_id, file_id):
    access_token = get_token(client_id)

    headers = {
        'Authorization': access_token,
    }

    response = requests.get(
        'https://api.moltin.com/v2/files/{}'.format(file_id),
        headers=headers
    )
    response.raise_for_status()
    file_description = response.json()
    file_url = file_description['data']['link']['href']

    file = requests.get(file_url)
    file.raise_for_status()

    return file_url


def create_customer(client_id, email):
    access_token = get_token(client_id)

    headers = {
        'Authorization': access_token,
        'Content-Type': 'application/json',
    }

    data = {
        "data": {
            "type": "customer",
            "name": "name",
            "email": email,
        }
    }

    response = requests.post('https://api.moltin.com/v2/customers', headers=headers, json=data)
    response.raise_for_status()
    response = response.json()
    return response['data']['id']


def get_customer(client_id, customer_id):
    access_token = get_token(client_id)

    headers = {
        'Authorization': access_token,
    }

    response = requests.get(
        'https://api.moltin.com/v2/customers/{}'.format(customer_id),
        headers=headers
    )
    response.raise_for_status()
    return response.json()


def add_item_to_cart(client_id, product_id, cart_id, quantity):
    access_token = get_token(client_id)
    
    headers = {
        'Authorization': access_token,
        'Content-Type': 'application/json',
    }

    data = {
        "data": {
            "id": product_id,
            "type": "cart_item",
            "quantity": quantity
        }
    }

    response = requests.post(
        'https://api.moltin.com/v2/carts/{}/items'.format(cart_id),
        headers=headers,
        json=data
    )
    response.raise_for_status()


def delete_item_from_cart(client_id, cart_id, product_id):
    access_token = get_token(client_id)

    headers = {
        'Authorization': access_token,
    }

    response = requests.delete(
        'https://api.moltin.com/v2/carts/{}/items/{}'.format(cart_id, product_id),
        headers=headers
    )
    response.raise_for_status()


def get_cart_items(client_id, cart_id):
    access_token = get_token(client_id)

    headers = {
        'Authorization': access_token,
    }

    response = requests.get(
        'https://api.moltin.com/v2/carts/{}/items'.format(cart_id),
        headers=headers
    )
    response.raise_for_status()
    return response.json()


def make_cart_description(cart):
    description = ''
    products = cart['data']
    
    for product in products:
        name = product['name']
        desc = product['description']
        price_per_kg = product['meta']['display_price']['with_tax']['unit']['formatted']
        quantity = product['quantity']
        total_price = product['meta']['display_price']['with_tax']['value']['formatted']
        description += f'{name}\n{desc}\n{price_per_kg} per kg\n{quantity}kg in cart for {total_price}\n\n'
    
    cart_price = cart['meta']['display_price']['with_tax']['formatted']
    
    description += f'Total: {cart_price}'
    return description
