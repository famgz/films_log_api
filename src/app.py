from flask import Flask, render_template, request, jsonify, abort
from functools import wraps
from pathlib import Path
from werkzeug.exceptions import HTTPException
import mysql
from mysql.connector import connect

source_dir = Path(__file__).resolve().parent

app = Flask(__name__)

HOST = "localhost"
USER = "root"
PASSWORD = "admin"
DATABASE = "films_log"


def get_db_connection():
    return connect(
        host=HOST,
        user=USER,
        password=PASSWORD,
        database=DATABASE,
    )


def run_sql_script(script_path):
    script_path = Path(source_dir, "database", script_path)
    with open(script_path, "r") as file:
        sql_commands = file.read().split(";")

    conn = connect(
        host=HOST,
        user=USER,
        password=PASSWORD,
    )

    cursor = conn.cursor()
    for command in sql_commands:
        if command.strip():
            cursor.execute(command)

    conn.commit()
    cursor.close()
    conn.close()


def is_database_empty():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM film")
    count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return count == 0


def init_db():
    # Criar database caso não exista
    try:
        run_sql_script("setup.sql")
        print("Database inicializado")
    except Exception as e:
        print(str(e))

    # Preencher table film caso esteja vazio
    if is_database_empty():
        try:
            run_sql_script("seed.sql")
            print("Filmes adicionados com sucesso")
        except Exception as e:
            print(str(e))


def handle_db_errors(func):
    @wraps(func)
    def inner_func(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except HTTPException as http_err:
            return jsonify({"error": http_err.description}), http_err.code
        except mysql.connector.Error as db_err:
            return jsonify({"error": str(db_err)}), 400
        except Exception as e:
            print(e.with_traceback)
            return jsonify({"error": str(e)}), 500

    return inner_func


def run_query(query):
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query)
        conn.commit()


def fetch_one_from_query(query):
    with get_db_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(query)
            return cursor.fetchone()


def find_user_by_username_or_email(username, email):
    return fetch_one_from_query(
        f"SELECT * FROM user WHERE username = '{username}' OR email = {email}"
    )


def get_user_id_by_username(username):
    user = fetch_one_from_query(f"SELECT * FROM user WHERE username = '{username}'")
    if not user:
        abort(404, "Usuário não encontrado")
    return user["id"]


def get_film_by_id(film_id):
    film = fetch_one_from_query(f"SELECT * FROM film WHERE id = '{film_id}'")
    if not film:
        abort(404, "Filme não encontrado")
    return film


""" Routes """


# Documentations
@app.route("/docs/en")
def red_docs_en():
    return render_template("docs-en.html")


@app.route("/docs/pt")
def red_docs_pt():
    return render_template("docs-pt.html")


# User CRUD
@app.route("/user", methods=["POST"])
@handle_db_errors
def create_user():
    data = request.form
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    if not (username and email and password):
        abort(400, "Os campos são obrigatórios")

    user = find_user_by_username_or_email(username, email)

    if user:
        abort(409, "Usuário já cadastrado com estes dados.")

    run_query(
        f"INSERT INTO user (username, email, password) VALUES ('{username}', '{email}', '{password}')"
    )

    return jsonify({"message": "User criado com sucesso"}), 201


@app.route("/user/<int:id>", methods=["GET"])
@handle_db_errors
def get_user(id):
    user = fetch_one_from_query(f"SELECT * FROM user WHERE id = {id}")

    if user:
        return jsonify(user)
    return jsonify({"message": "User não encontrado"}), 404


@app.route("/user/<int:id>", methods=["PUT"])
@handle_db_errors
def update_user(id):
    data = request.form
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    if not (username and email and password):
        abort(400, "Os campos são obrigatórios")

    user = find_user_by_username_or_email(username, email)

    if not user:
        abort(404, "Usuário não encontrado")

    run_query(
        f"UPDATE user SET username = '{username}', email = '{email}', password = '{password}' WHERE id = {id}"
    )

    return jsonify({"message": "User atualizado com sucesso"})


@app.route("/user/<int:id>", methods=["DELETE"])
@handle_db_errors
def delete_user(id):
    run_query(f"DELETE FROM user WHERE id = {id}")

    return jsonify({"message": "User excluído com sucesso"})


# Film CRUD
@app.route("/film", methods=["POST"])
@handle_db_errors
def create_film():
    data = request.form
    title = data.get("title")
    year = data.get("year")
    director = data.get("director")
    duration = data.get("duration")

    run_query(
        f"INSERT INTO film (title, year, director, duration) VALUES ('{title}', '{year}', '{director}', '{duration}')"
    )

    return jsonify({"message": "Filme adicionado com sucesso"}), 201


@app.route("/film/all", methods=["GET"])
@handle_db_errors
def get_all_films():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM film")
    film = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(film)


@app.route("/film/<int:id>", methods=["GET"])
@handle_db_errors
def get_film(id):
    film = get_film_by_id(id)
    if film:
        return jsonify(film)
    return jsonify({"message": "Filme não encontrado"}), 404


@app.route("/film/<int:id>", methods=["PUT"])
@handle_db_errors
def update_film(id):
    get_film_by_id(id)

    data = request.form
    title = data.get("title")
    year = data.get("year")
    director = data.get("director")
    duration = data.get("duration")

    run_query(
        f"UPDATE film SET title = '{title}', year = '{year}', director = '{director}', duration = '{duration}' WHERE id = {id}"
    )

    return jsonify({"message": "Filme atualizado com sucesso"})


@app.route("/film/<int:id>", methods=["DELETE"])
@handle_db_errors
def delete_film(id):
    run_query(f"DELETE FROM film WHERE id = {id}")

    return jsonify({"message": "Filme excluído com sucesso"})


# Review CRUD
@app.route("/user/<username>/film/<int:film_id>/review", methods=["POST"])
@handle_db_errors
def create_review(username, film_id):
    user_id = get_user_id_by_username(username)
    get_film_by_id(film_id)

    data = request.form
    review = data.get("review")

    if not review:
        abort(400, "Review não pode ser vazio.")

    existing_review = get_review(user_id, film_id)

    if existing_review:
        abort(409, "Review já existe para este usuário e filme")

    run_query(
        f"INSERT INTO review (user_id, film_id, review) VALUES ('{user_id}', '{film_id}', '{review}')"
    )

    return jsonify({"message": "Review adicionado com sucesso"}), 201


@app.route("/user/<username>/film/<int:film_id>/review", methods=["GET"])
@handle_db_errors
def get_review(username, film_id):
    user_id = get_user_id_by_username(username)["id"]
    get_film_by_id(film_id)

    review = fetch_one_from_query(
        f"SELECT * FROM review WHERE user_id = {user_id} AND film_id = {film_id}"
    )

    if review:
        return jsonify(review)
    return jsonify({"message": "Review não encontrado"}), 404


@app.route("/user/<username>/film/<int:film_id>/review", methods=["PUT"])
@handle_db_errors
def update_review(username, film_id):
    user_id = get_user_id_by_username(username)
    get_film_by_id(film_id)

    data = request.form
    review = data.get("review")

    if not review:
        abort(400, "Review não pode ser vazio.")

    existing_review = get_review(user_id, film_id)

    if not existing_review:
        abort(404, "Não foi encontrada Review para este usuário e filme")

    run_query(
        f"UPDATE review SET user_id = {user_id}, film_id = {film_id}, review = '{review}' WHERE id = {id}"
    )

    return jsonify({"message": "Review atualizado com sucesso"})


@app.route("/user/<username>/film/<int:film_id>/review", methods=["DELETE"])
@handle_db_errors
def delete_review(username, film_id):
    user_id = get_user_id_by_username(username)["id"]
    get_film_by_id(film_id)

    existing_review = get_review(user_id, film_id)

    if not existing_review:
        abort(404, "Não foi encontrada Review para este usuário e filme")

    run_query(f"DELETE FROM review WHERE user_id = {user_id} AND film_id = {film_id}")

    return jsonify({"message": "Review excluído com sucesso"})


# Rating CRUD
@app.route("/user/<username>/film/<int:film_id>/rating", methods=["POST"])
@handle_db_errors
def create_rating(username, film_id):
    user_id = get_user_id_by_username(username)
    get_film_by_id(film_id)

    data = request.form
    rating = data.get("rating")

    if not rating:
        abort(400, "Rating não pode ser vazio.")

    existing_rating = get_rating(user_id, film_id)

    if existing_rating:
        abort(409, "Rating já existe para este usuário e filme")

    run_query(
        f"INSERT INTO rating (user_id, film_id, rating) VALUES ('{user_id}', '{film_id}', '{rating}')"
    )

    return jsonify({"message": "Rating adicionado com sucesso"}), 201


@app.route("/user/<username>/film/<int:film_id>/rating", methods=["GET"])
@handle_db_errors
def get_rating(username, film_id):
    user_id = get_user_id_by_username(username)["id"]
    get_film_by_id(film_id)

    rating = fetch_one_from_query(
        f"SELECT * FROM rating WHERE user_id = {user_id} AND film_id = {film_id}"
    )

    if rating:
        return jsonify(rating)
    return jsonify({"message": "Rating não encontrado"}), 404


@app.route("/user/<username>/film/<int:film_id>/rating", methods=["PUT"])
@handle_db_errors
def update_rating(username, film_id):
    user_id = get_user_id_by_username(username)
    get_film_by_id(film_id)

    data = request.form
    rating = data.get("rating")

    if not rating:
        abort(400, "Rating não pode ser vazio.")

    existing_rating = get_rating(user_id, film_id)

    if not existing_rating:
        abort(404, "Não foi encontrada Rating para este usuário e filme")

    run_query(
        f"UPDATE rating SET user_id = {user_id}, film_id = {film_id}, rating = '{rating}' WHERE id = {id}"
    )

    return jsonify({"message": "Rating atualizado com sucesso"})


@app.route("/user/<username>/film/<int:film_id>/rating", methods=["DELETE"])
@handle_db_errors
def delete_rating(username, film_id):
    user_id = get_user_id_by_username(username)["id"]
    get_film_by_id(film_id)

    run_query(f"DELETE FROM rating WHERE user_id = {user_id} AND film_id = {film_id}")

    return jsonify({"message": "Rating excluído com sucesso"})


# Favorite CRUD
@app.route("/user/<username>/film/<int:film_id>/favorite", methods=["POST"])
@handle_db_errors
def create_favorite(username, film_id):
    user_id = get_user_id_by_username(username)
    get_film_by_id(film_id)

    data = request.form
    favorite = data.get("favorite")

    if favorite is None:
        abort(400, "Favorite não pode ser vazio.")

    existing_favorite = get_favorite(user_id, film_id)

    if existing_favorite is not None:
        abort(409, "Favorite já existe para este usuário e filme")

    run_query(
        f"INSERT INTO favorite (user_id, film_id, favorite) VALUES ('{user_id}', '{film_id}', '{favorite}')"
    )

    return jsonify({"message": "Favorite adicionado com sucesso"}), 201


@app.route("/user/<username>/film/<int:film_id>/favorite", methods=["GET"])
@handle_db_errors
def get_favorite(username, film_id):
    user_id = get_user_id_by_username(username)["id"]
    get_film_by_id(film_id)

    favorite = fetch_one_from_query(
        f"SELECT * FROM favorite WHERE user_id = {user_id} AND film_id = {film_id}"
    )

    if favorite is not None:
        return jsonify(favorite)
    return (
        jsonify({"message": "Não foi encontrada Favorite para este usuário e filme"}),
        404,
    )


@app.route("/user/<username>/film/<int:film_id>/favorite", methods=["PUT"])
@handle_db_errors
def update_favorite(username, film_id):
    user_id = get_user_id_by_username(username)
    get_film_by_id(film_id)

    data = request.form
    favorite = data.get("favorite")

    if favorite is None:
        abort(400, "Favorite não pode ser vazio.")

    existing_favorite = get_favorite(user_id, film_id)

    if not existing_favorite:
        return (
            jsonify(
                {"message": "Não foi encontrada Favorite para este usuário e filme"}
            ),
            404,
        )

    run_query(
        f"UPDATE favorite SET user_id = {user_id}, film_id = {film_id}, favorite = '{favorite}' WHERE id = {id}"
    )

    return jsonify({"message": "Favorite atualizado com sucesso"})


@app.route("/user/<username>/film/<int:film_id>/favorite", methods=["DELETE"])
@handle_db_errors
def delete_favorite(username, film_id):
    user_id = get_user_id_by_username(username)["id"]
    get_film_by_id(film_id)

    existing_favorite = get_favorite(user_id, film_id)

    if existing_favorite is None:
        return (
            jsonify(
                {"message": "Não foi encontrada Favorite para este usuário e filme"}
            ),
            404,
        )

    run_query(f"DELETE FROM favorite WHERE user_id = {user_id} AND film_id = {film_id}")

    return jsonify({"message": "Favorite excluído com sucesso"})


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8081, debug=True)
