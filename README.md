# Backend de persistencia multiagente

API asíncrona con FastAPI, MongoDB y Pydantic para consultar entidades
operativas y registrar trazas de ejecuciones de CrewAI.

## Configuración

1. Crea y activa un entorno virtual de Python.
2. Instala las dependencias del backend:

   ```bash
   pip install -r requirements.txt
   ```

3. Copia `.env.example` a `.env` y establece `MONGODB_URL`:
   - **MongoDB Atlas:** en Atlas, abre **Connect → Drivers**, copia la URI de
     conexión de Python y sustituye usuario, contraseña y nombre del clúster.
     Verifica también que la IP de tu equipo esté permitida en **Network Access**.
   - **MongoDB local:** usa `mongodb://localhost:27017` y asegúrate de que el
     servicio de MongoDB esté iniciado antes de ejecutar la API.

   No subas `.env` ni credenciales al repositorio. La URI es obligatoria; la
   aplicación ya no asume que MongoDB está instalado localmente.
4. Inicia el servidor desde la raíz:

   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

La aplicación verifica la conexión a MongoDB al iniciar y cierra el cliente al
terminar. Crea un índice único para `entidades.id_referencia` y un índice por
sesión/fecha en `trazas_ejecucion`. Si no hay URI configurada o MongoDB no está
disponible, el arranque informa el problema y falla explícitamente. La
documentación interactiva está en
`http://localhost:8000/docs`.

## Rutas principales

- `GET /api/v1/entidades/{id_referencia}`: consulta por identificador de dominio.
- `GET /api/v1/entidades/?tipo=Alumno&limit=50`: filtra por tipo.
- `POST /api/v1/entidades/`: crea o actualiza una entidad.
- `POST /api/v1/trazas/`: registra una acción de agente.
- `GET /api/v1/trazas/sesion/{session_id}?limit=500`: recupera trazas ordenadas
  cronológicamente.

El ejemplo opcional de cliente CrewAI requiere instalar también
`requirements-crewai.txt`; después se ejecuta con `python client_crewai_example.py`.
El `kickoff` se deja comentado para evitar iniciar una ejecución del agente por
accidente.

## Pruebas

```bash
python -m unittest discover -s .
```

Las pruebas de API simulan MongoDB y no requieren una instancia activa.
