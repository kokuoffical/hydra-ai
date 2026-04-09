import requests, os
from flask import Flask, request, jsonify, session, render_template_string
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
from bs4 import BeautifulSoup

app = Flask(__name__)

# CONFIG
app.secret_key = "hydra_render"
app.config["SESSION_TYPE"] = "filesystem"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"

Session(app)
db = SQLAlchemy(app)

# DB
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))

with app.app_context():
    db.create_all()

# SCRAPER
def get_repos(username):
    url = f"https://github.com/{username}?tab=repositories"
    res = requests.get(url)

    if res.status_code != 200:
        return None

    soup = BeautifulSoup(res.text, "html.parser")
    repo_tags = soup.select("li[itemprop='owns']")

    repos = []
    for i, repo in enumerate(repo_tags):
        name_tag = repo.find("a", itemprop="name codeRepository")
        if not name_tag:
            continue

        repos.append({
            "id": i+1,
            "name": name_tag.text.strip()
        })

    return repos

# DOWNLOAD
def download_repo_zip(username, repo):
    for branch in ["main", "master"]:
        url = f"https://github.com/{username}/{repo}/archive/refs/heads/{branch}.zip"
        r = requests.get(url)
        if r.status_code == 200:
            with open(f"/tmp/{repo}.zip", "wb") as f:
                f.write(r.content)
            return True
    return False

# UI (LIGHTWEIGHT FOR RENDER)
HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Hydra AI</title>
<style>
body {background:black;color:#00ffcc;font-family:monospace;text-align:center;}
input,button{margin:5px;padding:8px;background:black;color:#00ffcc;border:1px solid #00ffcc;}
.repo{border-bottom:1px solid #00ffcc;padding:4px;}
</style>
</head>

<body>

<h1>🐍 Hydra AI</h1>

{% if not session.get("user") %}

<input id="lu" placeholder="username">
<input id="lp" type="password">
<button onclick="login()">Login</button>

<input id="ru" placeholder="username">
<input id="rp" type="password">
<button onclick="register()">Register</button>

{% else %}

<p>Welcome {{session.get("user")}}</p>
<button onclick="logout()">Logout</button>

<input id="username" placeholder="GitHub username">
<button onclick="analyze()">Analyze</button>

<div id="out"></div>

{% endif %}

<script>
async function login(){
    await fetch("/login",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({u:lu.value,p:lp.value})});
    location.reload();
}

async function register(){
    await fetch("/register",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({u:ru.value,p:rp.value})});
    alert("Registered");
}

async function logout(){
    await fetch("/logout");
    location.reload();
}

async function analyze(){
    let res = await fetch("/analyze",{method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({username:username.value})});

    let data = await res.json();

    if(data.error){
        out.innerHTML=data.error;
        return;
    }

    let html="";
    data.repos.forEach(r=>{
        html+=`<div class="repo">[${r.id}] ${r.name}</div>`;
    });

    out.innerHTML=html+`
    <input id="repo_num">
    <button onclick="download()">Download</button>`;
}

async function download(){
    let res = await fetch("/download_repo",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({num:repo_num.value})
    });

    let data = await res.json();
    alert(data.msg);
}
</script>

</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML)

# AUTH
@app.route('/register', methods=['POST'])
def register():
    u=request.json['u']
    p=generate_password_hash(request.json['p'])

    if User.query.filter_by(username=u).first():
        return "exists"

    db.session.add(User(username=u,password=p))
    db.session.commit()
    return "ok"

@app.route('/login', methods=['POST'])
def login():
    u=request.json['u']
    p=request.json['p']

    user=User.query.filter_by(username=u).first()
    if user and check_password_hash(user.password,p):
        session["user"]=u

    return "ok"

@app.route('/logout')
def logout():
    session.clear()
    return "ok"

@app.route('/analyze', methods=['POST'])
def analyze():
    username=request.json['username']
    repos=get_repos(username)

    if not repos:
        return jsonify({"error":"Invalid username"})

    session["repos"]=repos
    session["username"]=username

    return jsonify({"repos":repos})

@app.route('/download_repo', methods=['POST'])
def download_repo():
    num=int(request.json['num'])
    repos=session.get("repos")
    username=session.get("username")

    repo=repos[num-1]["name"]

    if download_repo_zip(username, repo):
        return jsonify({"msg":f"{repo} downloaded!"})
    else:
        return jsonify({"msg":"Download failed"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)