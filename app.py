#!/usr/bin/env python3
# app.py mejorado con soporte para JSON de contenidos

from flask import Flask, request, render_template, redirect, url_for, session, flash, jsonify, send_file, abort
from pymongo import MongoClient
from flask_cors import CORS
from datetime import datetime
from urllib.parse import quote_plus
import json
import os
import requests
import uuid
from dotenv import load_dotenv
from bson.objectid import ObjectId



# Cargar variables de entorno (.env)
load_dotenv()

app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'advpjsh')

# ==============================
# ⚙️ Configuración general
# ==============================
MONGO_USERNAME = os.getenv('MONGO_USERNAME')
MONGO_PASSWORD = os.getenv('MONGO_PASSWORD')
MONGO_URI = (
    f"mongodb+srv://{MONGO_USERNAME}:{MONGO_PASSWORD}"
    "@cluster0.rhzhszo.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
)

DB_NAME = "codeverse"
COLLECTION_NAME = "tutorials"
CONTENIDO_FILE = "contenido_tutoriales.json"
DOWNLOAD_FOLDER = "downloads"

# ==============================
# 🧠 Conexión a MongoDB Atlas
# ==============================
try:
    client = MongoClient(
        MONGO_URI,
        tls=True,                         # Conexión segura
        tlsAllowInvalidCertificates=True, # Evita error SSL en Render
        serverSelectionTimeoutMS=5000     # Timeout corto para evitar cuelgues
    )
    client.server_info()  # Verifica conexión
    db = client[DB_NAME]
    print("✅ Conectado a MongoDB Atlas correctamente.")
except Exception as e:
    db = None
    print(f"⚠️ No se pudo conectar a MongoDB Atlas: {e}")
# Crear carpeta de descargas
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Variable global para la colección
tutorials_collection = None

def conectar_mongodb():
    """Intenta conectar a MongoDB y devuelve la colección"""
    global tutorials_collection
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000)
        client.admin.command('ping')
        db = client[DB_NAME]
        tutorials_collection = db[COLLECTION_NAME]
        print("✅ Conectado a MongoDB Atlas")
        return tutorials_collection
    except Exception as e:
        print(f"❌ Error al conectar a MongoDB: {e}")
        tutorials_collection = None
        return None

# Conectar al iniciar la aplicación
conectar_mongodb()

# Funciones auxiliares para JSON
def cargar_contenidos():
    """Carga el archivo JSON de contenidos"""
    if os.path.exists(CONTENIDO_FILE):
        try:
            with open(CONTENIDO_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error cargando JSON: {e}")
            return {}
    return {}

def guardar_contenidos(contenidos):
    """Guarda los contenidos en el archivo JSON"""
    try:
        with open(CONTENIDO_FILE, 'w', encoding='utf-8') as f:
            json.dump(contenidos, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error guardando JSON: {e}")

def sincronizar_json():
    """Sincroniza MongoDB con el JSON automáticamente"""
    try:
        if not tutorials_collection:
            print("❌ Colección no disponible para sincronizar")
            return False
        
        contenidos = {}
        tutoriales = list(tutorials_collection.find({}))
        
        for tutorial in tutoriales:
            tutorial_id = str(tutorial['_id'])
            contenidos[tutorial_id] = {
                'title': tutorial.get('title'),
                'language': tutorial.get('language'),
                'level': tutorial.get('level'),
                'duration': tutorial.get('duration'),
                'description': tutorial.get('description'),
                'content': tutorial.get('content', '<p>Contenido no disponible</p>'),
                'lastUpdated': datetime.now().isoformat()
            }
        
        guardar_contenidos(contenidos)
        print("✅ JSON sincronizado con MongoDB")
        return True
    except Exception as e:
        print(f"❌ Error sincronizando JSON: {e}")
        return False

# ==================== RUTAS ====================

@app.route('/')
def inicio():
    """Ruta para la página de inicio"""
    return render_template('index.html')

@app.route('/tutoriales')
def tutoriales():
    """Ruta para la página de tutoriales"""
    try:
        global tutorials_collection
        if tutorials_collection is None:
            conectar_mongodb()
        
        if tutorials_collection is None:
            contenidos = cargar_contenidos()
            tutoriales_list = [
                {
                    '_id': tid,
                    'title': content.get('title', 'Sin título'),
                    'description': content.get('description', ''),
                    'level': content.get('level', 'principiante'),
                    'duration': content.get('duration', '0'),
                    'language': content.get('language', 'python')
                }
                for tid, content in contenidos.items()
            ]
        else:
            tutoriales_list = list(tutorials_collection.find({}, {"_id": 1, "title": 1, "description": 1, "level": 1, "duration": 1, "language": 1}))
            for tutorial in tutoriales_list:
                tutorial['_id'] = str(tutorial['_id'])
        
        return render_template('tutoriales.html', tutoriales=tutoriales_list)
    except Exception as e:
        print(f"Error en tutoriales: {e}")
        contenidos = cargar_contenidos()
        tutoriales_list = [
            {
                '_id': tid,
                'title': content.get('title', 'Sin título'),
                'description': content.get('description', ''),
                'level': content.get('level', 'principiante'),
                'duration': content.get('duration', '0'),
                'language': content.get('language', 'python')
            }
            for tid, content in contenidos.items()
        ]
        return render_template('tutoriales.html', tutoriales=tutoriales_list)

@app.route('/tutorial/<tutorial_id>')
def ver_tutorial(tutorial_id):
    """Ruta para ver un tutorial específico con contenido del JSON"""
    try:
        global tutorials_collection
        if tutorials_collection is None:
            conectar_mongodb()
        
        tutorial = None
        
        if tutorials_collection is not None:
            try:
                tutorial = tutorials_collection.find_one({"_id": ObjectId(tutorial_id)})
                if tutorial:
                    tutorial['_id'] = str(tutorial['_id'])
            except Exception as e:
                print(f"Error consultando MongoDB: {e}")
                tutorial = None
        
        if not tutorial:
            contenidos = cargar_contenidos()
            if tutorial_id in contenidos:
                tutorial = {
                    '_id': tutorial_id,
                    **contenidos[tutorial_id]
                }
            else:
                return "Tutorial no encontrado", 404
        
        if 'content' not in tutorial or not tutorial['content']:
            contenidos = cargar_contenidos()
            if tutorial_id in contenidos:
                tutorial['content'] = contenidos[tutorial_id].get('content', '<p>Contenido no disponible</p>')
            else:
                tutorial['content'] = '<p>Contenido no disponible</p>'
        
        return render_template('tutorial-detalle.html', tutorial=tutorial)
    except Exception as e:
        print(f"Error en ver_tutorial: {e}")
        return f"Error al cargar el tutorial: {str(e)}", 500

@app.route('/admin/editor')
def editor_admin():
    """Página para editar tutoriales y guardarlos en JSON"""
    try:
        global tutorials_collection
        if tutorials_collection is None:
            conectar_mongodb()
        
        tutoriales_list = []
        
        if tutorials_collection is not None:
            try:
                tutoriales_list = list(tutorials_collection.find({}, {"_id": 1, "title": 1, "language": 1, "level": 1}))
                for tutorial in tutoriales_list:
                    tutorial['_id'] = str(tutorial['_id'])
                print(f"✅ Cargados {len(tutoriales_list)} tutoriales de MongoDB")
            except Exception as e:
                print(f"Error consultando MongoDB: {e}")
                tutoriales_list = []
        
        if not tutoriales_list:
            print("📄 Cargando tutoriales desde JSON...")
            contenidos = cargar_contenidos()
            tutoriales_list = [
                {
                    '_id': tid,
                    'title': content.get('title', 'Sin título'),
                    'language': content.get('language', 'python'),
                    'level': content.get('level', 'principiante')
                }
                for tid, content in contenidos.items()
            ]
            print(f"✅ Cargados {len(tutoriales_list)} tutoriales de JSON")
        
        return render_template('admin-editor.html', tutoriales=tutoriales_list)
    except Exception as e:
        print(f"Error en editor_admin: {e}")
        return f"Error al cargar el editor: {str(e)}", 500

# ==================== API ENDPOINTS ====================

@app.route('/api/tutorial/<tutorial_id>/contenido', methods=['GET'])
def get_contenido(tutorial_id):
    """Obtener contenido de un tutorial desde JSON"""
    try:
        contenidos = cargar_contenidos()
        
        if tutorial_id in contenidos:
            return jsonify({
                "success": True,
                "data": contenidos[tutorial_id]
            }), 200
        else:
            return jsonify({
                "success": False,
                "message": "Contenido no encontrado"
            }), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/tutorial/<tutorial_id>/contenido', methods=['POST'])
def guardar_contenido(tutorial_id):
    """Guardar contenido de un tutorial en JSON"""
    try:
        global tutorials_collection
        if tutorials_collection is None:
            conectar_mongodb()
        
        data = request.get_json()
        contenidos = cargar_contenidos()
        
        tutorial_data = {}
        if tutorials_collection is not None:
            try:
                tutorial = tutorials_collection.find_one({"_id": ObjectId(tutorial_id)})
                if tutorial:
                    tutorial_data = tutorial
            except Exception:
                pass
        
        if not tutorial_data and tutorial_id in contenidos:
            tutorial_data = contenidos[tutorial_id]
        
        if not tutorial_data:
            return jsonify({"error": "Tutorial no encontrado"}), 404
        
        contenidos[tutorial_id] = {
            'title': data.get('title', tutorial_data.get('title')),
            'language': data.get('language', tutorial_data.get('language')),
            'level': data.get('level', tutorial_data.get('level')),
            'duration': data.get('duration', tutorial_data.get('duration')),
            'description': data.get('description', tutorial_data.get('description')),
            'content': data.get('content', ''),
            'lastUpdated': datetime.now().isoformat()
        }
        
        guardar_contenidos(contenidos)
        
        if tutorials_collection is not None:
            try:
                tutorials_collection.update_one(
                    {"_id": ObjectId(tutorial_id)},
                    {"$set": {"content": data.get('content', '')}}
                )
            except Exception as e:
                print(f"⚠️ No se pudo actualizar en MongoDB: {e}")
        
        return jsonify({
            "success": True,
            "message": "Contenido guardado exitosamente",
            "data": contenidos[tutorial_id]
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/sincronizar-json', methods=['POST'])
def sincronizar():
    """Sincronizar MongoDB con JSON"""
    try:
        if sincronizar_json():
            return jsonify({
                "success": True,
                "message": "JSON sincronizado exitosamente"
            }), 200
        else:
            return jsonify({
                "success": False,
                "message": "Error sincronizando JSON"
            }), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/tutoriales', methods=['GET'])
def get_all_tutoriales():
    """Obtener todos los tutoriales"""
    try:
        global tutorials_collection
        if tutorials_collection is None:
            conectar_mongodb()
        
        tutoriales_list = []
        
        if tutorials_collection is not None:
            try:
                tutoriales_list = list(tutorials_collection.find({}, {"_id": 1, "title": 1, "description": 1, "level": 1, "duration": 1, "language": 1}))
                for tutorial in tutoriales_list:
                    tutorial['_id'] = str(tutorial['_id'])
            except Exception as e:
                print(f"Error consultando MongoDB: {e}")
                tutoriales_list = []
        
        if not tutoriales_list:
            contenidos = cargar_contenidos()
            tutoriales_list = [
                {
                    '_id': tid,
                    'title': content.get('title', 'Sin título'),
                    'description': content.get('description', ''),
                    'level': content.get('level', 'principiante'),
                    'duration': content.get('duration', '0'),
                    'language': content.get('language', 'python')
                }
                for tid, content in contenidos.items()
            ]
        
        return jsonify({
            "success": True,
            "count": len(tutoriales_list),
            "data": tutoriales_list
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/tutorial/nuevo', methods=['POST'])
def crear_tutorial():
    """Crear un nuevo tutorial"""
    try:
        global tutorials_collection
        if tutorials_collection is None:
            conectar_mongodb()
        
        data = request.get_json()
        
        if not data.get('title') or not data.get('description') or not data.get('duration'):
            return jsonify({"error": "Faltan campos requeridos"}), 400
        
        nuevo_tutorial = {
            'title': data.get('title'),
            'description': data.get('description'),
            'language': data.get('language', 'python'),
            'level': data.get('level', 'principiante'),
            'duration': data.get('duration'),
            'content': data.get('content', ''),
            'createdAt': datetime.now()
        }
        
        tutorial_id = None
        
        if tutorials_collection is not None:
            try:
                resultado = tutorials_collection.insert_one(nuevo_tutorial)
                tutorial_id = str(resultado.inserted_id)
            except Exception as e:
                print(f"⚠️ No se pudo insertar en MongoDB: {e}")
        
        if not tutorial_id:
            tutorial_id = str(uuid.uuid4())
        
        contenidos = cargar_contenidos()
        contenidos[tutorial_id] = {
            'title': nuevo_tutorial['title'],
            'language': nuevo_tutorial['language'],
            'level': nuevo_tutorial['level'],
            'duration': nuevo_tutorial['duration'],
            'description': nuevo_tutorial['description'],
            'content': nuevo_tutorial['content'],
            'lastUpdated': datetime.now().isoformat()
        }
        guardar_contenidos(contenidos)
        
        return jsonify({
            "success": True,
            "message": "Tutorial creado exitosamente",
            "tutorial_id": tutorial_id
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/tutorial/<tutorial_id>', methods=['DELETE'])
def eliminar_tutorial(tutorial_id):
    """Eliminar un tutorial"""
    try:
        global tutorials_collection
        if tutorials_collection is None:
            conectar_mongodb()
        
        eliminado = False
        
        if tutorials_collection is not None:
            try:
                resultado = tutorials_collection.delete_one({"_id": ObjectId(tutorial_id)})
                eliminado = resultado.deleted_count > 0
            except Exception as e:
                print(f"⚠️ No se pudo eliminar de MongoDB: {e}")
        
        contenidos = cargar_contenidos()
        if tutorial_id in contenidos:
            del contenidos[tutorial_id]
            guardar_contenidos(contenidos)
            eliminado = True
        
        if not eliminado:
            return jsonify({"error": "Tutorial no encontrado"}), 404
        
        return jsonify({
            "success": True,
            "message": "Tutorial eliminado exitosamente"
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Verificar el estado de la API"""
    try:
        global tutorials_collection
        if tutorials_collection is None:
            conectar_mongodb()
        
        if tutorials_collection is not None:
            return jsonify({
                "status": "healthy",
                "database": "connected",
                "timestamp": datetime.now().isoformat()
            }), 200
        else:
            return jsonify({
                "status": "degraded",
                "database": "disconnected",
                "fallback": "using JSON",
                "timestamp": datetime.now().isoformat()
            }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/snippets')
def snippets():
    return render_template('snippets.html')

@app.route('/tutorial/snippets')
def snippets_tutorial():
    return render_template('snippets-tutorial.html')

HERRAMIENTAS = {
    'imc': {
        'template': 'imc.html',
        'title': 'Calculadora IMC'
    },
    'convertidor': {
        'template': 'convertidor.html',
        'title': 'Convertidor de Unidades'
    },
    'calculadora': {
        'template': 'calculadora.html',
        'title': 'Calculadora'
    }
}

@app.route('/herramientas')
def listar_herramientas():
    """Ruta para la página principal que lista las herramientas."""
    return render_template('herramientas.html', current_tool='list')

@app.route('/qrgen')
def qrgen():
    return render_template("qr.html")

@app.route('/terminos')
def term():
    return render_template("terminos.html")

@app.route('/contacto')
def contac():
    return render_template("contacto.html")

@app.route('/privacidad')
def priv():
    return render_template("privacidad.html")

@app.route('/convertidor')
def convert():
    return render_template("convertidor.html")

@app.route('/caluladora_fechas')
def fechas_cal():
    return render_template("calculadora_fechas.html")

@app.route('/notas')
def notas():
    return render_template("notas.html")

@app.route('/tiktok')
def tiktok_page():
    return render_template("tiktok.html")

@app.route('/tiktok-download', methods=['POST'])
def tiktok_download():
    video_url = request.form.get('url')
    if not video_url:
        flash("Error: No se proporcionó una URL de TikTok.", "error")
        return redirect(url_for('tiktok_page'))

    try:
        api_url = "https://tikwm.com/api"
        response = requests.get(api_url, params={"url": video_url})
        data = response.json()

        if data["code"] != 0:
            flash(f"{data['msg']}", "error")
            return redirect(url_for('tiktok_page'))

        video_download_url = data["data"]["play"]
        video_content = requests.get(video_download_url).content
        filename = f"tiktok_{uuid.uuid4().hex}.mp4"
        filepath = os.path.join(DOWNLOAD_FOLDER, filename)

        with open(filepath, "wb") as f:
            f.write(video_content)

        return send_file(filepath, as_attachment=True)

    except Exception as e:
        flash(f"Ocurrió un error inesperado: {str(e)}", "error")
        return redirect(url_for('tiktok_page'))

@app.route('/herramienta/<nombre_herramienta>')
def mostrar_herramienta(nombre_herramienta):
    """Ruta dinámica que renderiza la herramienta seleccionada."""
    herramienta_info = HERRAMIENTAS.get(nombre_herramienta)
    
    if herramienta_info:
        return render_template(
            herramienta_info['template'], 
            title=herramienta_info['title'],
            current_tool=nombre_herramienta
        )
    else:
        abort(404)

# ==================== MANEJO DE ERRORES ====================

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Error interno del servidor"}), 500

# ==================== MAIN ===================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)