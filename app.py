#!/usr/bin/env python3
# app.py corregido






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

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'advpjsh')

# ==============================
# ⚙️ Configuración
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

os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Variable global para la colección
tutorials_collection = None
mongo_client = None

# ==============================
# 🔌 Conexión a MongoDB
# ==============================
def conectar_mongodb():
    """Intenta conectar a MongoDB y devuelve la colección"""
    global tutorials_collection, mongo_client
    try:
        if mongo_client is None:
            mongo_client = MongoClient(
                MONGO_URI,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                tls=True,
                tlsAllowInvalidCertificates=True
            )
        
        mongo_client.admin.command('ping')
        db = mongo_client[DB_NAME]
        tutorials_collection = db[COLLECTION_NAME]
        print("✅ Conectado a MongoDB Atlas")
        return tutorials_collection
    except Exception as e:
        print(f"❌ Error al conectar a MongoDB: {e}")
        tutorials_collection = None
        return None

# Intentar conectar al iniciar
conectar_mongodb()

# ==============================
# 📝 Funciones JSON
# ==============================
def cargar_contenidos():
    """Carga el archivo JSON de contenidos"""
    if os.path.exists(CONTENIDO_FILE):
        try:
            with open(CONTENIDO_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Error cargando JSON: {e}")
            return {}
    return {}

def guardar_contenidos(contenidos):
    """Guarda los contenidos en el archivo JSON"""
    try:
        with open(CONTENIDO_FILE, 'w', encoding='utf-8') as f:
            json.dump(contenidos, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ Error guardando JSON: {e}")
        return False

def obtener_tutoriales_safe():
    """Obtiene tutoriales de MongoDB o JSON como fallback"""
    tutoriales_list = []
    
    # Intentar desde MongoDB
    try:
        if tutorials_collection is None:
            conectar_mongodb()
        
        if tutorials_collection is not None:
            tutoriales_list = list(tutorials_collection.find(
                {},
                {"_id": 1, "title": 1, "description": 1, "level": 1, "duration": 1, "language": 1, "content": 1}
            ))
            for tutorial in tutoriales_list:
                tutorial['_id'] = str(tutorial['_id'])
            print(f"✅ {len(tutoriales_list)} tutoriales cargados desde MongoDB")
    except Exception as e:
        print(f"⚠️ Error consultando MongoDB: {e}")
        tutoriales_list = []
    
    # Fallback a JSON si MongoDB falla
    if not tutoriales_list:
        print("📄 Usando JSON como fallback...")
        contenidos = cargar_contenidos()
        tutoriales_list = [
            {
                '_id': tid,
                'title': content.get('title', 'Sin título'),
                'description': content.get('description', ''),
                'level': content.get('level', 'principiante'),
                'duration': content.get('duration', '30 min'),
                'language': content.get('language', 'python'),
                'content': content.get('content', '<p>Contenido no disponible</p>')
            }
            for tid, content in contenidos.items()
        ]
        print(f"✅ {len(tutoriales_list)} tutoriales cargados desde JSON")
    
    return tutoriales_list

# ==================== RUTAS ====================

@app.route('/')
def inicio():
    """Página de inicio"""
    return render_template('index.html')

@app.route('/tutoriales')
def tutoriales():
    """Página de tutoriales"""
    try:
        tutoriales_list = obtener_tutoriales_safe()
        print(f"📚 Renderizando {len(tutoriales_list)} tutoriales")
        
        # DEBUG: Imprime los tutoriales
        for t in tutoriales_list:
            print(f"   - {t.get('title')} | ID: {t.get('_id')} | Lang: {t.get('language')}")
        
        return render_template('tutoriales.html', tutoriales=tutoriales_list)
    except Exception as e:
        print(f"❌ Error crítico en /tutoriales: {e}")
        import traceback
        traceback.print_exc()
        return render_template('tutoriales.html', tutoriales=[])
    

@app.route('/tutorial/<tutorial_id>')
def ver_tutorial(tutorial_id):
    """Ver un tutorial específico"""
    try:
        tutorial = None
        
        # Intentar desde MongoDB
        if tutorials_collection is None:
            conectar_mongodb()
        
        if tutorials_collection is not None:
            try:
                tutorial = tutorials_collection.find_one({"_id": ObjectId(tutorial_id)})
                if tutorial:
                    tutorial['_id'] = str(tutorial['_id'])
                    print(f"✅ Tutorial {tutorial_id} cargado desde MongoDB")
            except Exception as e:
                print(f"⚠️ Error consultando MongoDB para tutorial {tutorial_id}: {e}")
        
        # Fallback a JSON
        if not tutorial:
            contenidos = cargar_contenidos()
            if tutorial_id in contenidos:
                tutorial = {
                    '_id': tutorial_id,
                    **contenidos[tutorial_id]
                }
                print(f"✅ Tutorial {tutorial_id} cargado desde JSON")
        
        if not tutorial:
            print(f"❌ Tutorial {tutorial_id} no encontrado")
            return "❌ Tutorial no encontrado", 404
        
        # Asegurar que content existe
        if 'content' not in tutorial or not tutorial['content']:
            tutorial['content'] = '<p>Contenido no disponible</p>'
        
        return render_template('tutorial-detalle.html', tutorial=tutorial)
    except Exception as e:
        print(f"❌ Error en ver_tutorial: {e}")
        return f"Error al cargar el tutorial: {str(e)}", 500

@app.route('/admin/editor')
def editor_admin():
    """Editor de tutoriales"""
    try:
        tutoriales_list = obtener_tutoriales_safe()
        return render_template('admin-editor.html', tutoriales=tutoriales_list)
    except Exception as e:
        print(f"❌ Error en editor_admin: {e}")
        return render_template('admin-editor.html', tutoriales=[])

# ==================== API ENDPOINTS ====================

@app.route('/api/tutorial/<tutorial_id>/contenido', methods=['GET'])
def get_contenido(tutorial_id):
    """Obtener contenido de un tutorial"""
    try:
        # Primero intentar MongoDB
        if tutorials_collection is not None:
            try:
                tutorial = tutorials_collection.find_one({"_id": ObjectId(tutorial_id)})
                if tutorial:
                    return jsonify({
                        "success": True,
                        "data": {
                            "title": tutorial.get('title'),
                            "language": tutorial.get('language'),
                            "level": tutorial.get('level'),
                            "duration": tutorial.get('duration'),
                            "description": tutorial.get('description'),
                            "content": tutorial.get('content', '<p>Contenido no disponible</p>')
                        }
                    }), 200
            except Exception as e:
                print(f"⚠️ Error consultando MongoDB: {e}")
        
        # Fallback a JSON
        contenidos = cargar_contenidos()
        if tutorial_id in contenidos:
            return jsonify({
                "success": True,
                "data": contenidos[tutorial_id]
            }), 200
        
        return jsonify({
            "success": False,
            "message": "Contenido no encontrado"
        }), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/tutorial/<tutorial_id>/contenido', methods=['POST'])
def guardar_contenido(tutorial_id):
    """Guardar contenido de un tutorial"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No se recibieron datos"}), 400
        
        # Cargar contenidos actuales
        contenidos = cargar_contenidos()
        
        # Crear/actualizar contenido
        contenidos[tutorial_id] = {
            'title': data.get('title', ''),
            'language': data.get('language', 'python'),
            'level': data.get('level', 'principiante'),
            'duration': data.get('duration', '30 min'),
            'description': data.get('description', ''),
            'content': data.get('content', ''),
            'lastUpdated': datetime.now().isoformat()
        }
        
        # Guardar en JSON
        if not guardar_contenidos(contenidos):
            return jsonify({"error": "Error al guardar en JSON"}), 500
        
        # Intentar actualizar en MongoDB
        if tutorials_collection is not None:
            try:
                tutorials_collection.update_one(
                    {"_id": ObjectId(tutorial_id)},
                    {"$set": {
                        "content": data.get('content', ''),
                        "title": data.get('title', ''),
                        "description": data.get('description', ''),
                        "lastUpdated": datetime.now()
                    }},
                    upsert=False
                )
                print(f"✅ Tutorial {tutorial_id} actualizado en MongoDB")
            except Exception as e:
                print(f"⚠️ No se pudo actualizar en MongoDB: {e}")
        
        return jsonify({
            "success": True,
            "message": "Contenido guardado exitosamente",
            "data": contenidos[tutorial_id]
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/tutoriales', methods=['GET'])
def get_all_tutoriales():
    """Obtener todos los tutoriales (API)"""
    try:
        tutoriales_list = obtener_tutoriales_safe()
        return jsonify({
            "success": True,
            "count": len(tutoriales_list),
            "data": tutoriales_list
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Estado de la API"""
    try:
        mongo_status = "disconnected"
        if tutorials_collection is not None:
            try:
                mongo_client.admin.command('ping')
                mongo_status = "connected"
            except:
                mongo_status = "disconnected"
        
        json_exists = os.path.exists(CONTENIDO_FILE)
        
        return jsonify({
            "status": "healthy" if mongo_status == "connected" or json_exists else "degraded",
            "database": mongo_status,
            "json_fallback": "available" if json_exists else "not found",
            "timestamp": datetime.now().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# ==================== OTRAS RUTAS ====================

@app.route('/snippets')
def snippets():
    return render_template('snippets.html')

@app.route('/tutorial/snippets')
def snippets_tutorial():
    return render_template('snippets-tutorial.html')

@app.route('/herramientas')
def listar_herramientas():
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

HERRAMIENTAS = {
    'imc': {'template': 'imc.html', 'title': 'Calculadora IMC'},
    'convertidor': {'template': 'convertidor.html', 'title': 'Convertidor de Unidades'},
    'calculadora': {'template': 'calculadora.html', 'title': 'Calculadora'}
}

@app.route('/herramienta/<nombre_herramienta>')
def mostrar_herramienta(nombre_herramienta):
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
    return jsonify({"error": "Ruta no encontrada"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Error interno del servidor"}), 500

# ==================== MAIN ====================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"🚀 Iniciando servidor en puerto {port}")
    print(f"📊 MongoDB: {'Conectado' if tutorials_collection is not None else 'Desconectado (usando JSON)'}")
    app.run(debug=True, host='0.0.0.0', port=port)