from flask import Flask, jsonify, render_template, request

from models import guardar_materiales, obtener_materiales

app = Flask(__name__)

@app.route("/")
def login():
    return render_template("login.html")

@app.route("/maquila")
def base():
    return render_template("base.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/inventario")
def inventario():
    return render_template("inventario.html", materiales=obtener_materiales())


@app.route("/inventario/guardar", methods=["POST"])
def guardar_inventario():
    datos = request.get_json(silent=True) or {}
    materiales = datos.get("materiales")

    if not isinstance(materiales, list):
        return jsonify(error="Se esperaba una lista de materiales."), 400

    return jsonify(materiales=guardar_materiales(materiales))

@app.route("/produccion")
def produccion():
    return render_template("produccion.html")
    

if __name__ == "__main__":
    app.run(debug=True)