# 💬 gRPC Chat — Aplicación de Mensajería Web en Tiempo Real

## Descripción del Proyecto

**gRPC Chat** es una aplicación web de mensajería en tiempo real que implementa una arquitectura **cliente-servidor** utilizando **gRPC** como protocolo de comunicación, **Python** en el backend, **Firebase Firestore** como base de datos NoSQL y un frontend construido con **HTML, CSS y JavaScript puro** (sin frameworks).

El proyecto está diseñado como un entregable académico a nivel universitario que demuestra el uso práctico de tecnologías modernas de comunicación entre servicios.

---

## 📐 Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────┐
│                    USUARIO (Navegador)                   │
│          HTML + CSS + JavaScript (Frontend)              │
│                                                         │
│   ┌───────────────────────────────────────────────┐     │
│   │  Polling cada 2s   │   POST al enviar mensaje │     │
│   └────────┬───────────┴────────────┬─────────────┘     │
└────────────┼────────────────────────┼───────────────────┘
             │ HTTP/REST              │ HTTP/REST
             ▼                        ▼
┌─────────────────────────────────────────────────────────┐
│                  SERVIDOR (Python)                       │
│                                                         │
│   ┌─────────────────────────────────────────────┐       │
│   │         Flask (Bridge REST + Static)         │       │
│   │    GET /api/messages  │  POST /api/messages  │       │
│   └────────┬──────────────┴──────────┬──────────┘       │
│            │ gRPC (localhost:50051)   │                  │
│            ▼                         ▼                  │
│   ┌─────────────────────────────────────────────┐       │
│   │           Servidor gRPC (ChatService)        │       │
│   │      GetMessages()  │  SendMessage()         │       │
│   └────────┬────────────┴────────────┬──────────┘       │
│            │                         │                  │
└────────────┼─────────────────────────┼──────────────────┘
             │ Firestore SDK           │
             ▼                         ▼
┌─────────────────────────────────────────────────────────┐
│              Firebase / Firestore (NoSQL)                │
│                                                         │
│   Colección: messages                                   │
│   Documentos: { username, message, timestamp }          │
└─────────────────────────────────────────────────────────┘
```

### ¿Por qué gRPC?

**gRPC (Google Remote Procedure Call)** es un framework de comunicación de alto rendimiento desarrollado por Google. A diferencia de REST:

| Característica | REST (JSON/HTTP) | gRPC (Protobuf/HTTP/2) |
|---|---|---|
| Formato de datos | JSON (texto) | Protocol Buffers (binario) |
| Rendimiento | Moderado | Alto |
| Tipado | Débil | Fuerte (esquema .proto) |
| Streaming | Limitado | Bidireccional nativo |
| Generación de código | Manual | Automática |

En este proyecto, gRPC se usa para la comunicación interna entre el bridge REST (Flask) y el servicio de chat, demostrando cómo definir contratos con Protocol Buffers y generar código automáticamente.

> **Nota:** Los navegadores no pueden consumir gRPC directamente, por lo que se incluye un **bridge REST** (Flask) que traduce peticiones HTTP a llamadas gRPC.

### ¿Por qué Firebase/Firestore?

- **Sin servidor de base de datos:** Firestore es serverless y se escala automáticamente.
- **Tiempo real:** Aunque en este proyecto usamos polling, Firestore soporta listeners en tiempo real.
- **Gratuito:** El plan Spark de Firebase ofrece un generoso tier gratuito (50K lecturas/día, 20K escrituras/día).
- **SDK oficial para Python:** `firebase-admin` proporciona integración directa y segura.
- **Ideal para prototipos:** Configuración rápida sin necesidad de gestionar infraestructura.

---

## 📁 Estructura del Proyecto

```
gRPC/
├── backend/
│   ├── protos/
│   │   └── chat.proto          # Definición del servicio gRPC
│   ├── server.py               # Servidor gRPC + Bridge REST + Static files
│   ├── requirements.txt        # Dependencias de Python
│   ├── .env.example            # Plantilla de variables de entorno
│   └── serviceAccountKey.json  # Credenciales de Firebase (NO subir a Git)
├── frontend/
│   ├── index.html              # Página principal del chat
│   ├── style.css               # Estilos (diseño tipo mensajería)
│   └── script.js               # Lógica del cliente (polling + envío)
├── .gitignore                  # Archivos excluidos del repositorio
├── render.yaml                 # Configuración de despliegue en Render
└── README.md                   # Este archivo
```

---

## 🔧 Configuración de Firebase

### Paso 1: Crear un proyecto en Firebase

1. Ve a [Firebase Console](https://console.firebase.google.com/).
2. Haz clic en **"Agregar proyecto"** (o "Add project").
3. Escribe un nombre para tu proyecto, por ejemplo: `grpc-chat-app`.
4. (Opcional) Desactiva Google Analytics si no lo necesitas.
5. Haz clic en **"Crear proyecto"** y espera a que se configure.

### Paso 2: Habilitar Cloud Firestore

1. En el menú lateral izquierdo, selecciona **"Firestore Database"** (dentro de "Compilación" o "Build").
2. Haz clic en **"Crear base de datos"** (o "Create database").
3. Selecciona **"Modo de producción"** (Production mode).
4. Elige una ubicación para el servidor (ejemplo: `us-central1`, `southamerica-east1`).
5. Haz clic en **"Habilitar"**.

#### Reglas de seguridad (para desarrollo)

En la pestaña **"Reglas"** de Firestore, configura temporalmente:

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /messages/{messageId} {
      allow read, write: if true;
    }
  }
}
```

> ⚠️ **Importante:** Esta regla permite acceso abierto. Para producción, configura reglas más restrictivas.

### Paso 3: Generar el archivo de credenciales JSON

1. En Firebase Console, haz clic en el **ícono de engranaje** ⚙️ junto a "Descripción general del proyecto".
2. Selecciona **"Configuración del proyecto"** → pestaña **"Cuentas de servicio"**.
3. Asegúrate de que esté seleccionado **"Firebase Admin SDK"** con **Python**.
4. Haz clic en **"Generar nueva clave privada"**.
5. Se descargará un archivo JSON. **Renómbralo** a `serviceAccountKey.json`.
6. **Copia este archivo** a la carpeta `backend/`.

> ⚠️ **NUNCA subas este archivo a GitHub.** Ya está incluido en `.gitignore`.

---

## 🚀 Ejecución en Entorno Local

### Prerrequisitos

- **Python 3.9+** instalado ([descargar](https://www.python.org/downloads/))
- **pip** (gestor de paquetes de Python)
- **Git** instalado ([descargar](https://git-scm.com/downloads))
- Archivo `serviceAccountKey.json` en la carpeta `backend/`

### Paso 1: Clonar o acceder al proyecto

```bash
cd "ruta/a/tu/carpeta/gRPC"
```

### Paso 2: Crear y activar un entorno virtual

```bash
# Crear entorno virtual
python -m venv venv

# Activar (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Activar (Windows CMD)
venv\Scripts\activate.bat

# Activar (Linux/macOS)
source venv/bin/activate
```

### Paso 3: Instalar dependencias

```bash
cd backend
pip install -r requirements.txt
```

### Paso 4: Generar los stubs de gRPC

Desde la carpeta `backend/`, ejecuta:

```bash
python -m grpc_tools.protoc -I./protos --python_out=. --grpc_python_out=. ./protos/chat.proto
```

Esto generará dos archivos:
- `chat_pb2.py` — Clases de los mensajes Protocol Buffers
- `chat_pb2_grpc.py` — Clases del servicio gRPC (stub y servicer)

### Paso 5: Configurar las variables de entorno

```bash
# Copiar la plantilla
copy .env.example .env    # Windows
# cp .env.example .env    # Linux/macOS
```

Edita el archivo `.env` y verifica que la ruta al archivo de credenciales sea correcta:

```
GOOGLE_APPLICATION_CREDENTIALS=serviceAccountKey.json
FIRESTORE_COLLECTION=messages
GRPC_PORT=50051
```

### Paso 6: Iniciar el servidor

```bash
python server.py
```

Verás una salida similar a:

```
2026-03-03 10:00:00 [INFO] ChatServer — Firebase inicializado con archivo: serviceAccountKey.json
2026-03-03 10:00:00 [INFO] ChatServer — Conexión con Firestore establecida correctamente.
2026-03-03 10:00:00 [INFO] ChatServer — Servidor gRPC escuchando en el puerto 50051
2026-03-03 10:00:00 [INFO] ChatServer — Servidor HTTP (Flask) escuchando en el puerto 5000
2026-03-03 10:00:00 [INFO] ChatServer — Frontend disponible en: http://localhost:5000
```

### Paso 7: Abrir el chat

Abre tu navegador y ve a: **http://localhost:5000**

---

## 📤 Subir el Proyecto a GitHub

### Paso 1: Crear un repositorio en GitHub

1. Ve a [github.com/new](https://github.com/new).
2. Nombre del repositorio: `grpc-chat` (o el que prefieras).
3. Deja el repositorio **público** o **privado** según prefieras.
4. **NO** inicialices con README, .gitignore ni licencia (ya los tenemos).
5. Haz clic en **"Create repository"**.

### Paso 2: Inicializar Git y subir

Desde la carpeta raíz del proyecto (`gRPC/`):

```bash
# Inicializar repositorio Git
git init

# Agregar todos los archivos (respetando .gitignore)
git add .

# Crear el primer commit
git commit -m "feat: proyecto completo de chat web con gRPC, Firebase y Python"

# Conectar con el repositorio remoto
git remote add origin https://github.com/TU_USUARIO/grpc-chat.git

# Subir al repositorio
git branch -M main
git push -u origin main
```

> 🔒 Verifica que `serviceAccountKey.json` **NO** aparezca en los archivos staged con `git status` antes de hacer push.

---

## 🌐 Despliegue en Render

### Paso 1: Crear cuenta en Render

1. Ve a [render.com](https://render.com/) y crea una cuenta (puedes usar tu cuenta de GitHub).

### Paso 2: Crear un nuevo Web Service

1. En el dashboard de Render, haz clic en **"New +"** → **"Web Service"**.
2. Conecta tu repositorio de GitHub (`grpc-chat`).
3. Configura los siguientes campos:

| Campo | Valor |
|---|---|
| **Name** | `grpc-chat` |
| **Region** | Oregon (US West) |
| **Branch** | `main` |
| **Root Directory** | `backend` |
| **Runtime** | Python |
| **Build Command** | `pip install -r requirements.txt && python -m grpc_tools.protoc -I./protos --python_out=. --grpc_python_out=. ./protos/chat.proto` |
| **Start Command** | `gunicorn server:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --preload` |

### Paso 3: Configurar las variables de entorno

En la sección **"Environment"** del servicio en Render:

1. Haz clic en **"Add Environment Variable"**.
2. Agrega las siguientes variables:

| Key | Value |
|---|---|
| `FIREBASE_CREDENTIALS_JSON` | *(Pega aquí el contenido completo del archivo `serviceAccountKey.json`)* |
| `FIRESTORE_COLLECTION` | `messages` |
| `GRPC_PORT` | `50051` |

> 📋 Para obtener el contenido del JSON, abre `serviceAccountKey.json` en un editor, selecciona todo el contenido y pégalo como valor de `FIREBASE_CREDENTIALS_JSON`.

### Paso 4: Desplegar

1. Haz clic en **"Create Web Service"**.
2. Render construirá e instalará las dependencias automáticamente.
3. Una vez desplegado, tendrás una URL como: `https://grpc-chat.onrender.com`.
4. Abre esa URL en tu navegador para usar el chat.

### Nota sobre Render (plan gratuito)

- Los servicios gratuitos de Render se **suspenden después de 15 minutos de inactividad**.
- La primera petición después de la suspensión puede tardar ~30 segundos.
- Para mantener el servicio activo, puedes usar un servicio de ping externo como [UptimeRobot](https://uptimerobot.com/).

---

## 🧪 Probar el Chat

1. Abre **dos pestañas** del navegador en `http://localhost:5000` (o la URL de Render).
2. En cada pestaña, ingresa un **nombre de usuario diferente**.
3. Envía mensajes desde ambas pestañas.
4. Los mensajes aparecerán en ambas ventanas gracias al **polling cada 2 segundos**.

---

## 📋 Definición del Servicio gRPC (chat.proto)

```protobuf
service ChatService {
  rpc SendMessage (SendMessageRequest) returns (SendMessageResponse);
  rpc GetMessages (GetMessagesRequest) returns (GetMessagesResponse);
}
```

- **SendMessage:** Recibe `username` y `message`, asigna un `timestamp` y almacena el documento en Firestore. Retorna un booleano `success` y un `detail`.
- **GetMessages:** Retorna todos los mensajes de la colección `messages`, ordenados ascendentemente por `timestamp`.

---

## 🛠️ Tecnologías Utilizadas

| Componente | Tecnología | Versión |
|---|---|---|
| Protocolo de comunicación | gRPC + Protocol Buffers | 1.68.x |
| Backend | Python | 3.11+ |
| Framework REST | Flask | 3.1.x |
| Base de datos | Firebase Firestore | — |
| SDK de Firebase | firebase-admin | 6.6.x |
| Frontend | HTML5 + CSS3 + JavaScript ES6 | — |
| Servidor WSGI | Gunicorn | 23.x |
| Despliegue | Render | — |

---

## ⚠️ Consideraciones de Seguridad

1. **Nunca subas las credenciales de Firebase** (`serviceAccountKey.json`) al repositorio.
2. En producción, usa **variables de entorno** para las credenciales (`FIREBASE_CREDENTIALS_JSON`).
3. Configura **reglas de seguridad** adecuadas en Firestore para producción.
4. Implementa **validación y sanitización** en el servidor para prevenir inyección.
5. Considera agregar **autenticación** (Firebase Auth) para entornos de producción.

---

## 📝 Licencia

Este proyecto fue desarrollado con fines educativos y puede ser utilizado libremente.

---

*Proyecto desarrollado como ejercicio académico para demostrar la implementación de gRPC con Python, Firebase Firestore y frontend vanilla.*
