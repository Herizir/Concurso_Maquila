from flask import Flask, render_template

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
    return render_template("inventario.html")

@app.route("/produccion")
def produccion():
    return render_template("produccion.html")
    

if __name__ == "__main__":
    app.run(debug=True)