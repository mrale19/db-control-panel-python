from flask import Flask, request, jsonify, send_from_directory, redirect, url_for, session, render_template
import pyodbc
import jwt
secret_key = 'AndrewFuckingGurskiy'

app = Flask(__name__, static_folder='static')
app.secret_key = secret_key


# Строка подключения к базе данных SQL Server
conn_str = f'DRIVER={{SQL Server}};SERVER={{localhost}};DATABASE={{eda}};TrustServerCertificate=yes;'
conn = pyodbc.connect(conn_str)


def generate_token(**kwargs):
    client_id = kwargs.get('client_id')
    phone = kwargs.get('phone')
    full_name = kwargs.get('full_name')
    birthday = kwargs.get('birthday')
    role = kwargs.get('role')

    payload = {'client_id': client_id, 'phone': phone, 'full_name': full_name, 'birthday': birthday, 'role': role, 'isUseful': True}
    jwt_token = jwt.encode(payload, secret_key, algorithm='HS256')
    return jwt_token


@app.route('/login', methods=['POST'])
def login_form():
    try:
        data = request.json
        print(data)
        phone = data['phone']
        password = data['password']
        #operation = data['operation']
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM CLIENTS WHERE phone = ? and password = ?', phone, password)
        rows = cursor.fetchone()
        cursor.close()
        print(rows)
        if rows:
            client_id, phone, full_name, password, birthday, role = rows

            jwt_token = generate_token(client_id=client_id, phone=phone, full_name=full_name, birthday=birthday, role=role)
            session['token'] = jwt_token
            return redirect(url_for('user_account', code=302))
        #elif (rows == None and operation == False)
           # cursor = conn.cursor()
            #cursor.execute()
        else:
            return jsonify({'auth': 'failed'})
    except pyodbc.Error as e:
        print('Error connecting to MS SQL Server:', e)
        return jsonify({'error': 'Error connecting to the database'})


@app.route('/')
def start_route():
    if 'token' not in session:
        # Если пользователь не авторизован, перенаправьте его на страницу аутентификации
        return send_from_directory('static', 'auth.html')
    else:
        token = session.get('token')  # Получение токена из параметров запроса
        decoded_token = jwt.decode(token, secret_key, algorithms=['HS256'])

        # Если пользователь авторизован, отобразите содержимое личного кабинета
        return render_template('user_account.html', isAdmin=decoded_token['role'] == 'admin')


@app.route('/user_account', methods=['GET'])
def user_account():
    token = session.get('token')  # Получение токена из параметров запроса
    if token:
        decoded_token = jwt.decode(token, secret_key, algorithms=['HS256'])
        if decoded_token['isUseful']:  # login = decoded_token['login']
            return render_template('user_account.html', isAdmin=decoded_token['role'] == 'admin')
        else:
            return redirect('/'), 302
    else:
        return redirect('/'), 302


@app.route('/logout', methods=['GET'])
def logout():
    session.clear()
    return redirect('/'), 302


@app.route('/user_data', methods=['GET'])
def user_info():
    token = session['token']
    decoded_token = jwt.decode(token, secret_key, algorithms=['HS256'])
    phone = decoded_token['phone']
    full_name = decoded_token['full_name']
    birthday = decoded_token['birthday']
    role = decoded_token['role']

    return jsonify({'full_name': full_name, 'phone': phone, 'birthday': birthday, 'role': role})

@app.route('/before-current-table', methods=['POST'])
def your_endpoint():
    button_id = request.json.get('buttonId')
    # Здесь можете выполнить какую-то обработку, если необходимо
    return redirect(url_for('current_table', buttonId=button_id))


@app.route('/reports', methods=['GET'])
def reports():
    try:
        token = session['token']
        decoded_token = jwt.decode(token, secret_key, algorithms=['HS256'])
        isAdmin = decoded_token['role'] == 'admin'

        return render_template('reports.html', isAdmin=isAdmin)
    except Exception as e:
        print(e)
        print('запрос получен с ошибкой')
        error_message = f'Ошибка при выполнении запроса к базе данных: {str(e)}'
        return jsonify({'error': error_message}), 500


@app.route('/report-restaurant', methods=['GET'])
def report_restaurant():
    try:
        start = request.args.get('start')
        end = request.args.get('end')

        where = 'WHERE date_time '

        if start and end:
            where += f"BETWEEN CONVERT(datetime, '{start}', 120) AND CONVERT(datetime, '{end}', 120)"
        elif start:
            where += f">= CONVERT(datetime, '{start}', 120)"
        elif end:
            where += f"<= CONVERT(datetime, '{end}', 120)"
        else:
            where = ''

        query = (f'SELECT restaurant_id, r.name, sum(total_cost) as sum FROM orders o'
                 f' join restaurants r on r.id = o.restaurant_id '
                 f'{where}'
                 f' group by restaurant_id, r.name')

        print("query", query)

        cursor = conn.cursor()
        headers = ['restaurant_id', 'name', 'sum']

        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()

        data = []
        for row in rows:
            row_dict = {}
            for idx, value in enumerate(row):
                row_dict[headers[idx]] = value
            data.append(row_dict)

        return render_template('report-restaurant.html', headers=headers, data=data)
    except Exception as e:
        print(e)
        print('запрос получен с ошибкой')
        error_message = f'Ошибка при выполнении запроса к базе данных: {str(e)}'
        return jsonify({'error': error_message}), 500



@app.route('/report-client', methods=['GET'])
def report_client():
    try:
        start = request.args.get('start')
        end = request.args.get('end')
        client_id = request.args.get('clientId')

        where = ''

        if start and end:
            where += f"WHERE date_time BETWEEN CONVERT(datetime, '{start}', 120) AND CONVERT(datetime, '{end}', 120)"
        elif start:
            where += f"WHERE date_time >= CONVERT(datetime, '{start}', 120)"
        elif end:
            where += f"WHERE date_time <= CONVERT(datetime, '{end}', 120)"
        else:
            where = ''

        if client_id:
            if where:
                where += ' AND '
            else:
                where = 'WHERE '

            where += f'c.id = {client_id}'

        query = (f'select c.id, c.full_name, r.name, sum(o.total_cost) as sum from orders o '
                 f'join clients c on c.id = o.client_id '
                 f'join restaurants r on r.id = o.restaurant_id '
                 f'{where} '
                 f'group by c.id, c.full_name, r.name '
                 f'order by c.id')

        print("query", query)

        cursor = conn.cursor()
        headers = ['client_id', 'client_name', 'restaurant_name', 'sum']

        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()

        data = []
        for row in rows:
            row_dict = {}
            for idx, value in enumerate(row):
                row_dict[headers[idx]] = value
            data.append(row_dict)

        return render_template('report_client.html', headers=headers, data=data)
    except Exception as e:
        print(e)
        print('запрос получен с ошибкой')
        error_message = f'Ошибка при выполнении запроса к базе данных: {str(e)}'
        return jsonify({'error': error_message}), 500



@app.route('/current-table', methods=['GET'])
def current_table():
    print('запрос получен')
    token = session['token']
    decoded_token = jwt.decode(token, secret_key, algorithms=['HS256'])
    isAdmin = decoded_token['role'] == 'admin'
    user_tables = ('orders', 'reviews', 'addresses', 'favorite_restaurants', 'favorite_products')


    try:
        cursor = conn.cursor()

        button_id = request.args.get('buttonId')

        if not button_id:
            return render_template('tables.html', isAdmin=isAdmin)

        user_filter = f" WHERE client_id = {decoded_token['client_id']}" if not isAdmin and button_id in user_tables else ""

        search = request.args.get('search')
        column_search = request.args.get('column')
        operation = request.args.get('operation')
        order_id = request.args.get('orderId')

        if search and column_search:
            converted_search = search

            if 'date' in column_search or 'day' in column_search:
                converted_search = f"CONVERT(DATETIME, '{search}', 120)"
            else:
                converted_search = f"'{search}'"

            user_filter += f" {'AND' if 'WHERE' in user_filter else 'WHERE'} {column_search} {operation} {converted_search}"

        print(user_filter)
        cursor.execute(f'SELECT * FROM {button_id}{user_filter}')
        rows = cursor.fetchall()
        # Получаем описание столбцов
        cursor.execute(f'SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = ?', button_id)
        columns_info = cursor.fetchall()

        linked_headers = []
        linked_data = []

        if button_id == 'orders' and order_id:
            cursor.execute(f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'products'")
            products_columns = cursor.fetchall()

            linked_headers = [column[0] for column in products_columns]

            products_columns_query = ", ".join(map(lambda h: f'p.{h}', linked_headers))

            cursor.execute(f'select {products_columns_query} from products p join product_in_order pio on pio.product_id = p.id where pio.order_id = {order_id}')
            products_rows = cursor.fetchall()

            for row in products_rows:
                row_dict = {}
                for idx, value in enumerate(row):
                    row_dict[linked_headers[idx]] = value
                linked_data.append(row_dict)



        cursor.close()
        print(columns_info)
        # Формируем список заголовков таблицы
        headers = [column[0] for column in columns_info]
        # Формируем данные для каждой строки таблицы
        data = []
        for row in rows:
            row_dict = {}
            for idx, value in enumerate(row):
                row_dict[headers[idx]] = value
            data.append(row_dict)
        print(headers, data)
        return render_template('currentTable.html', headers=headers, data=data, isAdmin=isAdmin, table=button_id, linkedHeaders=linked_headers, linkedData=linked_data, orderId=order_id)
    except Exception as e:
        print(e)
        print('запрос получен с ошибкой')
        error_message = f'Ошибка при выполнении запроса к базе данных: {str(e)}'
        return jsonify({'error': error_message}), 500


@app.route('/delete-data', methods=['POST'])
def delete_data():
    try:
        # Получение данных из тела запроса
        print(request.data)
        id = request.json.get('id')
        table = request.json.get('table')

        if not id:
            return jsonify({'query-failed': 'ID not provided'}), 400

        if not table:
            return jsonify({'query-failed': 'TABLE not provided'}), 400

        cursor = conn.cursor()
        # Выполнение SQL-запроса на удаление
        cursor.execute(f"DELETE FROM {table} WHERE id = ?", (id,))
        conn.commit()

        # Закрытие соединения с базой данных
        cursor.close()

        return jsonify({'success': True, 'deleted_id': id})
    except Exception as e:
        print("Ошибка удаления данных:", str(e))
        return jsonify({'query-failed': str(e)})  # Возвращаем ошибку сервера в случае исключения
    

@app.route('/update-data', methods=['POST'])
def update_data():
    try:
        # Получение данных из тела запроса
        table = request.json.get('table')
        values = request.json.get('values')
        id = request.json.get('id')

        if not table or not values or not id:
            return jsonify({'query-failed': 'Table name or values not provided'}), 400

        if not isinstance(values, dict):
            return jsonify({'query-failed': 'Values should be a dictionary'}), 400

        set_clause = ', '.join([f"{key} = ?" for key in values.keys()])
        values_list = list(values.values())
        values_list.append(id)

        # Создание SQL-запроса
        query = f"UPDATE {table} SET {set_clause} where id = ?"

        # Выполнение SQL-запроса на добавление
        cursor = conn.cursor()
        cursor.execute(query, values_list)
        conn.commit()

        # Закрытие курсора
        cursor.close()

        return jsonify({'success': True, 'inserted': values})
    except Exception as e:
        print("Ошибка обновления даных:", str(e))
        return jsonify({'query-failed': str(e)})  # Возвращаем ошибку сервера в случае исключения


@app.route('/new-data', methods=['POST'])
def new_data():
    try:
        # Получение данных из тела запроса
        table = request.json.get('table')
        values = request.json.get('values')

        if not table or not values:
            return jsonify({'query-failed': 'Table name or values not provided'}), 400

        if not isinstance(values, dict):
            return jsonify({'query-failed': 'Values should be a dictionary'}), 400

        columns = ', '.join(values.keys())
        placeholders = ', '.join(['?' for _ in values])
        values_list = list(values.values())

        # Создание SQL-запроса
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"

        # Выполнение SQL-запроса на добавление
        cursor = conn.cursor()
        cursor.execute(query, values_list)
        conn.commit()

        # Закрытие курсора
        cursor.close()

        return jsonify({'success': True, 'inserted': values})
    except Exception as e:
        print("Ошибка добавления даных:", str(e))
        return jsonify({'query-failed': str(e)})  # Возвращаем ошибку сервера в случае исключения


if __name__ == '__main__':
    app.run(debug=True)

