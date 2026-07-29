from flask import Flask, jsonify, render_template, request

import models

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
    return render_template("inventario.html", **models.obtener_inventario())


@app.route("/inventario/guardar", methods=["POST"])
def guardar_inventario():
    datos = request.get_json(silent=True) or {}

    if not isinstance(datos.get("documento"), dict):
        return jsonify(error="Falta el encabezado del documento."), 400
    if not isinstance(datos.get("materiales"), list):
        return jsonify(error="Se esperaba la lista de materiales."), 400
    if not isinstance(datos.get("referencias"), list):
        return jsonify(error="Se esperaba la lista de documentos de referencia."), 400

    return jsonify(**models.guardar_inventario(datos))

@app.route("/produccion")
def produccion():
    return render_template("produccion.html")
    

if __name__ == "__main__":
    app.run(debug=True)