# =============================================================================
# Archivo: server.py
# Descripción: Servidor principal que integra:
#   1. Servidor gRPC  → expone ChatService (SendMessage / GetMessages)
#   2. Bridge REST    → API HTTP para que el frontend (navegador) se comunique
#                       con el servicio gRPC sin necesidad de gRPC-Web.
#   3. Servidor de archivos estáticos → sirve el frontend (HTML/CSS/JS).
#
# Base de datos: Google Cloud Firestore (Firebase)
# =============================================================================

import os
import sys
import json
import time
import hashlib
import logging
import threading
from datetime import datetime, timezone
from concurrent import futures

# ── gRPC ─────────────────────────────────────────────────────────────────────
import grpc

# ── Flask (bridge REST + archivos estáticos) ─────────────────────────────────
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# ── Firebase / Firestore ─────────────────────────────────────────────────────
import firebase_admin
from firebase_admin import credentials, firestore

# ── Cargar variables de entorno desde .env (si existe) ───────────────────────
from dotenv import load_dotenv
load_dotenv()

# ── Stubs generados a partir de chat.proto ───────────────────────────────────
import chat_pb2
import chat_pb2_grpc

# =============================================================================
# Configuración de logging
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("ChatServer")

# =============================================================================
# Inicialización de Firebase
# =============================================================================

def init_firebase():
    """
    Inicializa la conexión con Firebase/Firestore.
    Soporta dos modos de configuración:
      • FIREBASE_CREDENTIALS_JSON  → contenido JSON directo (ideal para Render)
      • GOOGLE_APPLICATION_CREDENTIALS → ruta al archivo JSON local
    """
    try:
        # Opción 1: credenciales como variable de entorno JSON (Render / CI)
        creds_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
        if creds_json:
            creds_dict = json.loads(creds_json)
            cred = credentials.Certificate(creds_dict)
            logger.info("Firebase inicializado con FIREBASE_CREDENTIALS_JSON.")
        else:
            # Opción 2: ruta al archivo JSON local
            creds_path = os.environ.get(
                "GOOGLE_APPLICATION_CREDENTIALS",
                "serviceAccountKey.json",
            )
            if not os.path.exists(creds_path):
                logger.error(
                    "No se encontró el archivo de credenciales: %s", creds_path
                )
                sys.exit(1)
            cred = credentials.Certificate(creds_path)
            logger.info("Firebase inicializado con archivo: %s", creds_path)

        firebase_admin.initialize_app(cred)
        db = firestore.client()
        logger.info("Conexión con Firestore establecida correctamente.")
        return db
    except Exception as exc:
        logger.exception("Error al inicializar Firebase: %s", exc)
        sys.exit(1)


db = init_firebase()

# Referencia a las colecciones en Firestore
MESSAGES_COLLECTION = os.environ.get("FIRESTORE_COLLECTION", "messages")
USERS_COLLECTION = "users"


def hash_password(password):
    """Genera un hash SHA-256 de la contraseña."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

# =============================================================================
# Implementación del servicio gRPC — ChatService
# =============================================================================

class ChatServiceServicer(chat_pb2_grpc.ChatServiceServicer):
    """Implementación concreta de los métodos definidos en chat.proto."""

    # ── Autenticación ────────────────────────────────────────────────────

    def RegisterUser(self, request, context):
        """
        Registra un nuevo usuario en Firestore.
        Valida que el username no exista y que los campos no estén vacíos.
        La contraseña se almacena como hash SHA-256.
        """
        try:
            username = request.username.strip()
            password = request.password.strip()

            # Validar campos vacíos
            if not username or not password:
                return chat_pb2.RegisterResponse(
                    success=False,
                    detail="El nombre de usuario y la contraseña son obligatorios.",
                )

            # Validar longitud mínima
            if len(username) < 3:
                return chat_pb2.RegisterResponse(
                    success=False,
                    detail="El nombre de usuario debe tener al menos 3 caracteres.",
                )

            if len(password) < 4:
                return chat_pb2.RegisterResponse(
                    success=False,
                    detail="La contraseña debe tener al menos 4 caracteres.",
                )

            # Verificar si el usuario ya existe (username como ID del documento)
            user_ref = db.collection(USERS_COLLECTION).document(username.lower())
            user_doc = user_ref.get()

            if user_doc.exists:
                return chat_pb2.RegisterResponse(
                    success=False,
                    detail="El nombre de usuario ya está registrado.",
                )

            # Crear el usuario con contraseña hasheada
            user_ref.set({
                "username": username,
                "password_hash": hash_password(password),
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

            logger.info("Usuario registrado: %s", username)
            return chat_pb2.RegisterResponse(
                success=True,
                detail="Usuario registrado exitosamente.",
            )

        except Exception as exc:
            logger.exception("Error en RegisterUser: %s", exc)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error interno: {exc}")
            return chat_pb2.RegisterResponse(
                success=False,
                detail=f"Error interno del servidor: {exc}",
            )

    def LoginUser(self, request, context):
        """
        Verifica las credenciales de un usuario contra Firestore.
        Compara el hash de la contraseña proporcionada con el almacenado.
        """
        try:
            username = request.username.strip()
            password = request.password.strip()

            if not username or not password:
                return chat_pb2.LoginResponse(
                    success=False,
                    detail="El nombre de usuario y la contraseña son obligatorios.",
                )

            # Buscar el usuario por su username (ID del documento)
            user_ref = db.collection(USERS_COLLECTION).document(username.lower())
            user_doc = user_ref.get()

            if not user_doc.exists:
                return chat_pb2.LoginResponse(
                    success=False,
                    detail="El usuario no existe. Regístrate primero.",
                )

            user_data = user_doc.to_dict()
            stored_hash = user_data.get("password_hash", "")

            # Comparar contraseñas
            if hash_password(password) != stored_hash:
                return chat_pb2.LoginResponse(
                    success=False,
                    detail="Contraseña incorrecta.",
                )

            logger.info("Login exitoso: %s", username)
            return chat_pb2.LoginResponse(
                success=True,
                detail="Inicio de sesión exitoso.",
            )

        except Exception as exc:
            logger.exception("Error en LoginUser: %s", exc)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error interno: {exc}")
            return chat_pb2.LoginResponse(
                success=False,
                detail=f"Error interno del servidor: {exc}",
            )

    # ── Mensajes ─────────────────────────────────────────────────────────

    def SendMessage(self, request, context):
        """
        Recibe un mensaje (username + message), le asigna un timestamp
        y lo almacena en Firestore.
        """
        try:
            username = request.username.strip()
            message = request.message.strip()

            if not username or not message:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("El nombre de usuario y el mensaje son obligatorios.")
                return chat_pb2.SendMessageResponse(
                    success=False,
                    detail="Campos vacíos.",
                )

            timestamp = datetime.now(timezone.utc).isoformat()

            doc_data = {
                "username": username,
                "message": message,
                "timestamp": timestamp,
            }

            db.collection(MESSAGES_COLLECTION).add(doc_data)
            logger.info("Mensaje guardado: %s → %s", username, message[:50])

            return chat_pb2.SendMessageResponse(
                success=True,
                detail="Mensaje enviado correctamente.",
            )

        except Exception as exc:
            logger.exception("Error en SendMessage: %s", exc)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error interno: {exc}")
            return chat_pb2.SendMessageResponse(
                success=False,
                detail=f"Error interno del servidor: {exc}",
            )

    def GetMessages(self, request, context):
        """
        Retorna todos los mensajes almacenados en Firestore,
        ordenados de forma ascendente por timestamp.
        """
        try:
            docs = (
                db.collection(MESSAGES_COLLECTION)
                .order_by("timestamp", direction=firestore.Query.ASCENDING)
                .stream()
            )

            messages = []
            for doc in docs:
                data = doc.to_dict()
                messages.append(
                    chat_pb2.ChatMessage(
                        username=data.get("username", "Anónimo"),
                        message=data.get("message", ""),
                        timestamp=data.get("timestamp", ""),
                    )
                )

            logger.info("GetMessages: %d mensajes retornados.", len(messages))
            return chat_pb2.GetMessagesResponse(messages=messages)

        except Exception as exc:
            logger.exception("Error en GetMessages: %s", exc)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error interno: {exc}")
            return chat_pb2.GetMessagesResponse(messages=[])

# =============================================================================
# Servidor gRPC
# =============================================================================

GRPC_PORT = os.environ.get("GRPC_PORT", "50051")


def serve_grpc():
    """Inicia el servidor gRPC en un hilo separado."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    chat_pb2_grpc.add_ChatServiceServicer_to_server(ChatServiceServicer(), server)
    server.add_insecure_port(f"[::]:{GRPC_PORT}")
    server.start()
    logger.info("Servidor gRPC escuchando en el puerto %s", GRPC_PORT)
    return server

# =============================================================================
# Bridge REST (Flask) — permite al frontend comunicarse vía HTTP
# =============================================================================

# Ruta absoluta al directorio del frontend
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR)
CORS(app)  # Habilitar CORS para desarrollo local


# ── Endpoints REST — Autenticación ───────────────────────────────────────────

@app.route("/api/register", methods=["POST"])
def api_register():
    """Registra un nuevo usuario."""
    try:
        data = request.get_json(force=True)
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()

        if not username or not password:
            return jsonify({
                "success": False,
                "detail": "Se requieren los campos 'username' y 'password'.",
            }), 400

        channel = grpc.insecure_channel(f"localhost:{GRPC_PORT}")
        stub = chat_pb2_grpc.ChatServiceStub(channel)
        response = stub.RegisterUser(
            chat_pb2.RegisterRequest(username=username, password=password)
        )

        status_code = 200 if response.success else 409
        return jsonify({
            "success": response.success,
            "detail": response.detail,
        }), status_code

    except grpc.RpcError as rpc_err:
        logger.error("gRPC error en POST /api/register: %s", rpc_err)
        return jsonify({"success": False, "detail": str(rpc_err)}), 500
    except Exception as exc:
        logger.error("Error en POST /api/register: %s", exc)
        return jsonify({"success": False, "detail": str(exc)}), 500


@app.route("/api/login", methods=["POST"])
def api_login():
    """Inicia sesión de un usuario existente."""
    try:
        data = request.get_json(force=True)
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()

        if not username or not password:
            return jsonify({
                "success": False,
                "detail": "Se requieren los campos 'username' y 'password'.",
            }), 400

        channel = grpc.insecure_channel(f"localhost:{GRPC_PORT}")
        stub = chat_pb2_grpc.ChatServiceStub(channel)
        response = stub.LoginUser(
            chat_pb2.LoginRequest(username=username, password=password)
        )

        status_code = 200 if response.success else 401
        return jsonify({
            "success": response.success,
            "detail": response.detail,
        }), status_code

    except grpc.RpcError as rpc_err:
        logger.error("gRPC error en POST /api/login: %s", rpc_err)
        return jsonify({"success": False, "detail": str(rpc_err)}), 500
    except Exception as exc:
        logger.error("Error en POST /api/login: %s", exc)
        return jsonify({"success": False, "detail": str(exc)}), 500


# ── Endpoints REST — Mensajes ────────────────────────────────────────────────

@app.route("/api/messages", methods=["GET"])
def api_get_messages():
    """Retorna la lista de mensajes en formato JSON."""
    try:
        channel = grpc.insecure_channel(f"localhost:{GRPC_PORT}")
        stub = chat_pb2_grpc.ChatServiceStub(channel)
        response = stub.GetMessages(chat_pb2.GetMessagesRequest())

        messages = [
            {
                "username": m.username,
                "message": m.message,
                "timestamp": m.timestamp,
            }
            for m in response.messages
        ]
        return jsonify({"success": True, "messages": messages}), 200

    except grpc.RpcError as rpc_err:
        logger.error("gRPC error en GET /api/messages: %s", rpc_err)
        return jsonify({"success": False, "error": str(rpc_err)}), 500
    except Exception as exc:
        logger.error("Error en GET /api/messages: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/messages", methods=["POST"])
def api_send_message():
    """Recibe un mensaje vía POST y lo envía al servicio gRPC."""
    try:
        data = request.get_json(force=True)
        username = data.get("username", "").strip()
        message = data.get("message", "").strip()

        if not username or not message:
            return jsonify({
                "success": False,
                "error": "Se requieren los campos 'username' y 'message'.",
            }), 400

        channel = grpc.insecure_channel(f"localhost:{GRPC_PORT}")
        stub = chat_pb2_grpc.ChatServiceStub(channel)
        response = stub.SendMessage(
            chat_pb2.SendMessageRequest(username=username, message=message)
        )

        return jsonify({
            "success": response.success,
            "detail": response.detail,
        }), 200 if response.success else 500

    except grpc.RpcError as rpc_err:
        logger.error("gRPC error en POST /api/messages: %s", rpc_err)
        return jsonify({"success": False, "error": str(rpc_err)}), 500
    except Exception as exc:
        logger.error("Error en POST /api/messages: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500


# ── Servir archivos estáticos del frontend ───────────────────────────────────

@app.route("/")
def index():
    """Sirve el archivo index.html del frontend."""
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    """Sirve cualquier archivo estático del frontend."""
    return send_from_directory(FRONTEND_DIR, filename)


# ── Health check ─────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    """Endpoint de verificación de salud para Render."""
    return jsonify({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}), 200

# =============================================================================
# Iniciar servidor gRPC al cargar el módulo (necesario para Gunicorn)
# =============================================================================
# El servidor gRPC se inicia en un hilo separado tanto cuando se ejecuta
# directamente (python server.py) como cuando Gunicorn importa este módulo.
grpc_server = serve_grpc()

# =============================================================================
# Punto de entrada principal (ejecución directa: python server.py)
# =============================================================================

if __name__ == "__main__":
    # Puerto HTTP (Render asigna PORT dinámicamente)
    HTTP_PORT = int(os.environ.get("PORT", 5000))

    logger.info("Servidor HTTP (Flask) escuchando en el puerto %d", HTTP_PORT)
    logger.info("Frontend disponible en: http://localhost:%d", HTTP_PORT)

    # Iniciar Flask (bridge REST + frontend)
    app.run(host="0.0.0.0", port=HTTP_PORT, debug=False)
